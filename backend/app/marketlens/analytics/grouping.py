"""Deterministic comparable groups derived from normalized Listing fields.

A group always separates dataset (by the caller), category, condition and currency.
Inside a category the title is reduced to a product key, from the most specific
level (model and storage) to the whole category. The engine picks the most specific
level that still has enough priced peers.
"""

import re
from dataclasses import dataclass

from app.marketlens.contracts import Listing

# Prices are compared only inside one model; brand and category are overview stats.
LEVELS = ("variant", "model")
OVERVIEW_LEVELS = ("brand", "category")
LEVEL_WEIGHT = {"variant": 1.0, "model": 0.9}

_TRANSLITERATION = tuple(
    (re.compile(pattern), replacement)
    for pattern, replacement in (
        (r"айфон|айфн", "iphone"),
        (r"самсунг|самсунк", "samsung"),
        (r"галакси", "galaxy"),
        (r"редми", "redmi"),
        (r"сяоми|ксиоми|ксяоми|xiomi|xaomi", "xiaomi"),
        (r"\bпоко\b", "poco"),
        (r"хуавей|хуавэй", "huawei"),
        (r"хонор", "honor"),
        (r"реалми", "realme"),
        (r"пиксель", "pixel"),
        (r"\bпро\b", "pro"),
        (r"\bмакс\b", "max"),
        (r"\bплюс\b", "plus"),
        (r"\bмини\b", "mini"),
        (r"\bультра\b", "ultra"),
        (r"\bнот\b|\bноут\b", "note"),
        (r"\bа(?=\d)", "a"),
        (r"\bм(?=\d)", "m"),
        (r"(?<=\d)\s*(?:гб|гиг)\b", " gb"),
        (r"(?<=\d)\s*тб\b", " tb"),
        (r"(?<=\d)(?=gb\b|tb\b)", " "),
    )
)

# The trailing (?!\w) also ends a match after "+", where \b would not.
_MODEL_PATTERNS = (
    (
        "apple",
        re.compile(
            r"\biphone\s*(\d{1,2}|se|xs|xr|x)(?:\s*\(?(?:20[12]\d)\)?)?"
            r"(?:\s*(pro\s*max|pro|max|plus|mini|e))?(?!\w)"
        ),
    ),
    (
        "samsung",
        re.compile(
            r"\b(?:galaxy|samsung)\s*(?:galaxy\s*)?"
            r"(z\s*fold\s*\d|z\s*flip\s*\d|note\s*\d{1,2}|s\d{1,2}|[amf]\d{1,3})"
            r"(?:\s*(ultra|plus|\+|fe|lite|edge))?(?!\w)"
        ),
    ),
    (
        "xiaomi",
        re.compile(
            r"\b(redmi\s*note\s*\d{1,2}[a-z]?|redmi\s*\d{1,2}[a-z]?|poco\s*[a-z]\d{1,2}"
            r"|xiaomi\s*\d{1,2}t?|mi\s*\d{1,2}t?)"
            r"(?:\s*(pro\s*\+|pro\s*plus|pro|ultra|lite|s|c))?(?!\w)"
        ),
    ),
    ("google", re.compile(r"\bpixel\s*(\d{1,2}a?)(?:\s*(pro\s*xl|pro|xl))?(?!\w)")),
)

_BRANDS = (
    ("apple", re.compile(r"\b(?:iphone|apple)\b")),
    ("samsung", re.compile(r"\b(?:samsung|galaxy)\b")),
    ("xiaomi", re.compile(r"\b(?:xiaomi|redmi|poco)\b")),
    ("huawei", re.compile(r"\bhuawei\b")),
    ("honor", re.compile(r"\bhonor\b")),
    ("realme", re.compile(r"\brealme\b")),
    ("google", re.compile(r"\b(?:pixel|google)\b")),
    ("oneplus", re.compile(r"\bone\s*plus\b")),
    ("oppo", re.compile(r"\boppo\b")),
    ("vivo", re.compile(r"\bvivo\b")),
    ("tecno", re.compile(r"\btecno\b")),
    ("infinix", re.compile(r"\binfinix\b")),
    ("nokia", re.compile(r"\bnokia\b")),
    ("motorola", re.compile(r"\b(?:motorola|moto)\b")),
)

_STORAGE_TB = re.compile(r"\b([12])\s*tb\b")
_STORAGE_GB = re.compile(r"\b(16|32|64|128|256|512)\s*gb\b")
_STORAGE_PAIR = re.compile(r"\b\d{1,2}\s*/\s*(16|32|64|128|256|512|1024)\b")
# A bare capacity right after the model ("Айфон 12 про макс 128"). 16 and 32 are
# left out because they collide with model numbers.
_STORAGE_BARE = re.compile(r"\s*(64|128|256|512)\b")


def normalize_text(text: str) -> str:
    text = text.lower().replace("ё", "е")
    for pattern, replacement in _TRANSLITERATION:
        text = pattern.sub(replacement, text)
    return " ".join(re.sub(r"[^\w+/()]+", " ", text).split())


def _slug(*parts: str | None) -> str:
    return "-".join(re.sub(r"\s+", "", part) for part in parts if part).replace("+", "plus")


@dataclass(frozen=True)
class ProductKey:
    brand: str | None
    model: str | None
    storage: str | None


def product_key(title: str) -> ProductKey:
    text = normalize_text(title)
    for brand, pattern in _MODEL_PATTERNS:
        if match := pattern.search(text):
            prefix = {"apple": "iphone", "samsung": "galaxy", "google": "pixel"}.get(brand)
            name = _slug(prefix, match[1], match[2])
            storage = _storage(text)
            if storage is None and (bare := _STORAGE_BARE.match(text, match.end())):
                storage = f"{bare[1]}gb"
            return ProductKey(brand, f"{brand}-{name}", storage)
    brand = next((name for name, pattern in _BRANDS if pattern.search(text)), None)
    return ProductKey(brand, None, _storage(text))


def _storage(text: str) -> str | None:
    if match := _STORAGE_TB.search(text):
        return f"{match[1]}tb"
    if match := _STORAGE_GB.search(text):
        return f"{match[1]}gb"
    if match := _STORAGE_PAIR.search(text):
        return "1tb" if match[1] == "1024" else f"{match[1]}gb"
    return None


def group_keys(listing: Listing) -> dict[str, str]:
    """Return group keys for each level that applies, most specific first.

    Format: `<category>[/<subcategory>]:<product>[:<storage>]:<condition>:<currency>`.
    Dataset is not part of the string because MarketStats stores it separately.
    """
    scope = listing.category + (f"/{listing.subcategory}" if listing.subcategory else "")
    condition = (
        re.sub(r"\W+", "-", normalize_text(listing.condition)).strip("-")
        if listing.condition
        else "any"
    )
    currency = listing.currency or "none"
    key = product_key(listing.title)
    keys: dict[str, str] = {}
    if key.model and key.storage:
        keys["variant"] = f"{scope}:{key.model}:{key.storage}:{condition}:{currency}"
    if key.model:
        keys["model"] = f"{scope}:{key.model}:{condition}:{currency}"
    if key.brand:
        keys["brand"] = f"{scope}:{key.brand}:{condition}:{currency}"
    keys["category"] = f"{scope}:all:{condition}:{currency}"
    return keys
