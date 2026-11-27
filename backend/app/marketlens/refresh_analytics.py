"""Calculate and publish analytics for the MarketLens catalog without Gemini."""

import argparse
import json
from datetime import UTC, datetime

from google.api_core.exceptions import GoogleAPIError

from app.core.errors import AppError
from app.marketlens.analytics import analyze_store
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def refresh_analytics(store: MarketStore) -> dict[str, int | bool]:
    output = analyze_store(store, computed_at=datetime.now(UTC))
    return {
        "scannedCount": output["listings"],
        "scanLimited": output["scanLimited"],
        "savedResults": output["savedResults"],
        "savedGroups": output["savedStats"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    settings = MarketLensSettings()
    if not settings.firebase_enabled:
        parser.error("Enable the dedicated MarketLens Firebase project before refreshing")
    runtime = marketlens_runtime(settings)
    try:
        output = refresh_analytics(MarketStore(runtime.db()))
    except AppError as error:
        parser.exit(1, f"{error.message}\n")
    except GoogleAPIError:
        parser.exit(1, "Firestore analytics refresh failed; check access and rerun the refresh.\n")
    finally:
        runtime.close()
    print(json.dumps(output))


if __name__ == "__main__":
    main()
