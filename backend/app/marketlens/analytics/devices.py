"""Model keys for the city categories beyond phones and laptops.

Each function returns (brand, model, variant). The model is what prices are
compared within; the variant narrows it further when the title says enough.
Categories without a reliable model in the title (fridges, sofas, bikes...)
stay overview-only.
"""

import re

_STORAGE = re.compile(r"\b(32|64|128|256|512)\s*gb\b|\b([12])\s*tb\b")

# --- tablets -----------------------------------------------------------------
_IPAD = re.compile(r"\bipad\s*(pro|air|mini)?\s*(\d{1,2})(?:\s*(?:gen|поколени\w*))?\b")
_IPAD_SIZE = re.compile(r"\bipad\s*(?:(?:pro|air)\s*(?:10|11|12|13)\b|11\s*(?:pro|air)\b)")
_GALAXY_TAB = re.compile(r"\btab\s*([sa]\d{1,2})(?:\s*(ultra|plus|\+|fe|lite))?(?!\w)")
_XIAOMI_PAD = re.compile(r"\b(?:redmi|xiaomi|mi)\s*pad\s*(\d{1,2}|se)?(?:\s*(pro|se))?(?!\w)")

# --- consoles ----------------------------------------------------------------
_PLAYSTATION = re.compile(r"\b(?:playstation|ps)\s*([345])(?:\s*(slim|pro|digital|fat))?(?!\w)")
_XBOX = re.compile(r"\bxbox\s*(series\s*[xs]|one\s*[xs]|one|360)(?!\w)")
_SWITCH = re.compile(r"\bswitch(?:\s*(oled|lite))?(?!\w)")

# --- headphones and speakers -------------------------------------------------
_AIRPODS = re.compile(r"\bairpods\s*(pro|max)?\s*(\d)?(?!\w)")
_SONY_HEADPHONES = re.compile(r"\b(wh|wf)\s*-?\s*(1000\s*xm\d|ch\d{3}n?)\b")
_BUDS = re.compile(r"\bgalaxy\s*buds\s*(\d|pro|live|fe|plus|\+)?(?:\s*(pro))?(?!\w)")
_JBL = re.compile(
    r"\bjbl\s*(charge|flip|go|clip|xtreme|boombox|partybox|pulse|tune|live)\s*(\d{1,3})\b"
)
_YANDEX = re.compile(
    r"\b(?:yandex|яндекс)\s*(?:station|станци\w*)\s*(mini|мини|max|макс|lite|лайт|2)?"
)

# --- screens -----------------------------------------------------------------
_INCHES = re.compile(r"(\d{2}(?:[.,]\d)?)\s*(?:\"|”|″|''|’’|дюйм\w*|inch\w*|in\b)")
_DIAGONAL = re.compile(r"диагонал\w*\s*(\d{2,3}(?:[.,]\d)?)\s*(см)?")
_CM = re.compile(r"\b(\d{2,3})\s*см\b")
# Manufacturer codes start with the diagonal: UE43AU7100, 55UQ75006LF, 43PUS7008.
_TV_CODE = re.compile(r"\b(?:ue|qe|un|kd|xr|ps)?(\d{2})[a-z]{1,4}\d{3,5}")
_HERTZ = re.compile(r"\b([1-9]\d{1,2})\s*(?:hz|гц|герц\w*)\b")
SCREEN_BRANDS = (
    "samsung",
    "lg",
    "sony",
    "xiaomi",
    "tcl",
    "hisense",
    "philips",
    "artel",
    "haier",
    "shivaki",
    "yasin",
    "toshiba",
    "panasonic",
    "asus",
    "acer",
    "aoc",
    "dell",
    "hp",
    "benq",
    "msi",
    "gigabyte",
    "huawei",
    "lenovo",
    "viewsonic",
)
_SCREEN_BRAND = re.compile(r"\b(" + "|".join(SCREEN_BRANDS) + r")\b")


def _slug(*parts: str | None) -> str:
    return "-".join(re.sub(r"\s+", "-", part) for part in parts if part).replace("+", "plus")


def _storage(text: str) -> str | None:
    if match := _STORAGE.search(text):
        return f"{match[1]}gb" if match[1] else f"{match[2]}tb"
    return None


def tablet_key(text: str) -> tuple[str | None, str | None, str | None]:
    if _IPAD_SIZE.search(text):
        # A screen size alone does not identify the generation of an Air or Pro.
        return "apple", None, None
    if match := _IPAD.search(text):
        return "apple", _slug("apple-ipad", match[1], match[2]), _storage(text)
    if match := _GALAXY_TAB.search(text):
        return "samsung", _slug("samsung-galaxy-tab", match[1], match[2]), _storage(text)
    if match := _XIAOMI_PAD.search(text):
        return "xiaomi", _slug("xiaomi-pad", match[1], match[2]), _storage(text)
    return None, None, None


def console_key(text: str) -> tuple[str | None, str | None, str | None]:
    if match := _PLAYSTATION.search(text):
        edition = match[2]
        # Pro is a different console; slim/digital are versions of the same one.
        model = _slug("sony-playstation", match[1], "pro" if edition == "pro" else None)
        return "sony", model, edition if edition in {"slim", "digital", "fat"} else None
    if match := _XBOX.search(text):
        return "microsoft", _slug("microsoft-xbox", match[1]), None
    if match := _SWITCH.search(text):
        return "nintendo", _slug("nintendo-switch", match[1]), None
    return None, None, None


def audio_key(text: str) -> tuple[str | None, str | None, str | None]:
    if match := _AIRPODS.search(text):
        return "apple", _slug("apple-airpods", match[1], match[2]), None
    if match := _SONY_HEADPHONES.search(text):
        return "sony", _slug("sony", match[1], match[2]), None
    if match := _BUDS.search(text):
        return "samsung", _slug("samsung-galaxy-buds", match[1], match[2]), None
    if match := _JBL.search(text):
        return "jbl", _slug("jbl", match[1], match[2]), None
    if match := _YANDEX.search(text):
        size = {"мини": "mini", "макс": "max", "лайт": "lite"}.get(match[1] or "", match[1])
        return "yandex", _slug("yandex-station", size), None
    return None, None, None


def diagonal(text: str, low: int, high: int) -> int | None:
    """Screen size in whole inches, if the title states one in a plausible range."""
    candidates: list[float] = []
    if match := _INCHES.search(text):
        candidates.append(float(match[1].replace(",", ".")))
    if match := _DIAGONAL.search(text):
        value = float(match[1].replace(",", "."))
        candidates.append(value / 2.54 if match[2] or value > high else value)
    if match := _CM.search(text):
        candidates.append(int(match[1]) / 2.54)
    if match := _TV_CODE.search(text):
        candidates.append(int(match[1]))
    for value in candidates:
        if low <= value <= high:
            return round(value)
    return None


def screen_key(text: str, *, monitor: bool) -> tuple[str | None, str | None, str | None]:
    brand_match = _SCREEN_BRAND.search(text)
    brand = brand_match[1] if brand_match else None
    size = diagonal(text, 17, 49) if monitor else diagonal(text, 19, 100)
    if size is None:
        return brand, None, None
    if monitor:
        hertz = _HERTZ.search(text)
        return brand, f"{size}in", f"{hertz[1]}hz" if hertz else None
    return brand, f"{size}in", brand


DEVICE_KEYS = {
    "tablets": tablet_key,
    "game-consoles": console_key,
    "headphones": audio_key,
    "audio": audio_key,
    "televisions": lambda text: screen_key(text, monitor=False),
    "monitors": lambda text: screen_key(text, monitor=True),
}
