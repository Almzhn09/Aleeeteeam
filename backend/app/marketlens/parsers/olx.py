"""Collect public OLX.kz mobile phone cards from an authorized category page."""

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.marketlens.contracts import CollectionRequest, Listing, Source

CATEGORY = "electronics"
CATEGORY_URL = "https://www.olx.kz/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/"
USER_AGENT = "MarketLens/1.0"
DETAIL_PATH = re.compile(r"/d/(?:obyavlenie|ogoloshennya)/[^/]+-ID([A-Za-z0-9]+)\.html")
PRICE = re.compile(
    r"([0-9]+(?: [0-9]{3})*)(?:[,.]([0-9]{1,2}))? (?:тг\.?|₸|KZT)(?:\s*Договорная)?", re.I
)
VOID_TAGS = set("area base br col embed hr img input link meta param source track wbr".split())


class OLXSourceError(RuntimeError):
    """OLX could not supply a recognizable category response."""


@dataclass
class _Card:
    hrefs: list[str] = field(default_factory=list)
    title: list[str] = field(default_factory=list)
    price: list[str] = field(default_factory=list)


class _Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards: list[_Card] = []
        self.empty = False
        self._card: _Card | None = None
        self._tags: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-testid") == "listing-empty-state":
            self.empty = True
        if tag == "div" and attrs.get("data-cy") == "l-card":
            self._finish()
            self._card = _Card()
        if self._card is None:
            return
        if tag == "a" and (href := attrs.get("href")):
            self._card.hrefs.append(href)
        if tag in VOID_TAGS:
            return
        capture = self._tags[-1][1] if self._tags else None
        if tag in {"h4", "h6"}:
            capture = "title"
        if attrs.get("data-testid") == "ad-price":
            capture = "price"
        if tag in {"style", "script"}:
            capture = None
        self._tags.append((tag, capture))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self._tags) - 1, -1, -1):
            if self._tags[index][0] == tag:
                del self._tags[index:]
                if not self._tags:
                    self._finish()
                break

    def handle_data(self, data):
        if self._card is not None and self._tags:
            capture = self._tags[-1][1]
            if capture == "title":
                self._card.title.append(data)
            if capture == "price":
                self._card.price.append(data)

    def _finish(self):
        if self._card is not None:
            self.cards.append(self._card)
        self._card = None
        self._tags.clear()


def _original(href: str) -> tuple[str, str] | None:
    try:
        url = urlsplit(urljoin(CATEGORY_URL, href))
        if url.scheme != "https" or url.netloc.lower() not in {"olx.kz", "www.olx.kz"}:
            return None
    except ValueError:
        return None
    match = DETAIL_PATH.fullmatch(url.path)
    if match:
        return match[1], urlunsplit(("https", url.netloc.lower(), url.path, "", ""))
    return None


def _normalize(card: _Card, scraped_at: datetime) -> Listing | None:
    title = " ".join("".join(card.title).split())
    if not 1 <= len(title) <= 500:
        return None
    originals: dict[str, str] = {}
    for href in card.hrefs:
        if original := _original(href):
            originals.setdefault(*original)
    if len(originals) != 1:
        return None
    external_id, url = originals.popitem()
    if len(external_id) > 128 or len(url) > 2083:
        return None

    match = PRICE.fullmatch(" ".join("".join(card.price).split()))
    price = None
    if match:
        amount = match[1].replace(" ", "")
        if len(amount) <= 15:
            price = float(f"{amount}.{match[2] or '0'}")
    try:
        return Listing(
            id=f"olx:{external_id}",
            external_id=external_id,
            source="olx",
            dataset="real",
            url=url,
            title=title,
            category=CATEGORY,
            subcategory="phones",
            price=price,
            currency="KZT" if price is not None else None,
            scraped_at=scraped_at,
        )
    except ValidationError:
        return None


class OLXParser:
    """One category page per collection, with a new observation time on each run."""

    source: Source = "olx"

    def __init__(self, client: httpx.Client, *, authorized: bool = False):
        self._client = client
        self._authorized = authorized

    def collect(self, request: CollectionRequest) -> list[Listing]:
        if request.category != CATEGORY:
            raise ValueError("OLX: поддерживается только electronics (мобильные телефоны)")
        if not self._authorized:
            raise OLXSourceError("OLX: требуется подтверждённое разрешение на сбор категории")
        try:
            response = self._client.get(
                CATEGORY_URL,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                follow_redirects=False,
                timeout=15,
            )
        except httpx.ProxyError as error:
            raise OLXSourceError("OLX: доступ через сетевой прокси недоступен") from error
        except httpx.RequestError as error:
            raise OLXSourceError(f"OLX: ошибка запроса ({type(error).__name__})") from error
        if response.status_code != 200:
            raise OLXSourceError(f"OLX: категория недоступна (HTTP {response.status_code})")
        if response.headers.get("content-type", "").split(";")[0].strip().lower() != "text/html":
            raise OLXSourceError("OLX: ожидалась HTML-страница категории")

        cards = _Cards()
        cards.feed(response.text)
        cards.close()
        scraped_at = datetime.now(UTC)
        unique: dict[str, Listing] = {}
        for card in cards.cards:
            listing = _normalize(card, scraped_at)
            if listing is not None:
                unique.setdefault(listing.id, listing)
                if len(unique) == request.limit:
                    break
        if not unique and (cards.cards or not cards.empty):
            raise OLXSourceError("OLX: не найдены распознаваемые карточки категории")
        return list(unique.values())
