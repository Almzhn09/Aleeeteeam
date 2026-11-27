"""Analyze a JSON array of Listing records and print AnalysisResult and MarketStats.

Pure computation: nothing is read from or written to Firestore.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.marketlens.analytics import analyze
from app.marketlens.contracts import AnalysisResult, Listing, MarketStats


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="JSON array of Listing (export of collect_olx)")
    parser.add_argument(
        "--computed-at",
        type=datetime.fromisoformat,
        help="RFC 3339 time for a reproducible run (default: now, UTC)",
    )
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 20_000_000:
            parser.error("Input exceeds 20 MB")
        listings = TypeAdapter(list[Listing]).validate_json(args.input.read_bytes())
    except (OSError, ValidationError):
        parser.error("Expected a readable JSON array of valid Listing records")
    computed_at = args.computed_at or datetime.now(UTC)
    if computed_at.tzinfo is None:
        parser.error("--computed-at must include a timezone, e.g. 2026-11-27T09:05:00Z")
    analysis = analyze(listings, computed_at=computed_at)
    output = {
        "results": TypeAdapter(list[AnalysisResult]).dump_python(
            analysis.results, mode="json", by_alias=True
        ),
        "stats": TypeAdapter(list[MarketStats]).dump_python(
            analysis.stats, mode="json", by_alias=True
        ),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    results = analysis.results
    summary = {
        "listings": len(results),
        "withMarketPrice": sum(r.market_price is not None for r in results),
        "deals": sum(r.is_deal for r in results),
        "riskMediumOrHigh": sum(r.risk_level in {"medium", "high"} for r in results),
        "groups": len(analysis.stats),
    }
    print(json.dumps(summary), file=sys.stderr)


if __name__ == "__main__":
    main()
