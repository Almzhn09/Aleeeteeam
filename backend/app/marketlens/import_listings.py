"""Load a bounded JSON array of normalized live listings into dedicated Firestore."""

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.core.errors import AppError
from app.core.firebase import FirebaseRuntime
from app.marketlens.contracts import Listing
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 20_000_000:
            parser.error("Input exceeds 20 MB")
        items = TypeAdapter(list[Listing]).validate_json(args.input.read_bytes())
    except (OSError, ValidationError):
        parser.error("Expected a readable JSON array of valid Listing records")
    if not 1 <= len(items) <= 1000 or any(item.dataset != "real" for item in items):
        parser.error("Supply 1–1000 real listings. Fixture records cannot be imported here.")

    settings = MarketLensSettings()
    if not settings.firebase_enabled:
        parser.error("Enable the dedicated MarketLens Firebase project before importing")
    runtime = FirebaseRuntime(settings)
    saved = 0
    try:
        store = MarketStore(runtime.db())
        for item in items:
            saved += store.save_listing(item)
    except AppError as error:
        parser.exit(1, f"{error.message}\n")
    finally:
        runtime.close()
    print(json.dumps({"received": len(items), "savedObservations": saved}))


if __name__ == "__main__":
    main()
