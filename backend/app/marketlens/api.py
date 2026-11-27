from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request
from google.api_core.exceptions import GoogleAPIError

from app.api.dependencies import CurrentUser, get_runtime
from app.core.errors import AppError, IntegrationUnavailable, NotFound
from app.core.firebase import FirebaseRuntime
from app.marketlens.contracts import (
    Listing,
    ListingItem,
    ListingPage,
    PriceHistory,
    Source,
    StatsPage,
)
from app.marketlens.explanation import ExplanationResponse, explain
from app.marketlens.radar import RadarPage, radar
from app.marketlens.store import MarketStore

router = APIRouter(prefix="/api/v1/market", tags=["MarketLens"])
ListingId = Annotated[str, Path(pattern=r"^(olx|krisha|kolesa):[A-Za-z0-9_.-]{1,128}$")]


def market_store(runtime: Annotated[FirebaseRuntime, Depends(get_runtime)]) -> MarketStore:
    return MarketStore(runtime.db())


Store = Annotated[MarketStore, Depends(market_store)]


def matches(
    listing: Listing,
    *,
    q: str,
    category: str,
    city: str,
    source: Source | None,
    min_price: float | None,
    max_price: float | None,
) -> bool:
    return (
        (not category or category == listing.category.casefold())
        and (not city or city == (listing.city or "").casefold())
        and (source is None or source == listing.source)
        and (not q or q in f"{listing.title} {listing.description or ''}".casefold())
        # Price filters are denominated in KZT. Preserve other currencies in the catalog.
        and (
            min_price is None
            and max_price is None
            or listing.currency == "KZT"
            and listing.price is not None
            and (min_price is None or listing.price >= min_price)
            and (max_price is None or listing.price <= max_price)
        )
    )


@router.get("/listings", response_model=ListingPage)
def catalog(
    user: CurrentUser,
    store: Store,
    q: Annotated[str, Query(max_length=120)] = "",
    category: Annotated[str, Query(max_length=120)] = "",
    subcategory: Annotated[str, Query(max_length=120)] = "",
    city: Annotated[str, Query(max_length=120)] = "",
    source: Source | None = None,
    min_price: Annotated[float | None, Query(alias="minPrice", ge=0, allow_inf_nan=False)] = None,
    max_price: Annotated[float | None, Query(alias="maxPrice", ge=0, allow_inf_nan=False)] = None,
    view: Literal["all", "deals", "risk"] = "all",
    sort: Literal["default", "newest", "price_asc", "price_desc"] = "default",
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
    offset: Annotated[int, Query(ge=0, le=9_007_199_254_740_991)] = 0,
) -> ListingPage:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise AppError(422, "INVALID_PRICE_RANGE", "Minimum price exceeds maximum price")
    try:
        scanned_count = 0
        listings = []
        counts: dict[str, int] = {}
        covers: dict[str, str] = {}
        latest = None
        selected_subcategory = subcategory.strip().casefold()
        filters = dict(
            q=q.strip().casefold(),
            category=category.strip().casefold(),
            city=city.strip().casefold(),
            source=source,
            min_price=min_price,
            max_price=max_price,
        )
        for listing in store.iter_listings():
            scanned_count += 1
            if not matches(listing, **filters):
                continue
            category_key = (listing.subcategory or "").casefold()
            if category_key:
                counts[category_key] = counts.get(category_key, 0) + 1
                if category_key not in covers:
                    photo = next(
                        (image for image in listing.images if image.scheme == "https"), None
                    )
                    if photo is not None:
                        covers[category_key] = str(photo)
            if latest is None or listing.scraped_at > latest:
                latest = listing.scraped_at
            if not selected_subcategory or category_key == selected_subcategory:
                listings.append(listing)
        if sort == "newest":
            listings.sort(key=lambda listing: listing.scraped_at, reverse=True)
        elif sort in {"price_asc", "price_desc"}:
            priced = [
                item for item in listings if item.currency == "KZT" and item.price is not None
            ]
            priced_ids = {item.id for item in priced}
            priced.sort(key=lambda item: item.price or 0, reverse=sort == "price_desc")
            listings = priced + [item for item in listings if item.id not in priced_ids]
        if view == "all":
            items = store.with_analysis(listings[offset : offset + limit])
            total = len(listings)
        else:
            results = store.with_analysis(listings)
            selected = [
                item
                for item in results
                if item.analysis is not None
                and (
                    item.analysis.is_deal
                    if view == "deals"
                    else item.analysis.risk_level in {"medium", "high"}
                )
            ]
            if sort == "default":
                score = "deal_score" if view == "deals" else "risk_score"
                selected.sort(key=lambda item: getattr(item.analysis, score) or 0, reverse=True)
            items = selected[offset : offset + limit]
            total = len(selected)
    except GoogleAPIError:
        raise IntegrationUnavailable("MarketLens Firestore") from None
    return ListingPage(
        items=items,
        next_offset=offset + limit if offset + limit < total else None,
        scanned_count=scanned_count,
        scan_limited=False,
        total=total,
        subcategory_counts=counts,
        subcategory_photos=covers,
        latest_scraped_at=latest,
    )


def listing_item(store: MarketStore, listing_id: str) -> ListingItem:
    try:
        listing = store.get_listing(listing_id)
        if listing is None:
            raise NotFound()
        return store.with_analysis([listing])[0]
    except GoogleAPIError:
        raise IntegrationUnavailable("MarketLens Firestore") from None


@router.get("/listings/{listing_id}", response_model=ListingItem)
def detail(listing_id: ListingId, user: CurrentUser, store: Store) -> ListingItem:
    return listing_item(store, listing_id)


@router.get("/listings/{listing_id}/history", response_model=PriceHistory)
def history(
    listing_id: ListingId,
    user: CurrentUser,
    store: Store,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PriceHistory:
    try:
        if store.get_listing(listing_id) is None:
            raise NotFound()
        return store.price_history(listing_id, limit)
    except GoogleAPIError:
        raise IntegrationUnavailable("MarketLens Firestore") from None


@router.get("/radar", response_model=RadarPage)
def price_radar(
    user: CurrentUser,
    store: Store,
    city: Annotated[str, Query(max_length=120)] = "",
    group: Annotated[str, Query(max_length=300)] = "",
) -> RadarPage:
    try:
        return radar(store, city=city, group=group)
    except GoogleAPIError:
        raise IntegrationUnavailable("MarketLens Firestore") from None


@router.get("/stats", response_model=StatsPage)
def statistics(user: CurrentUser, store: Store) -> StatsPage:
    try:
        items, truncated = store.get_stats()
    except GoogleAPIError:
        raise IntegrationUnavailable("MarketLens Firestore") from None
    return StatsPage(items=items, truncated=truncated)


@router.post("/listings/{listing_id}/explanation", response_model=ExplanationResponse)
def explanation(
    listing_id: ListingId,
    user: CurrentUser,
    store: Store,
    request: Request,
) -> ExplanationResponse:
    settings = request.app.state.settings

    def reserve() -> bool:
        try:
            return store.reserve_explanation(
                user.uid,
                datetime.now(UTC).date(),
                per_user=settings.ai_daily_user_limit,
                global_limit=settings.ai_daily_global_limit,
            )
        except GoogleAPIError:
            return False

    return explain(listing_item(store, listing_id), settings, reserve=reserve)
