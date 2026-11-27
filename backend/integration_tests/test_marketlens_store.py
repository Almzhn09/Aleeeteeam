from datetime import UTC, datetime, timedelta

from app.marketlens.analytics import ALGORITHM_VERSION
from app.marketlens.contracts import AnalysisResult, Listing, MarketStats
from app.marketlens.refresh_analytics import refresh_analytics
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
    history = store.price_history(row.id, 2)
    assert not history.truncated
    assert [(item.scraped_at, item.price) for item in history.items] == [
        (latest.scraped_at, 80000),
        (row.scraped_at, 85000),
    ]
    assert store.price_history(row.id, 1).truncated

    result = AnalysisResult(
        listing_id=latest.id,
        listing_scraped_at=latest.scraped_at,
        computed_at=latest.scraped_at,
        algorithm_version=ALGORITHM_VERSION,
        market_price=100000,
        sample_size=12,
    )
    assert store.save_analysis(
        result.model_copy(
            update={
                "algorithm_version": "v1",
                "computed_at": scraped_at,
            }
        )
    )
    assert store.with_analysis([latest])[0].analysis is None
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


def test_refresh_publishes_comparison_and_histogram_for_real_catalog(db):
    store = MarketStore(db)
    scraped_at = datetime(2026, 11, 27, tzinfo=UTC)
    rows = [
        Listing(
            id=f"olx:{index}",
            external_id=str(index),
            source="olx",
            dataset="real",
            url=f"https://www.olx.kz/example/{index}",
            title="iPhone 13 128 GB",
            category="electronics",
            subcategory="phones",
            price=price,
            currency="KZT",
            scraped_at=scraped_at,
        )
        for index, price in enumerate([50000, 100000, 100000, 100000, 100000, 100000])
    ]
    for row in rows:
        assert store.save_listing(row)

    counts = refresh_analytics(store)

    assert counts["scannedCount"] == counts["savedResults"] == 6
    assert counts["savedGroups"] > 0
    result = store.with_analysis(rows[:1])[0].analysis
    assert result is not None
    assert result.market_price == 100000
    assert "price_far_below_market" in {reason.code for reason in result.risk_reasons}
    groups, truncated = store.get_stats()
    assert not truncated
    assert all(sum(bin.count for bin in group.histogram) == group.sample_size for group in groups)


def test_explanation_budget_is_isolated_per_user_and_day(db):
    store = MarketStore(db)
    day = datetime(2026, 11, 27, tzinfo=UTC).date()
    limits = {"per_user": 1, "global_limit": 2}
    assert store.reserve_explanation("analyst/one", day, **limits)
    assert not store.reserve_explanation("analyst/one", day, **limits)
    assert store.reserve_explanation("analyst-two", day, **limits)
    assert not store.reserve_explanation("analyst-three", day, **limits)
    assert store.reserve_explanation("analyst/one", day + timedelta(days=1), **limits)


def test_dashboard_stats_publish_as_one_generation(db):
    store = MarketStore(db)
    now = datetime(2026, 11, 27, tzinfo=UTC)
    original = MarketStats(
        dataset="real",
        computed_at=now,
        comparable_group="previous-group",
        category="electronics",
        currency="KZT",
        sample_size=1,
    )
    updated_at = now + timedelta(days=1)
    current = original.model_copy(
        update={"comparable_group": "latest-group", "computed_at": updated_at}
    )

    assert store.publish_stats([original], now) == 1
    assert store.publish_stats([current], updated_at) == 1
    assert store.publish_stats([original], now) == 0
    assert store.get_stats() == ([current], False)
    assert store.publish_stats([], updated_at + timedelta(days=1)) == 0
    assert store.get_stats() == ([], False)


def test_catalog_scan_includes_listings_past_the_previous_thousand_record_cap(db):
    store = MarketStore(db)
    raw = Listing(
        id="olx:test-0000",
        external_id="test-0000",
        source="olx",
        dataset="real",
        url="https://www.olx.kz/example",
        title="Объявление для проверки каталога",
        category="electronics",
        scraped_at=datetime(2026, 11, 27, tzinfo=UTC),
    ).model_dump(mode="json", by_alias=True)

    for start, stop in ((0, 400), (400, 800), (800, 1001)):
        batch = db.batch()
        for index in range(start, stop):
            external_id = f"test-{index:04d}"
            listing_id = f"olx:{external_id}"
            document = raw | {"id": listing_id, "externalId": external_id}
            batch.set(db.collection("listings").document(listing_id), document)
        batch.commit()

    rows, limited = store.scan_listings()
    assert len(rows) == 1001
    assert rows[-1].id == "olx:test-1000"
    assert not limited
