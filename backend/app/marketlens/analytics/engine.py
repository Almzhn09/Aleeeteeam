"""Deterministic market evaluation: same listings and computedAt give the same output."""

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from statistics import median

from app.marketlens.analytics import risk
from app.marketlens.analytics.grouping import LEVEL_WEIGHT, LEVELS, OVERVIEW_LEVELS, group_keys
from app.marketlens.contracts import AnalysisResult, Listing, MarketStats, PriceBin

ALGORITHM_VERSION = "v1"
MIN_PEERS = 4
FULL_CONFIDENCE_PEERS = 10
DEAL_FROM = -10.0
MIN_DEAL_CONFIDENCE = 0.3
MAX_BINS = 10


@dataclass(frozen=True)
class MarketAnalysis:
    results: list[AnalysisResult]
    stats: list[MarketStats]


def latest_observations(listings: Iterable[Listing]) -> list[Listing]:
    """Keep the latest observation for each ID, ordered by ID.

    Equal scrapedAt values are resolved by the serialized record so input order
    never changes the result.
    """
    latest: dict[str, Listing] = {}
    for listing in listings:
        current = latest.get(listing.id)
        if current is None or _version(listing) > _version(current):
            latest[listing.id] = listing
    return [latest[key] for key in sorted(latest)]


def _version(listing: Listing) -> tuple[datetime, str]:
    return listing.scraped_at, listing.model_dump_json()


def _market_eligible(listing: Listing) -> bool:
    return (
        listing.price is not None
        and listing.price > 0
        and not any(signal.excludes_from_market for signal in risk.text_signals(listing))
    )


def analyze(listings: Iterable[Listing], *, computed_at: datetime) -> MarketAnalysis:
    """Compute AnalysisResult for every unique listing and MarketStats for used groups.

    Real and fixture listings are evaluated separately and never share a group.
    """
    if computed_at.tzinfo is None:
        raise ValueError("computed_at must be timezone-aware")
    rows = latest_observations(listings)
    keys = {row.id: group_keys(row) for row in rows}
    # (dataset, group) -> sorted prices with listing IDs of eligible observations
    samples: dict[tuple[str, str], list[tuple[float, str]]] = defaultdict(list)
    meta: dict[tuple[str, str], Listing] = {}
    for row in rows:
        if _market_eligible(row):
            for group in keys[row.id].values():
                samples[(row.dataset, group)].append((float(row.price), row.id))
                meta.setdefault((row.dataset, group), row)
    for sample in samples.values():
        sample.sort()

    results = []
    used: set[tuple[str, str]] = set()
    for row in rows:
        result = _evaluate(row, keys[row.id], samples, computed_at)
        results.append(result)
        if result.comparable_group is not None:
            used.add((row.dataset, result.comparable_group))
        # Brand and category groups always get stats so the dashboard has an overview.
        for level in OVERVIEW_LEVELS:
            overview = (row.dataset, keys[row.id].get(level))
            if overview in samples:
                used.add(overview)

    stats = [
        _stats(dataset, group, meta[(dataset, group)], samples[(dataset, group)], computed_at)
        for dataset, group in sorted(used)
    ]
    return MarketAnalysis(results=results, stats=stats)


def _evaluate(row, keys, samples, computed_at) -> AnalysisResult:
    text = risk.text_signals(row)
    group, peers, level = None, [], None
    if row.price is not None and row.price > 0:
        for candidate in LEVELS:
            if candidate not in keys:
                continue
            sample = samples.get((row.dataset, keys[candidate]), [])
            others = [price for price, listing_id in sample if listing_id != row.id]
            if len(others) >= MIN_PEERS:
                group, peers, level = keys[candidate], others, candidate
                break

    market = deviation = savings = deal_score = confidence = None
    if peers:
        market = round(median(peers), 2)
        deviation = round((row.price - market) / market * 100, 2)
        savings = round(market - row.price, 2)
        deal_score = max(0, min(100, round(50 - deviation * 4 / 3)))
        confidence = _confidence(peers, level)

    signals = risk.price_signals(row, deviation) + text
    if market is None and risk.score(signals) == 0:
        risk_score, risk_level = None, "unknown"
    else:
        risk_score = risk.score(signals)
        risk_level = risk.level(risk_score)
    blocked = any(signal.excludes_from_market for signal in text)
    is_deal = (
        deviation is not None
        and risk.FAR_BELOW < deviation <= DEAL_FROM
        and confidence is not None
        and confidence >= MIN_DEAL_CONFIDENCE
        and not blocked
    )
    return AnalysisResult(
        listing_id=row.id,
        listing_scraped_at=row.scraped_at,
        computed_at=computed_at,
        algorithm_version=ALGORITHM_VERSION,
        comparable_group=group,
        market_price=market,
        price_deviation_percent=deviation,
        savings_amount=savings,
        deal_score=deal_score,
        risk_score=risk_score,
        risk_level=risk_level,
        risk_reasons=risk.reasons(signals),
        confidence=confidence,
        sample_size=len(peers),
        is_deal=is_deal,
    )


def _confidence(peers: list[float], level: str) -> float:
    """Sample size × group specificity × price agreement inside the group."""
    size = min(1.0, len(peers) / FULL_CONFIDENCE_PEERS)
    q1, q3 = _quantile(peers, 0.25), _quantile(peers, 0.75)
    spread = (q3 - q1) / (q3 + q1) if q3 + q1 > 0 else 1.0
    agreement = max(0.3, 1 - spread)
    return round(size * LEVEL_WEIGHT[level] * agreement, 2)


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def histogram(prices: list[float], bins: int | None = None) -> list[PriceBin]:
    """Equal-width bins between min and max; the last bin includes the maximum."""
    if not prices:
        return []
    low, high = min(prices), max(prices)
    if low == high:
        return [PriceBin(min=low, max=high, count=len(prices))]
    count = bins or min(MAX_BINS, max(1, math.ceil(math.sqrt(len(prices)))))
    width = (high - low) / count
    counts = [0] * count
    for price in prices:
        counts[min(count - 1, int((price - low) / width))] += 1
    return [
        PriceBin(
            min=round(low + width * index, 2),
            max=high if index == count - 1 else round(low + width * (index + 1), 2),
            count=counts[index],
        )
        for index in range(count)
    ]


def _stats(dataset, group, example: Listing, sample, computed_at) -> MarketStats:
    prices = [price for price, _ in sample]
    return MarketStats(
        dataset=dataset,
        computed_at=computed_at,
        comparable_group=group,
        category=example.category,
        currency=example.currency,
        sample_size=len(prices),
        mean_price=round(sum(prices) / len(prices), 2),
        median_price=round(median(prices), 2),
        min_price=min(prices),
        max_price=max(prices),
        histogram=histogram(prices),
    )
