from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm

from .card_formats import DEFAULT_CARD_FORMAT

CARD_W_MM = DEFAULT_CARD_FORMAT.portrait_width_mm
CARD_H_MM = DEFAULT_CARD_FORMAT.portrait_height_mm


@dataclass(frozen=True)
class Layout:
    page_size_pt: Tuple[float, float]
    cols: int
    rows: int
    gap_pt: float
    offset_x_pt: float
    offset_y_pt: float
    card_w_pt: float
    card_h_pt: float

    @property
    def per_page(self) -> int:
        return self.cols * self.rows


def compute_layout(
    *,
    page_portrait: bool,
    margin_mm: float,
    gap_mm: float,
    card_w_mm: float = CARD_W_MM,
    card_h_mm: float = CARD_H_MM,
) -> Layout:
    if margin_mm < 0 or gap_mm < 0:
        raise ValueError("margin_mm and gap_mm must be >= 0")

    page_w_pt, page_h_pt = A4
    if not page_portrait:
        page_w_pt, page_h_pt = landscape(A4)

    card_w_pt = card_w_mm * mm
    card_h_pt = card_h_mm * mm
    margin_pt = margin_mm * mm
    gap_pt = gap_mm * mm

    avail_w = page_w_pt - 2 * margin_pt
    avail_h = page_h_pt - 2 * margin_pt
    if avail_w <= 0 or avail_h <= 0:
        raise ValueError("Margins are too large for A4")
    if card_w_pt > avail_w or card_h_pt > avail_h:
        raise ValueError("Card dimensions do not fit on A4 with the selected margins")

    cols = max(1, int(math.floor((avail_w + gap_pt) / (card_w_pt + gap_pt))))
    rows = max(1, int(math.floor((avail_h + gap_pt) / (card_h_pt + gap_pt))))

    used_w = cols * card_w_pt + (cols - 1) * gap_pt
    used_h = rows * card_h_pt + (rows - 1) * gap_pt

    extra_w = max(0.0, avail_w - used_w)
    extra_h = max(0.0, avail_h - used_h)

    offset_x = margin_pt + extra_w / 2
    offset_y = margin_pt + extra_h / 2

    return Layout(
        page_size_pt=(page_w_pt, page_h_pt),
        cols=cols,
        rows=rows,
        gap_pt=gap_pt,
        offset_x_pt=offset_x,
        offset_y_pt=offset_y,
        card_w_pt=card_w_pt,
        card_h_pt=card_h_pt,
    )


def pick_best_layout(
    *,
    margin_mm: float,
    gap_mm: float,
    card_w_mm: float = CARD_W_MM,
    card_h_mm: float = CARD_H_MM,
) -> Tuple[str, Layout]:
    portrait = compute_layout(
        page_portrait=True,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
    )
    landscape_layout = compute_layout(
        page_portrait=False,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
    )

    if landscape_layout.per_page > portrait.per_page:
        return "landscape", landscape_layout
    if portrait.per_page > landscape_layout.per_page:
        return "portrait", portrait

    def waste(layout_: Layout) -> float:
        page_w, page_h = layout_.page_size_pt
        margin_pt = margin_mm * mm
        avail_w = page_w - 2 * margin_pt
        avail_h = page_h - 2 * margin_pt
        used_w = layout_.cols * layout_.card_w_pt + (layout_.cols - 1) * layout_.gap_pt
        used_h = layout_.rows * layout_.card_h_pt + (layout_.rows - 1) * layout_.gap_pt
        return max(0.0, (avail_w - used_w)) * max(0.0, (avail_h - used_h))

    if waste(landscape_layout) < waste(portrait):
        return "landscape", landscape_layout
    return "portrait", portrait


def page_slots(layout: Layout) -> List[Tuple[float, float]]:
    slots: List[Tuple[float, float]] = []
    for r in range(layout.rows):
        for col in range(layout.cols):
            x = layout.offset_x_pt + col * (layout.card_w_pt + layout.gap_pt)
            y_from_top = layout.offset_y_pt + r * (layout.card_h_pt + layout.gap_pt)
            page_w, page_h = layout.page_size_pt
            y = page_h - y_from_top - layout.card_h_pt
            slots.append((x, y))
    return slots
