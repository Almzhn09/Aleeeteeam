"""Exercise the actual Firebase Auth and Firestore adapters on loopback."""

import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from firebase_admin import auth

from app.marketlens.contracts import Listing
from app.marketlens.main import create_marketlens_app
from app.marketlens.refresh_analytics import refresh_analytics
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def test_marketlens_auth_and_catalog_use_the_same_emulator_project():
    assert os.environ.get("SAQ_FIRESTORE_INTEGRATION") == "1"
    assert os.environ.get("FIREBASE_AUTH_EMULATOR_HOST")
    project = "demo-marketlens-qa"
    application = create_marketlens_app(
        MarketLensSettings(_env_file=None, firebase_enabled=True, firebase_project_id=project)
    )
    runtime = application.state.firebase
    row = Listing(
        id="olx:auth-flow",
        external_id="auth-flow",
        source="olx",
        dataset="real",
        url="https://www.olx.kz/example",
        title="Integration test phone",
        category="electronics",
        subcategory="phones",
        currency="KZT",
        price=85000,
        scraped_at=datetime.now(UTC),
    )
    email = "analyst@example.test"
    password = uuid4().hex
    path = "/api/v1/market/listings"
    auth_host = os.environ["FIREBASE_AUTH_EMULATOR_HOST"]

    with TestClient(application) as client, httpx.Client(trust_env=False) as identity:
        user = auth.create_user(email=email, password=password, app=runtime.app())
        store = MarketStore(runtime.db())
        assert store.save_listing(row)
        assert refresh_analytics(store)["savedResults"] == 1

        def sign_in():
            response = identity.post(
                f"http://{auth_host}/identitytoolkit.googleapis.com/v1/"
                "accounts:signInWithPassword?key=local-demo",
                json={"email": email, "password": password, "returnSecureToken": True},
            )
            token = response.raise_for_status().json()["idToken"]
            return {"Authorization": f"Bearer {token}"}

        assert client.get(path).status_code == 401
        assert client.get(path, headers=sign_in()).status_code == 403
        auth.set_custom_user_claims(user.uid, {"role": "analyst"}, app=runtime.app())
        headers = sign_in()
        response = client.get(path, headers=headers)
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert item["listing"]["price"] == 85000
        assert item["analysis"]["listingId"] == row.id
        assert client.get("/api/v1/me", headers=headers).json()["uid"] == user.uid
        assert (
            client.get(f"{path}/{row.id}/history", headers=headers).json()["items"][0]["price"]
            == 85000
        )

        db = runtime.db()
        collection = db.collection("listings")
        serialized = row.model_dump(mode="json", by_alias=True)
        for start in range(0, 2010, 400):
            batch = db.batch()
            for index in range(start, min(start + 400, 2010)):
                external_id = f"bulk-{index:04d}"
                listing_id = f"olx:{external_id}"
                batch.set(
                    collection.document(listing_id),
                    serialized
                    | {
                        "id": listing_id,
                        "externalId": external_id,
                        "title": "Редкая модель за пределами тысячи"
                        if index == 2009
                        else "Телефон",
                    },
                )
            batch.commit()
        extended = client.get(path, params={"offset": 2005, "limit": 100}, headers=headers).json()
        assert extended["scannedCount"] == 2011
        assert [item["listing"]["id"] for item in extended["items"]][-1] == "olx:bulk-2009"
        search = client.get(path, params={"q": "редкая модель"}, headers=headers).json()
        assert [item["listing"]["id"] for item in search["items"]] == ["olx:bulk-2009"]
