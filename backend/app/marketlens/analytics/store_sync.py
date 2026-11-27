"""One call for core: analyze the stored real listings and save both result kinds."""

from datetime import UTC, datetime

from app.marketlens.analytics.engine import analyze


def analyze_store(store, computed_at: datetime | None = None) -> dict:
    """Uses only public MarketStore methods: scan_listings, save_analysis, save_stats."""
    listings, scan_limited = store.scan_listings()
    analysis = analyze(listings, computed_at=computed_at or datetime.now(UTC))
    return {
        "listings": len(listings),
        "scanLimited": scan_limited,
        "savedResults": sum(store.save_analysis(result) for result in analysis.results),
        "savedStats": sum(store.save_stats(stats) for stats in analysis.stats),
    }
