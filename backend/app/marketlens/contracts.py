from collections.abc import Iterable
from typing import Literal, Protocol
from urllib.parse import urlsplit

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    JsonValue,
    model_validator,
)
from pydantic.alias_generators import to_camel

Source = Literal["olx", "krisha", "kolesa"]
Dataset = Literal["real", "fixture"]
RiskLevel = Literal["unknown", "low", "medium", "high"]
SOURCE_HOSTS = {"olx": "olx.kz", "krisha": "krisha.kz", "kolesa": "kolesa.kz"}


class MarketModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", allow_inf_nan=False
    )


class Listing(MarketModel):
    id: str = Field(min_length=3, max_length=144)
    external_id: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,128}$")
    source: Source
    dataset: Dataset
    url: HttpUrl
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=20000)
    category: str = Field(min_length=1, max_length=120)
    subcategory: str | None = Field(default=None, max_length=120)
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    city: str | None = Field(default=None, max_length=120)
    images: list[HttpUrl] = Field(default_factory=list, max_length=20)
    attributes: dict[str, JsonValue] = Field(default_factory=dict, max_length=50)
    condition: str | None = Field(default=None, max_length=120)
    published_at: AwareDatetime | None = None
    scraped_at: AwareDatetime
    seller_id: str | None = Field(default=None, max_length=150)

    @model_validator(mode="after")
    def check_provenance(self):
        if self.id != f"{self.source}:{self.external_id}":
            raise ValueError("Listing ID must match source:externalId")
        if self.external_id.startswith("fixture-") != (self.dataset == "fixture"):
            raise ValueError("Fixture IDs must use the reserved fixture- prefix")
        url = urlsplit(str(self.url))
        host = url.hostname or ""
        domain = SOURCE_HOSTS[self.source]
        if (
            url.scheme != "https"
            or url.username is not None
            or url.password is not None
            or url.port not in {None, 443}
            or not (host == domain or host.endswith(f".{domain}"))
        ):
            raise ValueError("Original URL must use HTTPS and belong to the source")
        if self.price is not None and self.currency is None:
            raise ValueError("A known price requires its currency")
        return self


class CollectionRequest(MarketModel):
    category: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=100, ge=1, le=1000)
    pages: int = Field(default=1, ge=1, le=3)
    query: str | None = Field(default=None, min_length=1, max_length=80, pattern=r"^[\w -]+$")


class ListingParser(Protocol):
    @property
    def source(self) -> Source: ...

    def collect(self, request: CollectionRequest) -> Iterable[Listing]: ...


class RiskReason(MarketModel):
    code: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)


class AnalysisResult(MarketModel):
    listing_id: str
    listing_scraped_at: AwareDatetime
    computed_at: AwareDatetime
    algorithm_version: str = Field(min_length=1, max_length=100)
    comparable_group: str | None = None
    market_price: float | None = Field(default=None, gt=0)
    price_deviation_percent: float | None = None
    savings_amount: float | None = None
    deal_score: int | None = Field(default=None, ge=0, le=100)
    risk_score: int | None = Field(default=None, ge=0, le=100)
    risk_level: RiskLevel = "unknown"
    risk_reasons: list[RiskReason] = Field(default_factory=list, max_length=20)
    confidence: float | None = Field(default=None, ge=0, le=1)
    sample_size: int = Field(default=0, ge=0)
    is_deal: bool = False


class PriceBin(MarketModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)
    count: int = Field(ge=0)


class MarketStats(MarketModel):
    dataset: Dataset
    computed_at: AwareDatetime
    comparable_group: str
    category: str
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sample_size: int = Field(ge=0)
    mean_price: float | None = Field(default=None, ge=0)
    median_price: float | None = Field(default=None, ge=0)
    min_price: float | None = Field(default=None, ge=0)
    max_price: float | None = Field(default=None, ge=0)
    histogram: list[PriceBin] = Field(default_factory=list, max_length=100)


class ListingItem(MarketModel):
    listing: Listing
    analysis: AnalysisResult | None = None


class ListingPage(MarketModel):
    items: list[ListingItem]
    next_offset: int | None
    scanned_count: int
    scan_limited: bool


class StatsPage(MarketModel):
    items: list[MarketStats]
    truncated: bool


class PriceObservation(MarketModel):
    scraped_at: AwareDatetime
    price: float | None
    currency: str | None


class PriceHistory(MarketModel):
    items: list[PriceObservation]
    truncated: bool
