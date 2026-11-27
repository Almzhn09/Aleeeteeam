"""Explainable risk signals. Each signal is a reason to check, never a verdict."""

import re
from dataclasses import dataclass

from app.marketlens.analytics.grouping import normalize_text
from app.marketlens.contracts import Listing, RiskReason

# Deviation thresholds in percent relative to the comparable market price.
FAR_BELOW = -40.0
BELOW = -25.0
FAR_ABOVE = 60.0
MEDIUM_FROM = 30
HIGH_FROM = 60


@dataclass(frozen=True)
class Signal:
    code: str
    weight: int
    description: str
    # The listing does not describe a working device and must not shape the market price.
    excludes_from_market: bool = False


_TEXT_SIGNALS = (
    (
        re.compile(r"\b(?:предоплат\w*|prepay\w*|переведите|перевод на карту|kaspi перевод)\b"),
        Signal("prepayment_request", 25, "В тексте упоминается предоплата или перевод заранее"),
    ),
    (
        re.compile(r"\b(?:копи[яи]|реплик\w*|replica|не оригинал\w*|паль|подделк\w*)\b"),
        Signal(
            "replica_mention",
            30,
            "В тексте упоминается копия или неоригинальное устройство",
            excludes_from_market=True,
        ),
    ),
    (
        re.compile(
            r"\b(?:(?:на|под) (?:icloud|айклауд)|icloud lock|заблокир\w*|блокировк\w*|"
            r"залочен\w*|locked|без (?:коробки и |чека и )?документ\w*)\b"
        ),
        Signal(
            "lock_or_documents",
            25,
            "Упоминается блокировка устройства или отсутствие документов",
            excludes_from_market=True,
        ),
    ),
    (
        re.compile(r"\b(?:на запчаст\w*|запчаст\w*|не работает|не включается|разбит\w*|parts)\b"),
        Signal(
            "parts_or_damage",
            15,
            "Устройство описано как неисправное или на запчасти",
            excludes_from_market=True,
        ),
    ),
    (
        re.compile(r"\b(?:срочно|сегодня только|только сегодня|urgent)\b"),
        Signal("urgency_wording", 10, "Текст подталкивает к срочному решению"),
    ),
)


# Model searches also return accessories and parts: "Чехол для iPhone 13", "Дисплей iPhone 13".
# The title must start with the item and continue with a preposition or a Latin model name,
# so "Дисплей разбит" or "iPhone 13 + чехол" stay devices. A dummy is never a device.
_ACCESSORY = re.compile(
    r"^(?:чехл?\w*|стекл\w*|защитн\w*|пленк\w*|дисплей|матриц\w*|корпус|крышк\w*|"
    r"аккумулятор\w*|батаре\w*|зарядк\w*|зарядн\w*|блок питания|кабель|шнур|наушник\w*|"
    r"коробк\w*|клавиатур\w*|сумк\w*|рюкзак|подставк\w*|держател\w*|шлейф\w*|"
    r"запчаст\w*)\s+(?:для|на|от|к|под|[a-z])"
    r"|\bмуляж\w*"
)
ACCESSORY = Signal(
    "accessory_not_device",
    0,
    "Похоже на аксессуар, запчасть или муляж — не сравнивается с устройствами",
    excludes_from_market=True,
)


def is_accessory(listing: Listing) -> bool:
    return _ACCESSORY.search(normalize_text(listing.title)) is not None


# "без предоплаты", "не разбит", "без блокировки" deny the problem. Negated words are
# dropped before matching, except phrases that are signals themselves.
_NEGATION = re.compile(
    r"\b(?:не|без|нет)\s+(?!документ|коробки и|чека и|работа|включа|оригинал)\w+"
)


def text_signals(listing: Listing) -> list[Signal]:
    text = _NEGATION.sub(" ", normalize_text(f"{listing.title} {listing.description or ''}"))
    found = [signal for pattern, signal in _TEXT_SIGNALS if pattern.search(text)]
    if is_accessory(listing):
        found.append(ACCESSORY)
    if listing.description is not None and len(listing.description.strip()) < 20:
        found.append(Signal("short_description", 10, "Описание очень короткое"))
    return found


def price_signals(listing: Listing, deviation: float | None) -> list[Signal]:
    if listing.price is None:
        return [Signal("missing_price", 0, "Цена не указана, сравнение с рынком невозможно")]
    if listing.price == 0:
        return [Signal("symbolic_price", 30, "Указана нулевая цена")]
    if deviation is None:
        return []
    if deviation <= FAR_BELOW:
        return [
            Signal(
                "price_far_below_market",
                45,
                f"Цена на {-deviation:.0f}% ниже медианы сопоставимых объявлений",
            )
        ]
    if deviation <= BELOW:
        return [
            Signal(
                "price_below_market",
                20,
                f"Цена на {-deviation:.0f}% ниже медианы сопоставимых объявлений",
            )
        ]
    if deviation >= FAR_ABOVE:
        return [
            Signal(
                "price_far_above_market",
                10,
                f"Цена на {deviation:.0f}% выше медианы сопоставимых объявлений",
            )
        ]
    return []


def score(signals: list[Signal]) -> int:
    return min(100, sum(signal.weight for signal in signals))


def level(value: int) -> str:
    if value >= HIGH_FROM:
        return "high"
    return "medium" if value >= MEDIUM_FROM else "low"


def reasons(signals: list[Signal]) -> list[RiskReason]:
    return [RiskReason(code=signal.code, description=signal.description) for signal in signals]
