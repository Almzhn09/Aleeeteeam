"""One call for core: analyze the stored real listings and save both result kinds."""

from datetime import UTC, datetime

from app.marketlens.analytics.engine import analyze, models_needing_samples


def analyze_store(store, computed_at: datetime | None = None) -> dict:
    """Uses only public MarketStore methods: scan_listings, save_analysis, publish_stats."""
    when = computed_at or datetime.now(UTC)
    listings, scan_limited = store.scan_listings()
    analysis = analyze(listings, computed_at=when)
    return {
        "listings": len(listings),
        "scanLimited": scan_limited,
        "savedResults": sum(store.save_analysis(result) for result in analysis.results),
        "savedStats": store.publish_stats(analysis.stats, when),
        "modelsNeedingSamples": models_needing_samples(listings),
    }
