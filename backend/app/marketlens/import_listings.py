"""Load a bounded JSON array of normalized live listings into dedicated Firestore."""

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.core.errors import AppError
from app.marketlens.contracts import Listing
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def validate_import_rows(items: list[Listing]) -> None:
    if not 1 <= len(items) <= 1000 or any(item.dataset != "real" for item in items):
        raise ValueError("Supply 1–1000 real listings. Fixture records cannot be imported here.")


def import_rows(store: MarketStore, items: list[Listing]) -> dict[str, int]:
    return {
        "received": len(items),
        "savedObservations": sum(store.save_listing(item) for item in items),
    }


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

    try:
        validate_import_rows(items)
    except ValueError as error:
        parser.error(str(error))

    settings = MarketLensSettings()
    if not settings.firebase_enabled:
        parser.error("Enable the dedicated MarketLens Firebase project before importing")
    runtime = marketlens_runtime(settings)
    try:
        output = import_rows(MarketStore(runtime.db()), items)
    except AppError as error:
        parser.exit(1, f"{error.message}\n")
    finally:
        runtime.close()
    print(json.dumps(output))


if __name__ == "__main__":
    main()
