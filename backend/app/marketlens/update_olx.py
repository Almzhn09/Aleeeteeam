"""Collect one authorized OLX category page, import it, and refresh MarketLens."""

import argparse
import json

import httpx
from google.api_core.exceptions import GoogleAPIError
from pydantic import ValidationError

from app.core.errors import AppError
from app.marketlens.contracts import CollectionRequest
from app.marketlens.import_listings import import_rows, validate_import_rows
from app.marketlens.parsers.olx import OLX_SECTIONS, OLXParser, OLXSourceError
from app.marketlens.refresh_analytics import refresh_analytics
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized", action="store_true", help="Confirm OLX permits collection")
    parser.add_argument("--limit", type=int, default=30, help="Maximum unique listings")
    parser.add_argument(
        "--category", choices=OLX_SECTIONS, default="phones", help="OLX category to collect"
    )
    args = parser.parse_args()
    if not args.authorized:
        parser.error("--authorized is required to collect from OLX")
    try:
        request = CollectionRequest(category=args.category, limit=args.limit)
    except ValidationError:
        parser.error("--limit must be between 1 and 1000")

    settings = MarketLensSettings()
    if not settings.firebase_enabled:
        parser.error("Enable the dedicated MarketLens Firebase project before updating")
    runtime = marketlens_runtime(settings)
    try:
        with httpx.Client() as client:
            rows = OLXParser(client, authorized=True).collect(request)
        if not rows:
            parser.exit(1, "OLX returned no listings. The catalog was left unchanged.\n")
        validate_import_rows(rows)
    except (OLXSourceError, ValueError) as error:
        parser.exit(1, f"OLX collection failed: {error}\n")

    stage = "Import"
    try:
        store = MarketStore(runtime.db())
        imported = import_rows(store, rows)
        stage = "Analytics refresh"
        analytics = refresh_analytics(store)
    except AppError as error:
        parser.exit(1, f"{stage} failed: {error.message}\n")
    except GoogleAPIError:
        parser.exit(1, f"{stage} failed. Check Firestore access and retry the failed step.\n")
    finally:
        runtime.close()
    print(json.dumps({"import": imported, "analytics": analytics}))


if __name__ == "__main__":
    main()
