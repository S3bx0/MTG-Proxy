from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from reportlab.pdfgen import canvas

from .layout import Layout, page_slots, pick_best_layout
from .render import draw_card_image, load_image_for_pdf, warn_if_low_res


@dataclass(frozen=True)
class RepeatedSheetResult:
    page_orientation: str
    pages: int
    layout: Layout


def generate_repeated_front_sheet(
    *,
    image_path: Path,
    out_pdf: Path,
    copies: int,
    gap_mm: float,
    margin_mm: float,
    card_w_mm: float,
    card_h_mm: float,
) -> RepeatedSheetResult:
    if copies <= 0:
        raise ValueError("copies must be > 0")

    page_orientation, layout = pick_best_layout(
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
    )
    pages = math.ceil(copies / layout.per_page)
    slots = page_slots(layout)
    image = load_image_for_pdf(image_path, back_transform="none")

    try:
        warn_if_low_res(image, path=image_path, card_w_mm=card_w_mm, card_h_mm=card_h_mm)
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf = canvas.Canvas(str(out_pdf), pagesize=layout.page_size_pt)

        for copy_index in range(copies):
            if copy_index and copy_index % layout.per_page == 0:
                pdf.showPage()
            x_pt, y_pt = slots[copy_index % layout.per_page]
            draw_card_image(
                pdf,
                img=image,
                x_pt=x_pt,
                y_pt=y_pt,
                w_pt=layout.card_w_pt,
                h_pt=layout.card_h_pt,
                fit="cover",
            )

        pdf.save()
    finally:
        image.close()

    return RepeatedSheetResult(page_orientation=page_orientation, pages=pages, layout=layout)
