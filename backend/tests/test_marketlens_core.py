import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies import get_runtime
from app.marketlens.api import market_store
from app.marketlens.contracts import (
    AnalysisResult,
    Listing,
    ListingItem,
    PriceHistory,
    PriceObservation,
)
from app.marketlens.explanation import explain
from app.marketlens.main import create_marketlens_app
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore
from app.models.auth import Principal

WHEN = datetime(2026, 11, 27, tzinfo=UTC)
HEADERS = {"Authorization": "Bearer test-token"}


def listing(key="42", **changes):
    payload = {
        "id": f"olx:{key}",
        "external_id": key,
        "source": "olx",
        "dataset": "real",
        "url": "https://www.olx.kz/example",
        "title": "Ноутбук",
        "description": "Cодержимое источника",
        "category": "electronics",
        "city": "Алматы",
        "price": 85000,
        "currency": "KZT",
        "scraped_at": WHEN,
    }
    return Listing(**(payload | changes))


def result_for(row, **changes):
    payload = {
        "listing_id": row.id,
        "listing_scraped_at": row.scraped_at,
        "computed_at": WHEN,
        "algorithm_version": "v1",
        "market_price": 100000,
        "price_deviation_percent": -15,
        "sample_size": 12,
        "risk_level": "medium",
        "is_deal": True,
    }
    return AnalysisResult(**(payload | changes))


class Identity:
    def verify_token(self, token):
        assert token == "test-token"
        return Principal(uid="user", role="analyst")


class Store:
    def __init__(self):
        self.rows = [
            listing(subcategory="phones", images=["https://images.example.test/phone.jpg"]),
            listing("43", city="Астана", price=10000, subcategory="laptops"),
        ]

    def iter_listings(self):
        return iter(self.rows)

    def get_listing(self, listing_id):
        return next((row for row in self.rows if row.id == listing_id), None)

    def with_analysis(self, rows):
        return [
            ListingItem(listing=row, analysis=result_for(row) if row.id == "olx:42" else None)
            for row in rows
        ]

    def price_history(self, listing_id, limit):
        assert listing_id == "olx:42" and limit == 1
        return PriceHistory(
            items=[PriceObservation(scraped_at=WHEN, price=85000, currency="KZT")],
            truncated=True,
        )

    def price_snapshots(self, listing_ids):
        return [
            (row.id, PriceObservation(scraped_at=row.scraped_at, price=row.price, currency="KZT"))
            for row in self.rows
            if row.id in listing_ids
        ]

    def get_stats(self):
        return [], False


def test_routes_authorize_filter_and_explain():
    application = create_marketlens_app(MarketLensSettings(_env_file=None))
    application.dependency_overrides[get_runtime] = Identity
    application.dependency_overrides[market_store] = Store
    with TestClient(application) as client:
        assert client.get("/api/v1/market/listings").status_code == 401
        assert client.get("/api/v1/complexes", headers=HEADERS).status_code == 404
        assert client.get("/api/v1/me", headers=HEADERS).json()["uid"] == "user"
        page = client.get(
            "/api/v1/market/listings",
            params={"limit": 1},
            headers=HEADERS,
        ).json()
        assert page["nextOffset"] == 1
        assert page["total"] == 2
        assert page["subcategoryCounts"] == {"phones": 1, "laptops": 1}
        city = client.get("/api/v1/market/listings", params={"city": "Алматы"}, headers=HEADERS)
        assert city.json()["total"] == 1
        assert city.json()["subcategoryCounts"] == {"phones": 1}
        assert city.json()["subcategoryPhotos"] == {
            "phones": "https://images.example.test/phone.jpg"
        }
        assert page["items"][0]["listing"]["externalId"] == "42"
        laptop_page = client.get("/api/v1/market/listings?subcategory=laptops", headers=HEADERS)
        assert [item["listing"]["id"] for item in laptop_page.json()["items"]] == ["olx:43"]
        cheap = client.get("/api/v1/market/listings?sort=price_asc&limit=1", headers=HEADERS)
        assert cheap.json()["items"][0]["listing"]["externalId"] == "43"
        expensive = client.get("/api/v1/market/listings?sort=price_desc&limit=1", headers=HEADERS)
        assert expensive.json()["items"][0]["listing"]["externalId"] == "42"
        history = client.get("/api/v1/market/listings/olx:42/history?limit=1", headers=HEADERS)
        assert history.json() == {
            "items": [{"scrapedAt": "2026-11-27T00:00:00Z", "price": 85000, "currency": "KZT"}],
            "truncated": True,
        }
        assert client.get("/api/v1/market/listings/olx:42/history?limit=1").status_code == 401
        assert (
            client.get("/api/v1/market/listings/olx:missing/history", headers=HEADERS).status_code
            == 404
        )
        for view in ("deals", "risk"):
            response = client.get(
                "/api/v1/market/listings",
                params={"view": view, "q": "НОУТ", "city": "алматы", "minPrice": 85000},
                headers=HEADERS,
            )
            assert response.status_code == 200
            assert [item["listing"]["id"] for item in response.json()["items"]] == ["olx:42"]
        invalid = client.get("/api/v1/market/listings?minPrice=100&maxPrice=1", headers=HEADERS)
        assert invalid.status_code == 422
        assert client.get("/api/v1/market/listings/olx:missing", headers=HEADERS).status_code == 404
        assert (
            client.get("/api/v1/market/listings/olx:42", headers=HEADERS).json()["analysis"][
                "marketPrice"
            ]
            == 100000
        )
        assert client.get("/api/v1/market/stats", headers=HEADERS).json() == {
            "items": [],
            "truncated": False,
        }
        explanation = client.post("/api/v1/market/listings/olx:42/explanation", headers=HEADERS)
        assert explanation.json()["provider"] == "local"


def test_source_validation_and_isolated_settings(monkeypatch):
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "saq-qurylys")
    assert MarketLensSettings(_env_file=None).firebase_project_id == "demo-marketlens-local"
    assert (
        MarketLensSettings(_env_file=None, firebase_project_id="hackos20").firebase_project_id
        == "hackos20"
    )
    with pytest.raises(ValidationError, match="dedicated MarketLens"):
        MarketLensSettings(_env_file=None, firebase_project_id="saq-qurylys")
    with pytest.raises(ValidationError, match="belong to the source"):
        listing(url="https://olx.kz.example.org/")
    with pytest.raises(ValidationError, match="fixture- prefix"):
        listing("fixture-42")


def test_stale_analysis_is_excluded():
    row = listing(scraped_at=datetime(2026, 11, 28, tzinfo=UTC))
    stale = result_for(row, listing_scraped_at=WHEN)

    class Snapshot:
        id = row.id
        exists = True

        def to_dict(self):
            return stale.model_dump()

    class Collection:
        def document(self, key):
            return key

    class DB:
        def collection(self, name):
            assert name == "analysisResults"
            return Collection()

        def get_all(self, refs):
            assert refs == [row.id]
            return [Snapshot()]

    assert MarketStore(DB()).with_analysis([row])[0].analysis is None


def test_gemini_uses_only_metrics_and_falls_back_on_timeout():
    row = listing(description="UNTRUSTED PROMPT", title="UNTRUSTED TITLE")
    item = ListingItem(listing=row, analysis=result_for(row))
    settings = MarketLensSettings(
        _env_file=None, gemini_model="example-model", gemini_api_key="test-key"
    )

    def success(request, summary="Обзор"):
        body = json.loads(request.content)
        assert "UNTRUSTED" not in request.content.decode()
        assert json.loads(body["contents"][0]["parts"][0]["text"])["marketPrice"] == 100000
        output = {
            "summary": summary,
            "insights": [],
            "recommendations": [],
            "limitations": ["Цены объявлений"],
        }
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(output)}]},
                    }
                ]
            },
        )

    def timeout(request):
        raise httpx.ReadTimeout("Time limit", request=request)

    def unexpected_provider(request):
        pytest.fail("Quota rejection must skip the Gemini request")

    limited = explain(
        item, settings, reserve=lambda: False, transport=httpx.MockTransport(unexpected_provider)
    )
    assert limited.provider == "local"
    generated = explain(item, settings, transport=httpx.MockTransport(success))
    assert generated.provider == "gemini"
    assert any("Признаки риска требуют проверки" in limit for limit in generated.limitations)
    invented = httpx.MockTransport(lambda request: success(request, "Цена 1 000 000 тенге"))
    assert explain(item, settings, transport=invented).provider == "local"
    assert explain(item, settings, transport=httpx.MockTransport(timeout)).provider == "local"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"candidates": []}))
    assert explain(item, settings, transport=transport).provider == "local"


def test_emulator_requires_both_loopback_services_and_demo_project(monkeypatch):
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9199")
    demo = MarketLensSettings(_env_file=None, firebase_enabled=True)

    with pytest.raises(ValueError, match="Both Firebase emulators"):
        create_marketlens_app(demo)
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "example.org:8188")
    with pytest.raises(ValueError, match="IPv4 loopback"):
        create_marketlens_app(demo)

    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8188")
    with pytest.raises(ValueError, match="demo-marketlens- project"):
        create_marketlens_app(
            MarketLensSettings(_env_file=None, firebase_project_id="marketlens-dev")
        )
    with pytest.raises(ValueError, match="service account"):
        create_marketlens_app(demo.model_copy(update={"firebase_credentials_path": "key.json"}))
    assert create_marketlens_app(demo).state.firebase.settings is demo


@pytest.mark.parametrize("source_failure", ["unavailable", "empty", "second_category"])
def test_olx_update_does_not_open_firestore_on_collection_failure(
    monkeypatch, capsys, source_failure
):
    from app.marketlens import update_olx

    argv = ["update_olx", "--authorized"]
    if source_failure == "second_category":
        argv += ["--category", "phones", "--category", "laptops"]
    monkeypatch.setattr("sys.argv", argv)
    monkeypatch.setenv("MARKETLENS_FIREBASE_ENABLED", "true")

    class Runtime:
        def db(self):
            pytest.fail("Firestore must remain unopened when collection failed")

    def collect(self, request):
        if source_failure == "empty":
            return []
        if source_failure == "second_category" and request.category == "phones":
            return [listing()]
        raise update_olx.OLXSourceError("HTTP 403")

    monkeypatch.setattr(update_olx, "marketlens_runtime", lambda settings: Runtime())
    monkeypatch.setattr(update_olx.OLXParser, "collect", collect)

    with pytest.raises(SystemExit) as failure:
        update_olx.main()
    assert failure.value.code == 1
    out = capsys.readouterr()
    assert not out.out
    assert (
        "403" in out.err if source_failure != "empty" else "catalog was left unchanged" in out.err
    )


def test_default_views_rank_scores_and_allow_explicit_price_sort():
    class RankedStore(Store):
        def with_analysis(self, rows):
            return [
                ListingItem(
                    listing=row,
                    analysis=result_for(
                        row,
                        risk_score=70 if row.id == "olx:43" else 40,
                        deal_score=70 if row.id == "olx:43" else 50,
                    ),
                )
                for row in rows
            ]

    application = create_marketlens_app(MarketLensSettings(_env_file=None))
    application.dependency_overrides[get_runtime] = Identity
    application.dependency_overrides[market_store] = RankedStore
    with TestClient(application) as client:
        path = "/api/v1/market/listings"
        for view in ("deals", "risk"):
            top = client.get(path, params={"view": view, "limit": 1}, headers=HEADERS).json()
            assert top["items"][0]["listing"]["id"] == "olx:43"
            expensive = client.get(
                path, params={"view": view, "limit": 1, "sort": "price_desc"}, headers=HEADERS
            ).json()
            assert expensive["items"][0]["listing"]["id"] == "olx:42"


def test_openai_explanation_is_grounded_and_preserves_local_fallback():
    row = listing(title="PRIVATE TITLE", description="PRIVATE DESCRIPTION")
    item = ListingItem(listing=row, analysis=result_for(row))
    settings = MarketLensSettings(
        _env_file=None,
        openai_model="example-model",
        openai_api_key="test-openai-key",
        gemini_model="example-gemini",
        gemini_api_key="test-gemini-key",
    )

    def respond(request, status=200, finish="stop", summary="Обзор"):
        assert str(request.url) == "https://api.openai.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-openai-key"
        body = json.loads(request.content)
        assert body["model"] == "example-model"
        assert body["store"] is False
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "PRIVATE" not in request.content.decode()
        assert row.id not in request.content.decode()
        assert json.loads(body["messages"][1]["content"])["marketPrice"] == 100000
        content = {
            "summary": summary,
            "insights": [],
            "recommendations": [],
            "limitations": ["Цены объявлений"],
        }
        return httpx.Response(
            status,
            json={
                "choices": [{"finish_reason": finish, "message": {"content": json.dumps(content)}}]
            },
        )

    def unexpected(request):
        pytest.fail("A denied quota must prevent the provider request")

    assert explain(item, settings, transport=httpx.MockTransport(respond)).provider == "openai"
    for override in ({"status": 429}, {"finish": "length"}, {"summary": "Цена 123 тенге"}):
        mock = httpx.MockTransport(lambda request, options=override: respond(request, **options))
        assert explain(item, settings, transport=mock).provider == "local"
    result = explain(
        item, settings, reserve=lambda: False, transport=httpx.MockTransport(unexpected)
    )
    assert result.provider == "local"


def test_radar_filters_city_and_reports_thin_groups_and_real_price_samples():
    store = Store()
    store.rows = [
        listing(
            str(index),
            title=f"iPhone 13 {128 if index <= 3 else 256} GB",
            subcategory="phones",
            price=10000 * index,
        )
        for index in range(1, 6)
    ] + [
        listing("11", title="iPhone 13 128 GB", subcategory="phones", city="Астана", price=100),
        listing("12", title="Чехол iPhone 13 128 GB", subcategory="phones", price=200),
        listing("13", title="iPhone 14 128 GB", subcategory="phones", price=35000),
    ]
    app = create_marketlens_app(MarketLensSettings(_env_file=None))
    app.dependency_overrides[get_runtime] = Identity
    app.dependency_overrides[market_store] = lambda: store
    with TestClient(app) as client:
        url = "/api/v1/market/radar"
        assert client.get(url).status_code == 401
        result = client.get(url, params={"city": "алматы"}, headers=HEADERS).json()
        groups = {group["key"]: group["sampleSize"] for group in result["groups"]}
        assert sorted(groups.values(), reverse=True) == [5, 3, 2, 1, 1]
        assert groups["electronics/phones:apple-iphone-13:any:KZT"] == 5
        assert groups["electronics/phones:apple-iphone-13:128gb:any:KZT"] == 3
        assert result["sample"]["prices"] == [10000, 20000, 30000, 40000, 50000]
        assert result["sample"]["medianPrice"] == 30000
        assert sum(bin_["count"] for bin_ in result["sample"]["histogram"]) == 5
        thin = client.get(
            url,
            params={"city": "Алматы", "group": "electronics/phones:apple-iphone-14:any:KZT"},
            headers=HEADERS,
        ).json()
        assert thin["sample"]["prices"] == [35000]
        assert thin["sample"]["medianPrice"] is None


def test_catalog_offset_above_the_previous_limit():
    store = Store()
    store.rows = [listing(str(index)) for index in range(1010)]
    app = create_marketlens_app(MarketLensSettings(_env_file=None))
    app.dependency_overrides[get_runtime] = Identity
    app.dependency_overrides[market_store] = lambda: store
    with TestClient(app) as client:
        page = client.get(
            "/api/v1/market/listings", params={"offset": 1008, "limit": 1}, headers=HEADERS
        )
    assert page.status_code == 200
    assert page.json()["items"][0]["listing"]["id"] == "olx:1008"
    assert page.json()["nextOffset"] == 1009


def test_price_trend_keeps_one_latest_price_per_listing_and_day():
    from datetime import timedelta

    from app.marketlens.radar import price_trend

    day = datetime(2026, 11, 25, 6, tzinfo=UTC)
    observations = [
        ("a", day, 100.0),
        ("a", day + timedelta(hours=3), 120.0),  # same day, later: replaces 100
        ("b", day, 200.0),
        ("a", day + timedelta(days=1), 90.0),
        ("b", day + timedelta(days=1), 0.0),  # symbolic price is ignored
        ("c", day - timedelta(days=200), 50.0),  # older than 90 days before the last day
    ]

    class Snapshots:
        def price_snapshots(self, listing_ids):
            assert listing_ids == ["a", "b", "c"]
            return [
                (key, PriceObservation(scraped_at=when, price=price, currency="KZT"))
                for key, when, price in observations
            ]

    trend = price_trend(Snapshots(), ["a", "b", "c"])
    assert [(point.day.isoformat(), point.median_price, point.count) for point in trend] == [
        ("2026-11-25", 160.0, 2),
        ("2026-11-26", 90.0, 1),
    ]
