"""Collect an authorized OLX category, import it, and refresh MarketLens."""

import argparse
import json

import httpx
from google.api_core.exceptions import GoogleAPIError
from pydantic import ValidationError

from app.core.errors import AppError
from app.marketlens.contracts import CollectionRequest
from app.marketlens.import_listings import import_rows, validate_import_rows
from app.marketlens.parsers.olx import CITY_LABELS, OLX_SECTIONS, OLXParser, OLXSourceError
from app.marketlens.refresh_analytics import refresh_analytics
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorized", action="store_true", help="Confirm OLX permits collection")
    parser.add_argument("--limit", type=int, default=30, help="Maximum unique listings")
    parser.add_argument(
        "--category", choices=OLX_SECTIONS, action="append", help="OLX category (repeatable)"
    )
    parser.add_argument(
        "--pages", type=int, default=1, help="Maximum OLX pages (3 nationally, 12 in a city)"
    )
    parser.add_argument("--city", choices=CITY_LABELS, help="OLX city slug")
    parser.add_argument("--query", help="Optional model name within the selected category")
    args = parser.parse_args()
    if not args.authorized:
        parser.error("--authorized is required to collect from OLX")
    categories = list(dict.fromkeys(args.category or ["phones"]))
    if args.limit * len(categories) > 1000:
        parser.error("--limit per category must keep the total at or below 1000")
    try:
        requests = [
            CollectionRequest(
                category=category,
                limit=args.limit,
                pages=args.pages,
                query=args.query,
                city=args.city,
            )
            for category in categories
        ]
    except ValidationError:
        parser.error("Use --limit 1–1000, --pages 1–3 (1–12 with --city) and a valid model name.")

    settings = MarketLensSettings()
    if not settings.firebase_enabled:
        parser.error("Enable the dedicated MarketLens Firebase project before updating")
    runtime = marketlens_runtime(settings)
    try:
        with httpx.Client() as client:
            collector = OLXParser(client, authorized=True)
            unique = {}
            for request in requests:
                collected = collector.collect(request)
                if not collected:
                    parser.exit(
                        1,
                        f"OLX returned no listings for {request.category}. "
                        "The catalog was left unchanged.\n",
                    )
                for row in collected:
                    unique.setdefault(row.id, row)
            rows = list(unique.values())
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
