"""Collect public OLX.kz mobile phone cards from an authorized category page."""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

import httpx
from pydantic import ValidationError

from app.marketlens.contracts import CollectionRequest, Listing, Source

CATEGORY = "electronics"
CATEGORY_URL = "https://www.olx.kz/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/"
OLX_SECTIONS = {
    "phones": CATEGORY_URL,
    "laptops": "https://www.olx.kz/elektronika/noutbuki-i-aksesuary/noutbuki/",
}

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
    location: list[str] = field(default_factory=list)


class _Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards: list[_Card] = []
        self.empty = False
        self.embedded: list[str] = []
        self._structured_data = False
        self._card: _Card | None = None
        self._tags: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self._structured_data = attrs.get("type") == "application/ld+json"
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
        if attrs.get("data-testid") == "location-date":
            capture = "location"
        if tag in {"style", "script"}:
            capture = None
        self._tags.append((tag, capture))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "script":
            self._structured_data = False
        for index in range(len(self._tags) - 1, -1, -1):
            if self._tags[index][0] == tag:
                del self._tags[index:]
                if not self._tags:
                    self._finish()
                break

    def handle_data(self, data):
        if self._structured_data:
            self.embedded.append(data)
            return
        if self._card is not None and self._tags:
            capture = self._tags[-1][1]
            if capture == "title":
                self._card.title.append(data)
            if capture == "price":
                self._card.price.append(data)
            if capture == "location":
                self._card.location.append(data)

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


def _offer_images(documents: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for document in documents:
        try:
            page = json.loads(document)
        except (ValueError, RecursionError):
            continue
        aggregate = page.get("offers") if isinstance(page, dict) else None
        offers = aggregate.get("offers") if isinstance(aggregate, dict) else None
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if not isinstance(offer, dict) or not isinstance(offer.get("url"), str):
                continue
            original = _original(offer["url"])
            images = offer.get("image")
            if original is None or not isinstance(images, list):
                continue
            urls = list(dict.fromkeys(url for url in images if _is_olx_photo(url)))[:20]
            if urls:
                result.setdefault(original[0], urls)
    return result


def _is_olx_photo(value) -> bool:
    if not isinstance(value, str) or len(value) > 2083:
        return False
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        return (
            url.scheme == "https"
            and host.endswith(".olxcdn.com")
            and url.port in {None, 443}
            and url.username is None
            and url.password is None
            and url.path.startswith("/v1/files/")
        )
    except ValueError:
        return False


def _city(location: list[str]) -> str | None:
    place, separator, _ = " ".join("".join(location).split()).rpartition(" - ")
    value = place.split(",", 1)[0].strip()
    return value if separator and 1 <= len(value) <= 120 else None


def _normalize(
    card: _Card, scraped_at: datetime, images: dict[str, list[str]], subcategory: str
) -> Listing | None:
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
            subcategory=subcategory,
            price=price,
            currency="KZT" if price is not None else None,
            city=_city(card.location),
            images=images.get(external_id, []),
            scraped_at=scraped_at,
        )
    except ValidationError:
        return None


class OLXParser:
    """Up to three pages of one category per collection, with a new observation time on each run."""

    source: Source = "olx"

    def __init__(self, client: httpx.Client, *, authorized: bool = False):
        self._client = client
        self._authorized = authorized

    def collect(self, request: CollectionRequest) -> list[Listing]:
        section = "phones" if request.category == CATEGORY else request.category
        if section not in OLX_SECTIONS:
            raise ValueError("OLX: поддерживаются electronics/phones и electronics/laptops")
        if not self._authorized:
            raise OLXSourceError("OLX: требуется подтверждённое разрешение на сбор категории")
        url = OLX_SECTIONS[section]
        if request.query:
            slug = "-".join(request.query.split()).strip("-")
            if not any(character.isalnum() for character in slug):
                raise ValueError("OLX: строка поиска должна содержать название модели")
            url = f"{url}q-{quote(slug, safe='')}/"
        scraped_at = datetime.now(UTC)
        unique: dict[str, Listing] = {}
        for page in range(1, request.pages + 1):
            rows = self._collect_page(url, section, page, scraped_at)
            if not rows:
                break
            for row in rows:
                unique.setdefault(row.id, row)
                if len(unique) == request.limit:
                    return list(unique.values())
        return list(unique.values())

    def _collect_page(
        self, url: str, section: str, page: int, scraped_at: datetime
    ) -> list[Listing]:
        try:
            response = self._client.get(
                url,
                params={"page": page} if page > 1 else None,
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
        images = _offer_images(cards.embedded)
        rows = [
            listing
            for card in cards.cards
            if (listing := _normalize(card, scraped_at, images, section)) is not None
        ]
        if not rows and (cards.cards or not cards.empty):
            raise OLXSourceError(f"OLX: на странице {page} не найдены распознаваемые карточки")
        return rows
