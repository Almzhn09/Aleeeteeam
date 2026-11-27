"""Group observed prices for the interactive radar."""

from collections import defaultdict
from statistics import median

from app.marketlens.analytics.engine import MIN_PEERS, histogram
from app.marketlens.analytics.grouping import group_keys
from app.marketlens.analytics.risk import text_signals
from app.marketlens.contracts import Listing, ListingItem, MarketModel, PriceBin
from app.marketlens.store import MarketStore


class RadarGroup(MarketModel):
    key: str
    sample_size: int


class RadarSample(MarketModel):
    key: str
    prices: list[float]
    median_price: float | None
    histogram: list[PriceBin]
    offers: list[ListingItem]


class RadarPage(MarketModel):
    groups: list[RadarGroup]
    sample: RadarSample | None
    scan_limited: bool


def radar(store: MarketStore, *, city: str, group: str) -> RadarPage:
    city = city.strip().casefold()
    cohorts: dict[str, list[tuple[float, Listing]]] = defaultdict(list)
    for listing in store.iter_listings():
        price = listing.price
        if (
            (city and city != (listing.city or "").casefold())
            or listing.currency != "KZT"
            or price is None
            or price <= 0
        ):
            continue
        keys = group_keys(listing)
        key = keys.get("variant") or keys.get("model")
        if key and not any(signal.excludes_from_market for signal in text_signals(listing)):
            cohorts[key].append((price, listing))

    ordered = sorted(cohorts, key=lambda key: (-len(cohorts[key]), key))
    groups = [RadarGroup(key=key, sample_size=len(cohorts[key])) for key in ordered]
    sample = None
    selected = group or (ordered[0] if ordered else "")
    if selected in cohorts:
        rows = sorted(cohorts[selected], key=lambda row: (row[0], row[1].id))
        prices = [price for price, _ in rows]
        sample = RadarSample(
            key=selected,
            prices=prices,
            median_price=round(median(prices), 2) if len(prices) > MIN_PEERS else None,
            histogram=histogram(prices),
            offers=store.with_analysis([row for _, row in rows[:24]]),
        )
    return RadarPage(groups=groups, sample=sample, scan_limited=False)
