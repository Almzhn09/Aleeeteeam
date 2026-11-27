"""Calculate and publish analytics for the MarketLens catalog without Gemini."""

import argparse
import json
from datetime import UTC, datetime

from google.api_core.exceptions import GoogleAPIError

from app.core.errors import AppError
from app.marketlens.analytics import analyze
from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings
from app.marketlens.store import MarketStore


def refresh_analytics(store: MarketStore) -> dict[str, int | bool]:
    computed_at = datetime.now(UTC)
    listings, scan_limited = store.scan_listings()
    output = analyze(listings, computed_at=computed_at)
    return {
        "scannedCount": len(listings),
        "scanLimited": scan_limited,
        "savedResults": sum(store.save_analysis(result) for result in output.results),
        "savedGroups": sum(store.save_stats(stats) for stats in output.stats),
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
