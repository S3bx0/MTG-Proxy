from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .duplex import back_slot_map
from .layout import compute_layout, page_slots


def draw_calibration_slot(
    c: canvas.Canvas,
    *,
    x_pt: float,
    y_pt: float,
    w_pt: float,
    h_pt: float,
    label: str,
) -> None:
    c.setLineWidth(0.9)
    c.rect(x_pt, y_pt, w_pt, h_pt, stroke=1, fill=0)

    cx = x_pt + w_pt / 2
    cy = y_pt + h_pt / 2
    mark = min(w_pt, h_pt) * 0.08
    c.line(cx - mark, cy, cx + mark, cy)
    c.line(cx, cy - mark, cx, cy + mark)

    c.setFont("Helvetica", 10)
    c.drawString(x_pt + 8, y_pt + h_pt - 14, label)
    c.setFont("Helvetica", 8)
    c.drawString(x_pt + 8, y_pt + 8, f"({x_pt/mm:.1f}mm, {y_pt/mm:.1f}mm)")


def generate_calibration_pdf(
    *,
    out_pdf,
    page_portrait: bool,
    margin_mm: float,
    gap_mm: float,
    back_placement: str,
    card_format_label: str = "MTG Proxy",
    card_w_mm: float,
    card_h_mm: float,
    front_offset_x_mm: float,
    front_offset_y_mm: float,
    back_offset_x_mm: float,
    back_offset_y_mm: float,
) -> None:
    layout = compute_layout(
        page_portrait=page_portrait,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
    )

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_pdf), pagesize=layout.page_size_pt)
    slots = page_slots(layout)
    back_map = back_slot_map(cols=layout.cols, rows=layout.rows, placement=back_placement)

    front_dx_pt = front_offset_x_mm * mm
    front_dy_pt = front_offset_y_mm * mm
    back_dx_pt = back_offset_x_mm * mm
    back_dy_pt = back_offset_y_mm * mm

    c.saveState()
    if front_dx_pt != 0.0 or front_dy_pt != 0.0:
        c.translate(front_dx_pt, front_dy_pt)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, layout.page_size_pt[1] - 12 * mm, f"{card_format_label} calibration - FRONT")
    c.setFont("Helvetica", 9)
    c.drawString(18 * mm, layout.page_size_pt[1] - 17 * mm, f"front_offset=({front_offset_x_mm:.2f}mm, {front_offset_y_mm:.2f}mm)")
    for i, (x, y) in enumerate(slots):
        draw_calibration_slot(
            c,
            x_pt=x,
            y_pt=y,
            w_pt=layout.card_w_pt,
            h_pt=layout.card_h_pt,
            label=f"F{i+1}",
        )
    c.restoreState()
    c.showPage()

    c.saveState()
    if back_dx_pt != 0.0 or back_dy_pt != 0.0:
        c.translate(back_dx_pt, back_dy_pt)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(18 * mm, layout.page_size_pt[1] - 12 * mm, f"{card_format_label} calibration - BACK")
    c.setFont("Helvetica", 9)
    c.drawString(
        18 * mm,
        layout.page_size_pt[1] - 17 * mm,
        f"back_offset=({back_offset_x_mm:.2f}mm, {back_offset_y_mm:.2f}mm), placement={back_placement}",
    )
    for i in range(len(slots)):
        x, y = slots[back_map[i]]
        draw_calibration_slot(
            c,
            x_pt=x,
            y_pt=y,
            w_pt=layout.card_w_pt,
            h_pt=layout.card_h_pt,
            label=f"B{i+1}",
        )
    c.restoreState()
    c.showPage()

    c.save()
