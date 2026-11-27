from datetime import UTC, datetime, timedelta

from app.marketlens.contracts import AnalysisResult, Listing, MarketStats
from app.marketlens.store import MarketStore


def test_market_store_keeps_snapshots_and_matches_current_analysis(db):
    store = MarketStore(db)
    scraped_at = datetime(2026, 11, 27, tzinfo=UTC)
    row = Listing(
        id="olx:42",
        external_id="42",
        source="olx",
        dataset="real",
        url="https://www.olx.kz/example",
        title="Ноутбук",
        category="electronics",
        price=85000,
        currency="KZT",
        scraped_at=scraped_at,
    )
    latest = row.model_copy(update={"scraped_at": scraped_at + timedelta(days=1), "price": 80000})
    fixture = row.model_copy(
        update={
            "id": "olx:fixture-42",
            "external_id": "fixture-42",
            "dataset": "fixture",
        }
    )

    assert store.save_listing(latest)
    assert store.save_listing(row)
    assert not store.save_listing(latest)
    assert store.save_listing(fixture)
    assert len(list(db.collection("listingSnapshots").stream())) == 3
    assert store.scan_listings() == ([latest], False)
    assert store.get_listing(fixture.id) is None

    result = AnalysisResult(
        listing_id=latest.id,
        listing_scraped_at=latest.scraped_at,
        computed_at=latest.scraped_at,
        algorithm_version="test-v1",
        market_price=100000,
        sample_size=12,
    )
    assert store.save_analysis(result)
    assert not store.save_analysis(result.model_copy(update={"listing_scraped_at": scraped_at}))
    assert store.with_analysis([latest])[0].analysis == result
    newer = latest.model_copy(update={"scraped_at": latest.scraped_at + timedelta(days=1)})
    assert store.save_listing(newer)
    assert store.with_analysis([newer])[0].analysis is None

    stats = MarketStats(
        dataset="real",
        computed_at=scraped_at,
        comparable_group="test",
        category="electronics",
        currency="KZT",
        sample_size=12,
    )
    assert store.save_stats(stats)
    assert not store.save_stats(stats)
    assert store.save_stats(stats.model_copy(update={"dataset": "fixture"}))
    assert store.get_stats() == ([stats], False)
