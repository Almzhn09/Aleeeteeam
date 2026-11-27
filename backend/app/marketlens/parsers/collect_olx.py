"""Export an authorized OLX.kz category for the MarketLens importer."""

import argparse

import httpx
from pydantic import TypeAdapter, ValidationError

from app.marketlens.contracts import CollectionRequest, Listing
from app.marketlens.parsers.olx import OLX_SECTIONS, OLXParser, OLXSourceError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="Maximum unique listings")
    parser.add_argument(
        "--authorized",
        action="store_true",
        help="Confirm that OLX permits collection of this category",
    )
    parser.add_argument(
        "--category", choices=OLX_SECTIONS, default="phones", help="OLX category to collect"
    )
    parser.add_argument("--pages", type=int, default=1, help="Maximum OLX pages (1–3)")
    parser.add_argument("--query", help="Optional model name within the selected category")
    args = parser.parse_args()
    try:
        request = CollectionRequest(
            category=args.category, limit=args.limit, pages=args.pages, query=args.query
        )
    except ValidationError:
        parser.error("Use --limit 1–1000, --pages 1–3 and a model name with letters or numbers.")
    with httpx.Client() as client:
        try:
            listings = OLXParser(client, authorized=args.authorized).collect(request)
        except (OLXSourceError, ValueError) as error:
            parser.exit(1, f"{error}\n")
    if not listings:
        parser.exit(1, "OLX: категория пуста, передавать в импорт нечего\n")
    print(TypeAdapter(list[Listing]).dump_json(listings, by_alias=True, indent=2).decode())


if __name__ == "__main__":
    main()
