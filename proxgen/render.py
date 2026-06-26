from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, TypeVar

from PIL import Image, ImageOps
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .card_formats import DEFAULT_CARD_FORMAT
from .duplex import back_slot_map
from .layout import compute_layout, page_slots
from .pairing import build_back_list
from .quality import assess_dimensions


CARD_W_MM = DEFAULT_CARD_FORMAT.portrait_width_mm
CARD_H_MM = DEFAULT_CARD_FORMAT.portrait_height_mm


def warn_if_low_res(
    img: Image.Image,
    *,
    path: Path,
    card_w_mm: float = CARD_W_MM,
    card_h_mm: float = CARD_H_MM,
    fit: str,
) -> None:
    w_px, h_px = img.size
    dpi, crop_percent = assess_dimensions(
        width_px=w_px,
        height_px=h_px,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
        fit=fit,
    )

    if dpi < 250:
        import sys

        print(
            f"[WARN] Low resolution for print: {path.name} ({w_px}x{h_px}px, ~{dpi:.0f} DPI at {card_w_mm:.0f}x{card_h_mm:.0f}mm).",
            file=sys.stderr,
        )
    if crop_percent >= 15.0:
        import sys

        print(
            f"[WARN] Strong cover crop: {path.name} ({crop_percent:.1f}% of source area is outside the card box).",
            file=sys.stderr,
        )


def load_image_for_pdf(path: Path, *, back_transform: str) -> Image.Image:
    # Detach pixels from the source file so large batches do not retain open handles.
    with Image.open(path) as source:
        normalized = ImageOps.exif_transpose(source) or source
        mode = "RGBA" if normalized.mode == "RGBA" else "RGB"
        img = normalized.convert(mode)

    if back_transform == "none":
        return img
    if back_transform == "rotate180":
        return img.rotate(180, expand=True)
    if back_transform == "mirror-x":
        return ImageOps.mirror(img)
    if back_transform == "mirror-y":
        return ImageOps.flip(img)

    raise ValueError(f"Unknown back_transform: {back_transform}")


def draw_card_image(
    c: canvas.Canvas,
    *,
    img: Image.Image,
    x_pt: float,
    y_pt: float,
    w_pt: float,
    h_pt: float,
    fit: str,
) -> None:
    iw, ih = img.size
    if iw <= 0 or ih <= 0:
        return

    c.saveState()
    clip = c.beginPath()
    clip.rect(x_pt, y_pt, w_pt, h_pt)
    c.clipPath(clip, stroke=0, fill=0)

    if fit == "contain":
        scale = min(w_pt / iw, h_pt / ih)
        dw, dh = iw * scale, ih * scale
        dx = x_pt + (w_pt - dw) / 2
        dy = y_pt + (h_pt - dh) / 2
        c.drawImage(ImageReader(img), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        c.restoreState()
        return

    if fit == "cover":
        scale = max(w_pt / iw, h_pt / ih)
        dw, dh = iw * scale, ih * scale
        dx = x_pt + (w_pt - dw) / 2
        dy = y_pt + (h_pt - dh) / 2
        c.drawImage(ImageReader(img), dx, dy, width=dw, height=dh, preserveAspectRatio=True, mask="auto")
        c.restoreState()
        return

    c.restoreState()
    raise ValueError(f"Unknown fit mode: {fit}")


T = TypeVar("T")


def chunked(seq: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def generate_pdf(
    *,
    front_paths: List[Path],
    back_paths: List[Path],
    out_pdf: Path,
    page_portrait: bool,
    margin_mm: float,
    gap_mm: float,
    fit: str,
    duplex_mode: str,
    back_pairing: str,
    back_transform: str,
    back_placement: str,
    card_w_mm: float = CARD_W_MM,
    card_h_mm: float = CARD_H_MM,
    front_offset_x_mm: float = 0.0,
    front_offset_y_mm: float = 0.0,
    back_offset_x_mm: float = 0.0,
    back_offset_y_mm: float = 0.0,
) -> None:
    layout = compute_layout(
        page_portrait=page_portrait,
        margin_mm=margin_mm,
        gap_mm=gap_mm,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
    )
    if layout.per_page <= 0:
        raise RuntimeError("Invalid layout")

    backs_expanded = build_back_list(front_paths, back_paths, back_pairing=back_pairing)

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out_pdf), pagesize=layout.page_size_pt)

    slots = page_slots(layout)
    back_map = back_slot_map(cols=layout.cols, rows=layout.rows, placement=back_placement)

    front_dx_pt = front_offset_x_mm * mm
    front_dy_pt = front_offset_y_mm * mm
    back_dx_pt = back_offset_x_mm * mm
    back_dy_pt = back_offset_y_mm * mm

    pairs = list(zip(front_paths, backs_expanded))

    if duplex_mode == "paired":
        for page_pairs in chunked(pairs, layout.per_page):
            c.saveState()
            if front_dx_pt != 0.0 or front_dy_pt != 0.0:
                c.translate(front_dx_pt, front_dy_pt)
            for i, (front_p, _back_p) in enumerate(page_pairs):
                img = load_image_for_pdf(front_p, back_transform="none")
                warn_if_low_res(img, path=front_p, card_w_mm=card_w_mm, card_h_mm=card_h_mm, fit=fit)
                x, y = slots[i]
                draw_card_image(c, img=img, x_pt=x, y_pt=y, w_pt=layout.card_w_pt, h_pt=layout.card_h_pt, fit=fit)
            c.restoreState()
            c.showPage()

            c.saveState()
            if back_dx_pt != 0.0 or back_dy_pt != 0.0:
                c.translate(back_dx_pt, back_dy_pt)
            for i, (_front_p, back_p) in enumerate(page_pairs):
                img = load_image_for_pdf(back_p, back_transform=back_transform)
                warn_if_low_res(img, path=back_p, card_w_mm=card_w_mm, card_h_mm=card_h_mm, fit=fit)
                x, y = slots[back_map[i]]
                draw_card_image(c, img=img, x_pt=x, y_pt=y, w_pt=layout.card_w_pt, h_pt=layout.card_h_pt, fit=fit)
            c.restoreState()
            c.showPage()

        c.save()
        return

    if duplex_mode == "separate":
        front_pages = list(chunked(front_paths, layout.per_page))
        back_pages = list(chunked(backs_expanded, layout.per_page))

        for page_fronts in front_pages:
            c.saveState()
            if front_dx_pt != 0.0 or front_dy_pt != 0.0:
                c.translate(front_dx_pt, front_dy_pt)
            for i, front_p in enumerate(page_fronts):
                img = load_image_for_pdf(front_p, back_transform="none")
                warn_if_low_res(img, path=front_p, card_w_mm=card_w_mm, card_h_mm=card_h_mm, fit=fit)
                x, y = slots[i]
                draw_card_image(c, img=img, x_pt=x, y_pt=y, w_pt=layout.card_w_pt, h_pt=layout.card_h_pt, fit=fit)
            c.restoreState()
            c.showPage()

        for page_backs in back_pages:
            c.saveState()
            if back_dx_pt != 0.0 or back_dy_pt != 0.0:
                c.translate(back_dx_pt, back_dy_pt)
            for i, back_p in enumerate(page_backs):
                img = load_image_for_pdf(back_p, back_transform=back_transform)
                warn_if_low_res(img, path=back_p, card_w_mm=card_w_mm, card_h_mm=card_h_mm, fit=fit)
                x, y = slots[back_map[i]]
                draw_card_image(c, img=img, x_pt=x, y_pt=y, w_pt=layout.card_w_pt, h_pt=layout.card_h_pt, fit=fit)
            c.restoreState()
            c.showPage()

        c.save()
        return

    raise ValueError(f"Unknown duplex_mode: {duplex_mode}")
