import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.dependencies import get_runtime
from app.marketlens.api import market_store
from app.marketlens.contracts import AnalysisResult, Listing, ListingItem
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
        self.rows = [listing(), listing("43", city="Астана", price=10000)]

    def scan_listings(self):
        return self.rows, False

    def get_listing(self, listing_id):
        return next((row for row in self.rows if row.id == listing_id), None)

    def with_analysis(self, rows):
        return [
            ListingItem(listing=row, analysis=result_for(row) if row.id == "olx:42" else None)
            for row in rows
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
        assert page["items"][0]["listing"]["externalId"] == "42"
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

    def success(request):
        body = json.loads(request.content)
        assert "UNTRUSTED" not in request.content.decode()
        assert json.loads(body["contents"][0]["parts"][0]["text"])["marketPrice"] == 100000
        output = {
            "summary": "Обзор",
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

    assert explain(item, settings, transport=httpx.MockTransport(success)).provider == "gemini"
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


@pytest.mark.parametrize("source_failure", ["unavailable", "empty"])
def test_olx_update_does_not_open_firestore_on_collection_failure(
    monkeypatch, capsys, source_failure
):
    from app.marketlens import update_olx

    monkeypatch.setattr("sys.argv", ["update_olx", "--authorized"])
    monkeypatch.setenv("MARKETLENS_FIREBASE_ENABLED", "true")

    class Runtime:
        def db(self):
            pytest.fail("Firestore must remain unopened when collection failed")

    def collect(self, request):
        if source_failure == "unavailable":
            raise update_olx.OLXSourceError("HTTP 403")
        return []

    monkeypatch.setattr(update_olx, "marketlens_runtime", lambda settings: Runtime())
    monkeypatch.setattr(update_olx.OLXParser, "collect", collect)

    with pytest.raises(SystemExit) as failure:
        update_olx.main()
    assert failure.value.code == 1
    out = capsys.readouterr()
    assert not out.out
    assert (
        "403" in out.err
        if source_failure == "unavailable"
        else "catalog was left unchanged" in out.err
    )
