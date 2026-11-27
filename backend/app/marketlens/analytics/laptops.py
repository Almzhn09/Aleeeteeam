"""Laptop model keys: "<brand>-<series>[-<number>]" and the processor as the variant."""

import re

# Series word -> brand. The brand word itself is optional in OLX titles.
SERIES = {
    "macbook": "apple",
    "ideapad": "lenovo",
    "thinkpad": "lenovo",
    "thinkbook": "lenovo",
    "legion": "lenovo",
    "yoga": "lenovo",
    "loq": "lenovo",
    "vivobook": "asus",
    "zenbook": "asus",
    "tuf": "asus",
    "rog": "asus",
    "pavilion": "hp",
    "victus": "hp",
    "omen": "hp",
    "elitebook": "hp",
    "probook": "hp",
    "envy": "hp",
    "aspire": "acer",
    "nitro": "acer",
    "swift": "acer",
    "predator": "acer",
    "extensa": "acer",
    "inspiron": "dell",
    "latitude": "dell",
    "vostro": "dell",
    "xps": "dell",
    "alienware": "dell",
    "matebook": "huawei",
    "magicbook": "honor",
    "redmibook": "xiaomi",
}

_SERIES = "|".join(SERIES)
# MacBook: line (air/pro) and Apple chip; other series: optional line word and a number.
_MACBOOK = re.compile(
    r"\bmacbook\s*(air|pro)?(?:\s+\d{2}(?:\s*(?:дюйм\w*|inch|\"))?)?\s*(m[1-4])?\b"
)
_MODEL = re.compile(
    rf"\b({_SERIES})(?:\s+(?:gaming|slim|thin|pro|plus|x))?(?:\s+([a-z]{{0,2}}\d{{1,2}}[a-z]?))?\b"
)
_CHIP = re.compile(r"\b(m[1-4])(?:\s*(pro|max))?\b")
_INTEL = re.compile(r"\b(?:core\s*)?i([3579])\b")
_RYZEN = re.compile(r"\bryzen\s*([3579])\b")


def laptop_key(text: str) -> tuple[str | None, str | None, str | None]:
    """Return (brand, model, processor) from normalized title text."""
    if match := _MACBOOK.search(text):
        model = "-".join(part for part in ("apple-macbook", match[1], match[2]) if part)
        return "apple", model, _processor(text)
    if match := _MODEL.search(text):
        brand = SERIES[match[1]]
        model = "-".join(part for part in (brand, match[1], match[2]) if part)
        return brand, model, _processor(text)
    return None, None, _processor(text)


def _processor(text: str) -> str | None:
    if match := _CHIP.search(text):
        return "-".join(part for part in match.groups() if part)
    if match := _INTEL.search(text):
        return f"i{match[1]}"
    if match := _RYZEN.search(text):
        return f"ryzen{match[1]}"
    return None
