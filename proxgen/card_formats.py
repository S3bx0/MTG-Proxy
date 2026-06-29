from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardFormat:
    key: str
    label: str
    portrait_width_mm: float
    portrait_height_mm: float


PLANECHASE = CardFormat(
    key="planechase",
    label="Planechase",
    portrait_width_mm=88.0,
    portrait_height_mm=126.0,
)
STANDARD_MTG = CardFormat(
    key="standard",
    label="Standard MTG",
    portrait_width_mm=63.5,
    portrait_height_mm=88.9,
)

CARD_FORMATS: dict[str, CardFormat] = {
    PLANECHASE.key: PLANECHASE,
    STANDARD_MTG.key: STANDARD_MTG,
}
DEFAULT_CARD_FORMAT = PLANECHASE


def get_card_format(key: str) -> CardFormat:
    normalized = key.lower().strip()
    try:
        return CARD_FORMATS[normalized]
    except KeyError as exc:
        choices = "|".join(sorted(CARD_FORMATS))
        raise ValueError(f"card_format must be {choices}") from exc
