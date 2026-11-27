"""Group observed prices for the interactive radar."""

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median

from app.marketlens.analytics.engine import MIN_PEERS, histogram
from app.marketlens.analytics.grouping import group_keys
from app.marketlens.analytics.risk import text_signals
from app.marketlens.contracts import Listing, ListingItem, MarketModel, PriceBin
from app.marketlens.store import MarketStore

ALMATY = timezone(timedelta(hours=5))  # Kazakhstan uses UTC+5 all year.


class RadarGroup(MarketModel):
    key: str
    sample_size: int


class TrendPoint(MarketModel):
    day: date
    median_price: float
    count: int


class RadarSample(MarketModel):
    key: str
    prices: list[float]
    median_price: float | None
    histogram: list[PriceBin]
    offers: list[ListingItem]
    trend: list[TrendPoint] = []


TREND_DAYS = 90


def price_trend(store: MarketStore, listing_ids: list[str]) -> list[TrendPoint]:
    """Daily median of the cohort's observed prices (Kazakhstan days, last 90 days).

    One price per listing and day: the latest observation of that day.
    """
    latest: dict[tuple[date, str], tuple[datetime, float]] = {}
    for listing_id, row in store.price_snapshots(listing_ids):
        if row.currency != "KZT" or row.price is None or row.price <= 0:
            continue
        day = row.scraped_at.astimezone(ALMATY).date()
        seen = latest.get((day, listing_id))
        if seen is None or seen[0] < row.scraped_at:
            latest[(day, listing_id)] = (row.scraped_at, row.price)
    by_day: dict[date, list[float]] = defaultdict(list)
    for (day, _), (_, price) in latest.items():
        by_day[day].append(price)
    if not by_day:
        return []
    since = max(by_day) - timedelta(days=TREND_DAYS - 1)
    return [
        TrendPoint(day=day, median_price=round(median(prices), 2), count=len(prices))
        for day, prices in sorted(by_day.items())
        if day >= since
    ]


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
        model = keys.get("model")
        if not model or any(signal.excludes_from_market for signal in text_signals(listing)):
            continue
        cohorts[model].append((price, listing))
        device_variant = keys.get("variant")
        if device_variant:
            cohorts[device_variant].append((price, listing))

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
            trend=price_trend(store, [row.id for _, row in rows]),
        )
    return RadarPage(groups=groups, sample=sample, scan_limited=False)
