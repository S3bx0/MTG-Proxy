from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps


@dataclass(frozen=True)
class ImageQuality:
    path: Path
    width_px: int
    height_px: int
    effective_dpi: float
    crop_percent: float


def assess_dimensions(
    *,
    width_px: int,
    height_px: int,
    card_w_mm: float,
    card_h_mm: float,
    fit: str,
) -> tuple[float, float]:
    if width_px <= 0 or height_px <= 0:
        raise ValueError("Image dimensions must be positive")
    if card_w_mm <= 0 or card_h_mm <= 0:
        raise ValueError("Card dimensions must be positive")
    if fit not in {"contain", "cover"}:
        raise ValueError("fit must be contain|cover")

    width_mm_per_px = card_w_mm / width_px
    height_mm_per_px = card_h_mm / height_px
    scale_mm_per_px = max(width_mm_per_px, height_mm_per_px) if fit == "cover" else min(width_mm_per_px, height_mm_per_px)
    effective_dpi = 25.4 / scale_mm_per_px

    if fit == "contain":
        return effective_dpi, 0.0

    rendered_w_mm = width_px * scale_mm_per_px
    rendered_h_mm = height_px * scale_mm_per_px
    visible_fraction = (card_w_mm * card_h_mm) / (rendered_w_mm * rendered_h_mm)
    crop_percent = max(0.0, 100.0 * (1.0 - visible_fraction))
    return effective_dpi, crop_percent


def assess_image(*, path: Path, card_w_mm: float, card_h_mm: float, fit: str) -> ImageQuality:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source) or source
        width_px, height_px = image.size

    effective_dpi, crop_percent = assess_dimensions(
        width_px=width_px,
        height_px=height_px,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
        fit=fit,
    )
    return ImageQuality(
        path=path,
        width_px=width_px,
        height_px=height_px,
        effective_dpi=effective_dpi,
        crop_percent=crop_percent,
    )


def assess_unique_images(
    paths: Iterable[Path],
    *,
    card_w_mm: float,
    card_h_mm: float,
    fit: str,
) -> list[ImageQuality]:
    unique_paths = sorted({Path(path) for path in paths}, key=lambda path: path.name.lower())
    return [
        assess_image(path=path, card_w_mm=card_w_mm, card_h_mm=card_h_mm, fit=fit)
        for path in unique_paths
    ]


def quality_level(*, effective_dpi: float, min_dpi: float) -> str:
    if min_dpi <= 0:
        raise ValueError("min_dpi must be > 0")
    # Pixel dimensions are integers, so a nominal 300 DPI export can land a fraction below 300.
    if effective_dpi >= min_dpi * 0.995:
        return "OK"
    if effective_dpi >= min_dpi * 0.8:
        return "WARN"
    return "LOW"


def preflight_level(*, effective_dpi: float, crop_percent: float, min_dpi: float) -> str:
    level = quality_level(effective_dpi=effective_dpi, min_dpi=min_dpi)
    if level == "OK" and crop_percent >= 15.0:
        return "WARN"
    return level
