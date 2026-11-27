"""Contract tests for MarketLens analytics on a fixed set of fixture- listings."""

import json
import random
import sys
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import TypeAdapter

from app.marketlens.analytics import ALGORITHM_VERSION, analyze, analyze_store, histogram
from app.marketlens.analytics.__main__ import main as analyze_cli
from app.marketlens.analytics.grouping import group_keys, product_key
from app.marketlens.contracts import AnalysisResult, Listing, MarketStats

SCRAPED = datetime(2026, 11, 27, 9, tzinfo=UTC)
COMPUTED = datetime(2026, 11, 27, 9, 5, tzinfo=UTC)
GROUP_13 = "electronics/phones:apple-iphone-13:any:KZT"


def phone(key, title, price, currency="KZT", dataset="fixture", **changes):
    external = f"fixture-{key}" if dataset == "fixture" else f"real-{key}"
    payload = {
        "id": f"olx:{external}",
        "external_id": external,
        "source": "olx",
        "dataset": dataset,
        "url": f"https://www.olx.kz/d/obyavlenie/{external}.html",
        "title": title,
        "category": "electronics",
        "subcategory": "phones",
        "price": price,
        "currency": currency if price is not None else None,
        "scraped_at": SCRAPED,
    }
    return Listing(**(payload | changes))


def iphone_market(prices=(300000, 310000, 320000, 330000, 340000, 350000), dataset="fixture"):
    return [
        phone(f"i{index}", f"iPhone 13 {index} отличное состояние", price, dataset=dataset)
        for index, price in enumerate(prices)
    ]


def by_id(analysis):
    return {result.listing_id: result for result in analysis.results}


@pytest.mark.parametrize(
    ("title", "model", "storage"),
    [
        ("Apple iPhone 13 Pro Max 256GB", "apple-iphone-13-promax", "256gb"),
        ("Продам айфон 11 128 гб", "apple-iphone-11", "128gb"),
        ("iPhone SE (2020) 64gb", "apple-iphone-se", "64gb"),
        ("Samsung Galaxy S23+ 8/256", "samsung-galaxy-s23-plus", "256gb"),
        ("Самсунг Галакси А54", "samsung-galaxy-a54", None),
        ("Samsung A54 5G", "samsung-galaxy-a54", None),
        ("Xiaomi Redmi Note 12 Pro 1TB", "xiaomi-redminote12-pro", "1tb"),
        ("Редми ноут 13 про", "xiaomi-redminote13-pro", None),
        ("Айфон 12 про макс 128", "apple-iphone-12-promax", "128gb"),
        ("iPhone XR 64, акб 85%", "apple-iphone-xr", "64gb"),
        ("Samsung Galaxy S24 Ultra 12/512", "samsung-galaxy-s24-ultra", "512gb"),
        ("Poco X6 Pro 5G 12/512", "xiaomi-pocox6-pro", "512gb"),
        ("Redmi 13C 8/256", "xiaomi-redmi13c", "256gb"),
        ("iPhone 14 Pro 2 sim", "apple-iphone-14-pro", None),
        ("Tecno Spark 20 Pro 8/256", "tecno-spark20-pro", "256gb"),
        ("Infinix Hot 40i 128гб", "infinix-hot40i", "128gb"),
        ("Honor X8b 8/128", "honor-x8b", "128gb"),
        ("Huawei P30 Lite", "huawei-p30-lite", None),
        ("Realme C55", "realme-c55", None),
        ("OnePlus 12 Pro", "oneplus-12-pro", None),
        ("Vivo Y36 128 gb", "vivo-y36", "128gb"),
        ("Tecno 128 gb синий", None, "128gb"),
        ("Телефон в хорошем состоянии", None, None),
    ],
)
def test_product_key_reads_model_and_storage_from_title(title, model, storage):
    key = product_key(title)
    assert (key.model, key.storage) == (model, storage)


def test_product_key_falls_back_to_brand():
    assert product_key("Самсунг Галакси А54").brand == "samsung"
    assert product_key("Huawei смартфон").brand == "huawei"
    assert product_key("Кнопочный телефон").brand is None


def test_group_keys_separate_category_condition_and_currency():
    keys = group_keys(phone("a", "iPhone 13 128GB", 300000, currency="USD", condition="Б/у"))
    assert keys == {
        "variant": "electronics/phones:apple-iphone-13:128gb:б-у:USD",
        "model": "electronics/phones:apple-iphone-13:б-у:USD",
        "brand": "electronics/phones:apple:б-у:USD",
        "category": "electronics/phones:all:б-у:USD",
    }


def test_deal_uses_leave_one_out_median_and_contract_formula():
    target = phone("deal", "iPhone 13 срочно", 272000)
    results = by_id(analyze([*iphone_market(), target], computed_at=COMPUTED))
    result = results[target.id]
    assert result.comparable_group == GROUP_13
    assert result.market_price == 325000
    assert result.sample_size == 6
    assert result.price_deviation_percent == pytest.approx(-16.31, abs=0.01)
    assert result.savings_amount == 53000
    assert result.deal_score == 72
    assert result.is_deal
    assert result.algorithm_version == ALGORITHM_VERSION
    assert result.listing_scraped_at == SCRAPED
    assert result.computed_at == COMPUTED
    assert [reason.code for reason in result.risk_reasons] == ["urgency_wording"]
    assert result.risk_level == "low"
    assert 0 < result.confidence <= 1


def test_small_sample_leaves_estimates_empty():
    rows = iphone_market(prices=(300000, 320000, 340000))
    rows += [phone("odd", "Кнопочный телефон", 5000)]
    for result in analyze(rows, computed_at=COMPUTED).results:
        assert result.market_price is None
        assert result.price_deviation_percent is None
        assert result.savings_amount is None
        assert result.deal_score is None
        assert result.confidence is None
        assert result.comparable_group is None
        assert result.sample_size == 0
        assert result.risk_level == "unknown"
        assert result.risk_score is None
        assert not result.is_deal


def test_other_models_are_never_used_as_market_reference():
    # A first OLX page has many models with 1–3 cards; comparing them with other
    # models would create false deals and false price risks.
    rows = iphone_market() + [
        phone("rare", "iPhone 15 Pro 256gb", 90000),
        phone("redmi", "Redmi 13C", 60000),
    ]
    analysis = analyze(rows, computed_at=COMPUTED)
    results = by_id(analysis)
    for key in ("rare", "redmi"):
        result = results[f"olx:fixture-{key}"]
        assert result.market_price is None and result.comparable_group is None
        assert result.risk_reasons == [] and result.risk_level == "unknown"
        assert not result.is_deal
    assert results["olx:fixture-i0"].comparable_group == GROUP_13
    stats = {item.comparable_group: item for item in analysis.stats}
    assert stats["electronics/phones:apple:any:KZT"].sample_size == 7
    assert stats["electronics/phones:xiaomi:any:KZT"].sample_size == 1
    assert stats["electronics/phones:all:any:KZT"].sample_size == 8


def test_outlier_is_a_risk_signal_not_a_deal_and_does_not_move_market():
    outlier = phone("cheap", "iPhone 13", 90000)
    analysis = analyze([*iphone_market(), outlier], computed_at=COMPUTED)
    results = by_id(analysis)
    result = results[outlier.id]
    assert result.price_deviation_percent < -70
    assert not result.is_deal
    assert result.risk_reasons[0].code == "price_far_below_market"
    assert result.risk_level == "medium"
    # Median of peers is robust: a regular listing still compares to ~325k.
    assert results["olx:fixture-i5"].market_price == 315000
    assert results["olx:fixture-i5"].risk_reasons == []
    assert results["olx:fixture-i5"].risk_level == "low"


def test_text_signals_accumulate_to_high_risk_and_exclude_from_market():
    fake = phone("fake", "iPhone 13 копия, только предоплата", 120000)
    analysis = analyze([*iphone_market(), fake], computed_at=COMPUTED)
    result = by_id(analysis)[fake.id]
    codes = {reason.code for reason in result.risk_reasons}
    assert codes == {"price_far_below_market", "replica_mention", "prepayment_request"}
    assert result.risk_level == "high"
    assert result.risk_score == 100
    assert not result.is_deal
    stats = {item.comparable_group: item for item in analysis.stats}
    assert stats[GROUP_13].sample_size == 6
    assert stats[GROUP_13].min_price == 300000


def test_missing_and_zero_prices_are_unknown_not_market_inputs():
    missing = phone("none", "iPhone 13", None)
    zero = phone("zero", "iPhone 13", 0)
    analysis = analyze([*iphone_market(), missing, zero], computed_at=COMPUTED)
    results = by_id(analysis)
    for row, code in ((missing, "missing_price"), (zero, "symbolic_price")):
        result = results[row.id]
        assert result.market_price is None
        assert result.price_deviation_percent is None
        assert result.comparable_group is None
        assert [reason.code for reason in result.risk_reasons] == [code]
    stats = {item.comparable_group: item for item in analysis.stats}
    assert stats[GROUP_13].sample_size == 6
    assert "electronics/phones:all:any:none" not in stats


def test_mixed_currencies_are_never_compared():
    dollars = [phone(f"usd{index}", "iPhone 13", 700 + index * 10, "USD") for index in range(3)]
    analysis = analyze([*iphone_market(), *dollars], computed_at=COMPUTED)
    results = by_id(analysis)
    assert all(results[row.id].market_price is None for row in dollars)
    assert results["olx:fixture-i0"].market_price == 330000
    stats = {(item.currency, item.comparable_group): item for item in analysis.stats}
    assert stats[("KZT", GROUP_13)].sample_size == 6
    assert stats[("USD", "electronics/phones:all:any:USD")].sample_size == 3
    assert ("USD", "electronics/phones:apple-iphone-13:any:USD") not in stats


def test_real_and_fixture_datasets_never_share_groups_or_stats():
    real = iphone_market(prices=(500000,) * 6, dataset="real")
    analysis = analyze([*iphone_market(), *real], computed_at=COMPUTED)
    results = by_id(analysis)
    assert results["olx:fixture-i0"].market_price == 330000
    assert results["olx:real-i0"].market_price == 500000
    pairs = {(item.dataset, item.comparable_group) for item in analysis.stats}
    assert ("fixture", GROUP_13) in pairs and ("real", GROUP_13) in pairs
    real_stats = next(
        s for s in analysis.stats if (s.dataset, s.comparable_group) == ("real", GROUP_13)
    )
    assert real_stats.sample_size == 6 and real_stats.mean_price == 500000


def test_recalculation_is_deterministic_and_keeps_latest_observation():
    rows = [*iphone_market(), phone("deal", "iPhone 13", 272000)]
    newer = phone("deal", "iPhone 13", 330000, scraped_at=SCRAPED + timedelta(hours=1))
    first = analyze([*rows, newer], computed_at=COMPUTED)
    shuffled = [*rows, newer]
    random.Random(7).shuffle(shuffled)
    second = analyze(shuffled + shuffled, computed_at=COMPUTED)
    assert first == second
    result = by_id(first)["olx:fixture-deal"]
    assert result.listing_scraped_at == newer.scraped_at
    assert not result.is_deal
    assert len(first.results) == 7
    assert [r.listing_id for r in first.results] == sorted(r.listing_id for r in first.results)


def test_stats_aggregate_group_and_category_overview():
    analysis = analyze(iphone_market(), computed_at=COMPUTED)
    stats = {item.comparable_group: item for item in analysis.stats}
    assert set(stats) == {
        GROUP_13,
        "electronics/phones:apple:any:KZT",
        "electronics/phones:all:any:KZT",
    }
    group = stats[GROUP_13]
    assert (group.dataset, group.category, group.currency) == ("fixture", "electronics", "KZT")
    assert group.sample_size == 6
    assert group.mean_price == 325000
    assert group.median_price == 325000
    assert (group.min_price, group.max_price) == (300000, 350000)
    assert sum(item.count for item in group.histogram) == 6
    assert group.histogram[0].min == 300000 and group.histogram[-1].max == 350000
    assert group.computed_at == COMPUTED


def test_histogram_edges():
    assert histogram([]) == []
    single = histogram([100, 100, 100])
    assert [(b.min, b.max, b.count) for b in single] == [(100, 100, 3)]
    bins = histogram([0, 10, 20, 30, 40], bins=4)
    assert [b.count for b in bins] == [1, 1, 1, 2]
    assert bins[-1].max == 40


def test_results_round_trip_through_public_contract():
    analysis = analyze([*iphone_market(), phone("none", "iPhone 13", None)], computed_at=COMPUTED)
    for result in analysis.results:
        dumped = result.model_dump(mode="json", by_alias=True)
        assert AnalysisResult.model_validate(dumped) == result
    for item in analysis.stats:
        assert MarketStats.model_validate(item.model_dump(mode="json", by_alias=True)) == item


def test_naive_computed_at_is_rejected():
    with pytest.raises(ValueError):
        analyze(iphone_market(), computed_at=datetime(2026, 11, 27))


def test_cli_prints_both_result_kinds(tmp_path, monkeypatch, capsys):
    source = tmp_path / "listings.json"
    source.write_bytes(TypeAdapter(list[Listing]).dump_json(iphone_market(), by_alias=True))
    monkeypatch.setattr(
        sys, "argv", ["analytics", str(source), "--computed-at", "2026-11-27T09:05:00Z"]
    )
    analyze_cli()
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert json.loads(captured.err) == {
        "listings": 6,
        "withMarketPrice": 6,
        "deals": 0,
        "riskMediumOrHigh": 0,
        "groups": 3,
    }
    assert len(output["results"]) == 6
    assert output["results"][0]["algorithmVersion"] == ALGORITHM_VERSION
    assert output["results"][0]["computedAt"] == "2026-11-27T09:05:00Z"
    assert {item["comparableGroup"] for item in output["stats"]} == {
        GROUP_13,
        "electronics/phones:apple:any:KZT",
        "electronics/phones:all:any:KZT",
    }


def test_analyze_store_saves_results_and_stats_through_public_methods():
    class FakeStore:
        def __init__(self):
            self.results, self.stats = [], []

        def scan_listings(self):
            return iphone_market(dataset="real"), False

        def save_analysis(self, result):
            self.results.append(result)
            return True

        def publish_stats(self, stats, computed_at):
            assert computed_at == COMPUTED
            self.stats.extend(stats)
            return len(stats)

    store = FakeStore()
    summary = analyze_store(store, computed_at=COMPUTED)
    assert summary == {"listings": 6, "scanLimited": False, "savedResults": 6, "savedStats": 3}
    assert all(item.dataset == "real" for item in store.stats)
    assert store.results[0].market_price == 330000
