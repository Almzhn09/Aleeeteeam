from datetime import UTC
from hashlib import sha256

from firebase_admin import firestore

from app.marketlens.analytics import ALGORITHM_VERSION
from app.marketlens.contracts import (
    AnalysisResult,
    Listing,
    ListingItem,
    MarketStats,
    PriceHistory,
    PriceObservation,
)

SCAN_LIMIT = 1000
STATS_LIMIT = 100


class MarketStore:
    def __init__(self, db):
        self.db = db

    def save_listing(self, listing: Listing) -> bool:
        """Persist an observation once. An older observation cannot replace the latest one."""
        listing_ref = self.db.collection("listings").document(listing.id)
        time_key = listing.scraped_at.astimezone(UTC).isoformat()
        snapshot_id = sha256(f"{listing.id}|{time_key}".encode()).hexdigest()
        snapshot_ref = self.db.collection("listingSnapshots").document(snapshot_id)

        @firestore.transactional
        def write(transaction):
            current = listing_ref.get(transaction=transaction).to_dict()
            if snapshot_ref.get(transaction=transaction).exists:
                return False
            transaction.create(
                snapshot_ref,
                {
                    "listingId": listing.id,
                    "scrapedAt": listing.scraped_at,
                    "dataset": listing.dataset,
                    "price": listing.price,
                    "currency": listing.currency,
                },
            )
            if current is None or Listing.model_validate(current).scraped_at < listing.scraped_at:
                transaction.set(listing_ref, listing.model_dump(mode="json", by_alias=True))
            return True

        return write(self.db.transaction())

    def save_analysis(self, result: AnalysisResult) -> bool:
        listing_ref = self.db.collection("listings").document(result.listing_id)
        reference = self.db.collection("analysisResults").document(result.listing_id)

        @firestore.transactional
        def write(transaction):
            listing = listing_ref.get(transaction=transaction).to_dict()
            if (
                listing is None
                or Listing.model_validate(listing).scraped_at != result.listing_scraped_at
            ):
                return False
            existing = reference.get(transaction=transaction).to_dict()
            if (
                existing is not None
                and AnalysisResult.model_validate(existing).computed_at >= result.computed_at
            ):
                return False
            transaction.set(reference, result.model_dump(mode="json", by_alias=True))
            return True

        return write(self.db.transaction())

    def save_stats(self, stats: MarketStats) -> bool:
        key = f"{stats.dataset}|{stats.currency}|{stats.comparable_group}"
        reference = self.db.collection("marketStats").document(sha256(key.encode()).hexdigest())

        @firestore.transactional
        def write(transaction):
            existing = reference.get(transaction=transaction).to_dict()
            if (
                existing is not None
                and MarketStats.model_validate(existing).computed_at >= stats.computed_at
            ):
                return False
            transaction.set(reference, stats.model_dump(mode="json", by_alias=True))
            return True

        return write(self.db.transaction())

    def get_listing(self, listing_id: str) -> Listing | None:
        record = self.db.collection("listings").document(listing_id).get().to_dict()
        if record is None or record.get("dataset") != "real":
            return None
        return Listing.model_validate(record)

    def price_history(self, listing_id: str, limit: int) -> PriceHistory:
        records = list(
            self.db.collection("listingSnapshots")
            .where(filter=firestore.FieldFilter("listingId", "==", listing_id))
            .order_by("scrapedAt", direction=firestore.Query.DESCENDING)
            .select(["scrapedAt", "price", "currency"])
            .limit(limit + 1)
            .stream()
        )
        return PriceHistory(
            items=[PriceObservation.model_validate(record.to_dict()) for record in records[:limit]],
            truncated=len(records) > limit,
        )

    def scan_listings(self) -> tuple[list[Listing], bool]:
        records = list(
            self.db.collection("listings")
            .where(filter=firestore.FieldFilter("dataset", "==", "real"))
            .order_by("__name__")
            .limit(SCAN_LIMIT + 1)
            .stream()
        )
        return [Listing.model_validate(record.to_dict()) for record in records[:SCAN_LIMIT]], len(
            records
        ) > SCAN_LIMIT

    def with_analysis(self, listings: list[Listing]) -> list[ListingItem]:
        if not listings:
            return []
        collection = self.db.collection("analysisResults")
        records = self.db.get_all([collection.document(listing.id) for listing in listings])
        results = {
            record.id: AnalysisResult.model_validate(record.to_dict())
            for record in records
            if record.exists
        }
        items = []
        for listing in listings:
            result = results.get(listing.id)
            if result is not None and (
                result.listing_id != listing.id
                or result.listing_scraped_at != listing.scraped_at
                or result.algorithm_version != ALGORITHM_VERSION
            ):
                result = None
            items.append(ListingItem(listing=listing, analysis=result))
        return items

    def get_stats(self) -> tuple[list[MarketStats], bool]:
        records = list(
            self.db.collection("marketStats")
            .where(filter=firestore.FieldFilter("dataset", "==", "real"))
            .order_by("__name__")
            .limit(STATS_LIMIT + 1)
            .stream()
        )
        return [
            MarketStats.model_validate(record.to_dict()) for record in records[:STATS_LIMIT]
        ], len(records) > STATS_LIMIT
