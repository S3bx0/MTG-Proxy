from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

from PIL import Image, ImageOps

from .card_formats import CARD_FORMATS, CardFormat, DEFAULT_CARD_FORMAT, get_card_format
from .calibration import generate_calibration_pdf
from .config import load_config_json, write_config_json
from .duplex import resolve_back_placement
from .layout import compute_layout, pick_best_layout
from .pairing import (
    append_rename_history_entry,
    apply_strict_rename_plan,
    build_powershell_rename_script,
    build_strict_rename_plan,
    undo_last_rename_batch,
    write_powershell_rename_script,
)
from .quality import assess_unique_images, preflight_level
from .render import generate_pdf


APP_VERSION = "1.3.0"

REF_PX_PER_MM = 11.81
SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}


def iter_images_sorted(folder: Path) -> List[Path]:
    if not folder.exists():
        raise FileNotFoundError(f"Folder not found: {folder}")

    files: List[Path] = []
    for p in folder.iterdir():
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)

    files.sort(key=lambda p: p.name.lower())
    return files


def ref_px_for_mm(w_mm: float, h_mm: float) -> Tuple[int, int]:
    return int(round(w_mm * REF_PX_PER_MM)), int(round(h_mm * REF_PX_PER_MM))


def resolve_card_dimensions_mm(
    *,
    card_format: CardFormat,
    card_orientation: str,
    fronts: List[Path],
) -> Tuple[str, float, float]:
    card_orientation = card_orientation.lower().strip()
    if card_orientation == "portrait":
        return "portrait", card_format.portrait_width_mm, card_format.portrait_height_mm
    if card_orientation == "landscape":
        return "landscape", card_format.portrait_height_mm, card_format.portrait_width_mm

    if card_orientation != "auto":
        raise ValueError("card_orientation must be auto|portrait|landscape")

    sample = fronts[: min(12, len(fronts))]
    if not sample:
        return "portrait", card_format.portrait_width_mm, card_format.portrait_height_mm

    landscape_votes = 0
    portrait_votes = 0

    for pth in sample:
        try:
            with Image.open(pth) as source:
                im = ImageOps.exif_transpose(source) or source
                w, h = im.size
            if w >= h:
                landscape_votes += 1
            else:
                portrait_votes += 1
        except Exception:
            continue

    if landscape_votes >= portrait_votes:
        return "landscape", card_format.portrait_height_mm, card_format.portrait_width_mm
    return "portrait", card_format.portrait_width_mm, card_format.portrait_height_mm


def parse_args_with_config(argv: Sequence[str]) -> argparse.Namespace:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--config", type=Path, default=None, help="Optional JSON config file")
    pre_ns, _ = pre.parse_known_args(argv)

    config_path: Path | None = pre_ns.config
    if config_path is None:
        candidate = Path("settings.json")
        if candidate.exists():
            config_path = candidate

    config: dict = {}
    if config_path is not None:
        config = load_config_json(config_path)
        print(f"Loaded config: {config_path}")

    p = argparse.ArgumentParser(
        description=(
            "MTG Proxy PDF generator (A4)\n"
            "- Reads JPG/PNG from front and back folders\n"
            "- Supports Planechase (88x126mm) and standard MTG (63x88mm) cards\n"
            "- Exports a print-ready PDF for duplex printing"
        )
    )

    p.add_argument("--version", action="version", version=f"MTG ProxyGen {APP_VERSION}")

    p.add_argument("--config", type=Path, default=config_path, help="Optional JSON config file")
    p.add_argument(
        "--write-config",
        nargs="?",
        default=None,
        const="",
        help=(
            "Write effective settings back to a JSON config file (optional path). "
            "If you pass the flag without a value, it writes to --config if set, otherwise settings.json."
        ),
    )
    p.add_argument("--print-settings", action="store_true", help="Print a short duplex printing checklist (does not change output).")
    p.add_argument("--dry-run", action="store_true", help="Do everything except generating the PDF (shows chosen layout and estimated page count).")
    p.add_argument("--preflight", action="store_true", help="Analyze effective print DPI and cover crop without generating a PDF.")
    p.add_argument("--calibration-sheet", action="store_true", help="Generate a 2-page calibration PDF (front/back slot markers) instead of card images.")
    p.add_argument("--suggest-back-renames", action="store_true", help="Print suggested back filenames to satisfy strict pairing.")
    p.add_argument(
        "--write-rename-script",
        nargs="?",
        default=None,
        const="",
        help="Write suggested strict-pairing renames to a PowerShell script (.ps1). Optional path.",
    )
    p.add_argument("--apply-back-renames", action="store_true", help="Apply suggested back renames in back directory (safe dry-run unless --yes).")
    p.add_argument("--undo-back-renames", action="store_true", help="Undo last applied back-rename batch (safe dry-run unless --yes).")
    p.add_argument(
        "--rename-history-file",
        type=Path,
        default=Path("output/rename_history.jsonl"),
        help="Path to rename history file used for undo operations.",
    )
    p.add_argument("--yes", action="store_true", help="Confirm destructive actions like --apply-back-renames.")

    p.add_argument("--front-dir", type=Path, default=Path(config.get("front_dir", "input/front")), help="Folder with front images")
    p.add_argument("--back-dir", type=Path, default=Path(config.get("back_dir", "input/back")), help="Folder with back images")
    p.add_argument("--out", type=Path, default=Path(config.get("out", "output/planechase_proxies.pdf")), help="Output PDF path")
    p.add_argument(
        "--card-format",
        choices=sorted(CARD_FORMATS),
        default=str(config.get("card_format", DEFAULT_CARD_FORMAT.key)),
        help="Card size: planechase (88x126mm) or standard (63x88mm).",
    )

    p.add_argument("--gap-mm", type=float, default=float(config.get("gap_mm", 3.0)), help="Gap between cards in mm (recommended 2-3)")
    p.add_argument("--margin-mm", type=float, default=float(config.get("margin_mm", 5.0)), help="Page margin in mm (printer safe area). Use 0 for borderless printers.")
    p.add_argument("--min-dpi", type=float, default=float(config.get("min_dpi", 300.0)), help="Target effective DPI used by --preflight (default: 300)")

    p.add_argument("--page", choices=["auto", "portrait", "landscape"], default=str(config.get("page", "auto")), help="A4 orientation. 'auto' picks the layout with the most cards per page.")
    p.add_argument("--fit", choices=["contain", "cover"], default=str(config.get("fit", "cover")), help="How to fit images into the selected card box")
    p.add_argument("--card-orientation", choices=["auto", "portrait", "landscape"], default=str(config.get("card_orientation", "auto")), help="Card orientation. 'auto' detects it from front images.")
    p.add_argument("--duplex-mode", choices=["paired", "separate"], default=str(config.get("duplex_mode", "paired")), help="'paired' = page1 fronts, page2 backs (aligned). 'separate' = all fronts then all backs.")
    p.add_argument("--back-pairing", choices=["smart", "strict"], default=str(config.get("back_pairing", "smart")), help="How to match back images to fronts: smart (fallbacks) or strict (name-matching required).")
    p.add_argument("--back-transform", choices=["none", "rotate180", "mirror-x", "mirror-y"], default=str(config.get("back_transform", "rotate180")), help="Transform backs to match your printer duplex behavior.")
    p.add_argument("--back-placement", choices=["auto", "same", "mirror-x", "mirror-y", "rotate180"], default=str(config.get("back_placement", "auto")), help="How to place backs on the page grid for duplex alignment. 'auto' picks mirror-x for portrait pages and mirror-y for landscape pages.")

    p.add_argument("--front-offset-x-mm", type=float, default=float(config.get("front_offset_x_mm", 0.0)), help="Fine duplex calibration: shift fronts horizontally by mm (+right, -left).")
    p.add_argument("--front-offset-y-mm", type=float, default=float(config.get("front_offset_y_mm", 0.0)), help="Fine duplex calibration: shift fronts vertically by mm (+up, -down).")
    p.add_argument("--back-offset-x-mm", type=float, default=float(config.get("back_offset_x_mm", 0.0)), help="Fine duplex calibration: shift backs horizontally by mm (+right, -left).")
    p.add_argument("--back-offset-y-mm", type=float, default=float(config.get("back_offset_y_mm", 0.0)), help="Fine duplex calibration: shift backs vertically by mm (+up, -down).")

    return p.parse_args(argv)


def build_effective_config_dict(args: argparse.Namespace) -> dict:
    return {
        "front_dir": str(args.front_dir).replace("\\\\", "/"),
        "back_dir": str(args.back_dir).replace("\\\\", "/"),
        "out": str(args.out).replace("\\\\", "/"),
        "page": args.page,
        "gap_mm": float(args.gap_mm),
        "margin_mm": float(args.margin_mm),
        "min_dpi": float(args.min_dpi),
        "card_format": args.card_format,
        "card_orientation": args.card_orientation,
        "fit": args.fit,
        "duplex_mode": args.duplex_mode,
        "back_pairing": args.back_pairing,
        "back_transform": args.back_transform,
        "back_placement": args.back_placement,
        "front_offset_x_mm": float(args.front_offset_x_mm),
        "front_offset_y_mm": float(args.front_offset_y_mm),
        "back_offset_x_mm": float(args.back_offset_x_mm),
        "back_offset_y_mm": float(args.back_offset_y_mm),
    }


def print_duplex_checklist(*, duplex_mode: str, back_placement: str, back_transform: str) -> None:
    print("\n=== PRINT SETTINGS (duplex checklist) ===")
    print("PDF viewer:")
    print("- Scale: 100% / Actual size (NO 'Fit to page')")
    print("- Page sizing: do not shrink / do not expand")
    print("Printer driver:")
    print("- Disable any extra scaling / centering / 'fit to printable area'")
    print("- Duplex: flip on LONG edge (typical for A4)")
    print("ProxyGen settings:")
    print(f"- duplex_mode={duplex_mode}")
    print(f"- back_placement={back_placement} (slot mapping)")
    print(f"- back_transform={back_transform} (image orientation)")
    print("\nTip: If alignment drifts between prints, that's printer duplex registration variability.")


def print_quality_preflight(
    *,
    image_paths: List[Path],
    card_w_mm: float,
    card_h_mm: float,
    fit: str,
    min_dpi: float,
) -> None:
    assessments = assess_unique_images(
        image_paths,
        card_w_mm=card_w_mm,
        card_h_mm=card_h_mm,
        fit=fit,
    )
    print("\n=== IMAGE QUALITY PREFLIGHT ===")
    print(f"Target: {card_w_mm:.1f}x{card_h_mm:.1f}mm, fit={fit}, target DPI={min_dpi:.0f}")

    counts = {"OK": 0, "WARN": 0, "LOW": 0}
    for item in assessments:
        level = preflight_level(
            effective_dpi=item.effective_dpi,
            crop_percent=item.crop_percent,
            min_dpi=min_dpi,
        )
        counts[level] += 1
        crop_note = f", cover crop={item.crop_percent:.1f}%" if item.crop_percent > 0.05 else ""
        print(
            f"[{level}] {item.path.name}: {item.width_px}x{item.height_px}px, "
            f"effective={item.effective_dpi:.0f} DPI{crop_note}"
        )

    print(f"Summary: {len(assessments)} unique image(s), OK={counts['OK']} WARN={counts['WARN']} LOW={counts['LOW']}")
    print("Note: effective DPI is calculated after scaling to the physical card size; embedded DPI metadata is ignored.")


def estimate_total_pages(*, fronts_count: int, per_page: int, duplex_mode: str) -> Tuple[int, int, int]:
    if per_page <= 0:
        raise ValueError("per_page must be > 0")
    front_pages = int(math.ceil(fronts_count / per_page))
    if duplex_mode not in {"paired", "separate"}:
        raise ValueError(f"Unknown duplex_mode: {duplex_mode}")
    back_pages = front_pages
    total = front_pages + back_pages
    return front_pages, back_pages, total


def main(argv: Sequence[str]) -> int:
    args = parse_args_with_config(argv)

    if args.out.suffix.lower() != ".pdf":
        print(f"[WARN] Output file does not end with .pdf: {args.out}", file=sys.stderr)

    if args.undo_back_renames:
        undo_result = undo_last_rename_batch(
            history_path=args.rename_history_file,
            back_dir=args.back_dir,
            apply_changes=bool(args.yes),
        )

        print("=== UNDO RENAME PLAN ===")
        print(f"history_file={args.rename_history_file}")

        if undo_result.no_history:
            print("No rename history found for this back directory.")
            return 0

        print(f"mode={'APPLY' if args.yes and not undo_result.conflicts else 'DRY-RUN'} actions={len(undo_result.actions)}")
        for action in undo_result.actions:
            print(f"- {action.source.name} -> {action.target.name}")

        if undo_result.conflicts:
            print("Conflicts:")
            for conflict_msg in undo_result.conflicts:
                print(f"- {conflict_msg}")
            print("No files renamed due to conflicts.")

        if args.yes and not undo_result.conflicts:
            print(f"Undo renamed files: {undo_result.applied}")
        elif not args.yes:
            print("Dry-run only. Re-run with --yes to apply undo.")
        return 0

    if args.suggest_back_renames or args.write_rename_script is not None or args.apply_back_renames:
        try:
            fronts = iter_images_sorted(args.front_dir)
            backs = iter_images_sorted(args.back_dir)
        except Exception as e:
            print(f"Input error: {e}", file=sys.stderr)
            return 2

        plan = build_strict_rename_plan(fronts, backs)
        print("=== STRICT PAIRING RENAME SUGGESTIONS ===")
        print(f"fronts={len(fronts)} backs={len(backs)} already_matched={plan.already_matched}")

        if plan.duplicate_back_keys:
            print("Duplicate back name keys:")
            for key in plan.duplicate_back_keys:
                print(f"- {key}")

        if plan.suggestions:
            print("Suggested renames:")
            for suggestion in plan.suggestions:
                print(f"- {suggestion.source.name} -> {suggestion.target_name}")
        else:
            print("No rename suggestions needed.")

        if plan.missing_fronts:
            print("Missing backs for fronts:")
            for name in plan.missing_fronts[:20]:
                print(f"- {name}")
            if len(plan.missing_fronts) > 20:
                print(f"... +{len(plan.missing_fronts) - 20} more")

        if args.write_rename_script is not None:
            if args.write_rename_script == "":
                script_path = Path("output/rename_back_files.ps1")
            else:
                script_path = Path(args.write_rename_script)

            script_content = build_powershell_rename_script(plan=plan, back_dir=args.back_dir)
            write_powershell_rename_script(path=script_path, content=script_content)
            print(f"Wrote rename script: {script_path}")

        if args.apply_back_renames:
            apply_result = apply_strict_rename_plan(
                plan=plan,
                back_dir=args.back_dir,
                apply_changes=bool(args.yes),
            )

            print("=== APPLY RENAME PLAN ===")
            print(f"mode={'APPLY' if args.yes and not apply_result.conflicts else 'DRY-RUN'} actions={len(apply_result.actions)}")

            for action in apply_result.actions:
                print(f"- {action.source.name} -> {action.target.name}")

            if apply_result.skipped_same_name:
                print(f"Skipped (already matching name): {apply_result.skipped_same_name}")

            if apply_result.conflicts:
                print("Conflicts:")
                for conflict_msg in list(apply_result.conflicts):
                    print(f"- {conflict_msg}")
                print("No files renamed due to conflicts.")

            if args.yes and not apply_result.conflicts:
                print(f"Renamed files: {apply_result.applied}")
                if apply_result.applied > 0:
                    append_rename_history_entry(
                        history_path=args.rename_history_file,
                        back_dir=args.back_dir,
                        actions=apply_result.actions,
                    )
                    print(f"History updated: {args.rename_history_file}")
            elif not args.yes:
                print("Dry-run only. Re-run with --yes to apply changes.")

        return 0

    if args.calibration_sheet:
        try:
            card_format = get_card_format(args.card_format)
            card_label, card_w_mm, card_h_mm = resolve_card_dimensions_mm(
                card_format=card_format,
                card_orientation=args.card_orientation,
                fronts=[],
            )
        except Exception as e:
            print(f"Card orientation error: {e}", file=sys.stderr)
            return 2

        try:
            if args.page == "auto":
                page_label, layout = pick_best_layout(
                    margin_mm=args.margin_mm,
                    gap_mm=args.gap_mm,
                    card_w_mm=card_w_mm,
                    card_h_mm=card_h_mm,
                )
                page_portrait = page_label == "portrait"
            else:
                page_label = args.page
                page_portrait = args.page == "portrait"
                layout = compute_layout(
                    page_portrait=page_portrait,
                    margin_mm=args.margin_mm,
                    gap_mm=args.gap_mm,
                    card_w_mm=card_w_mm,
                    card_h_mm=card_h_mm,
                )
        except Exception as e:
            print(f"Layout error: {e}", file=sys.stderr)
            return 2

        try:
            effective_back_placement = resolve_back_placement(
                back_placement=args.back_placement,
                page_portrait=page_portrait,
            )
        except Exception as e:
            print(f"Back placement error: {e}", file=sys.stderr)
            return 2

        print(
            f"Calibration layout A4 {page_label}: {layout.cols}x{layout.rows} = {layout.per_page} slots/page "
            f"(gap={args.gap_mm}mm margin={args.margin_mm}mm)"
        )
        print(f"Card format: {card_format.label}; orientation: {card_label}")
        print(
            f"Calibration settings: back_placement={effective_back_placement} "
            f"front_offset=({args.front_offset_x_mm},{args.front_offset_y_mm})mm "
            f"back_offset=({args.back_offset_x_mm},{args.back_offset_y_mm})mm"
        )

        if args.dry_run:
            print("\n=== DRY RUN (no PDF generated) ===")
            print(f"Would write calibration sheet: {args.out}")
            print("Pages: 2 (front markers + back markers)")
            return 0

        try:
            generate_calibration_pdf(
                out_pdf=args.out,
                page_portrait=page_portrait,
                margin_mm=args.margin_mm,
                gap_mm=args.gap_mm,
                back_placement=effective_back_placement,
                card_format_label=card_format.label,
                card_w_mm=card_w_mm,
                card_h_mm=card_h_mm,
                front_offset_x_mm=args.front_offset_x_mm,
                front_offset_y_mm=args.front_offset_y_mm,
                back_offset_x_mm=args.back_offset_x_mm,
                back_offset_y_mm=args.back_offset_y_mm,
            )
        except Exception as e:
            print(f"Calibration generation error: {e}", file=sys.stderr)
            return 2

        print(f"Saved calibration sheet: {args.out}")
        return 0

    try:
        fronts = iter_images_sorted(args.front_dir)
    except Exception as e:
        print(f"Front folder error: {e}", file=sys.stderr)
        return 2
    if len(fronts) == 0:
        print(f"No images found in {args.front_dir}", file=sys.stderr)
        return 2

    try:
        backs = iter_images_sorted(args.back_dir)
    except Exception as e:
        print(f"Back folder error: {e}", file=sys.stderr)
        return 2

    try:
        card_format = get_card_format(args.card_format)
        card_label, card_w_mm, card_h_mm = resolve_card_dimensions_mm(
            card_format=card_format,
            card_orientation=args.card_orientation,
            fronts=fronts,
        )
    except Exception as e:
        print(f"Card orientation error: {e}", file=sys.stderr)
        return 2

    try:
        if args.page == "auto":
            page_label, layout = pick_best_layout(
                margin_mm=args.margin_mm,
                gap_mm=args.gap_mm,
                card_w_mm=card_w_mm,
                card_h_mm=card_h_mm,
            )
            page_portrait = page_label == "portrait"
        else:
            page_label = args.page
            page_portrait = args.page == "portrait"
            layout = compute_layout(
                page_portrait=page_portrait,
                margin_mm=args.margin_mm,
                gap_mm=args.gap_mm,
                card_w_mm=card_w_mm,
                card_h_mm=card_h_mm,
            )
    except Exception as e:
        print(f"Layout error: {e}", file=sys.stderr)
        return 2

    print(
        f"Layout A4 {page_label}: {layout.cols}x{layout.rows} = {layout.per_page} cards/page (gap={args.gap_mm}mm margin={args.margin_mm}mm)"
    )
    print(f"Card format: {card_format.label}; orientation: {card_label}")
    ref_w_px, ref_h_px = ref_px_for_mm(card_w_mm, card_h_mm)
    print(f"Card size: {card_w_mm}x{card_h_mm}mm (reference ~{ref_w_px}x{ref_h_px}px @300DPI)")

    try:
        effective_back_placement = resolve_back_placement(
            back_placement=args.back_placement,
            page_portrait=page_portrait,
        )
    except Exception as e:
        print(f"Back placement error: {e}", file=sys.stderr)
        return 2

    if args.back_placement == "auto":
        print(f"Resolved back_placement: {effective_back_placement} (page={page_label})")
    elif page_label == "landscape" and args.back_placement == "mirror-x":
        print(
            "[WARN] page=landscape with back_placement=mirror-x may cause duplex slot mismatch. "
            "For long-edge duplex, try back_placement=mirror-y or auto.",
            file=sys.stderr,
        )
    elif page_label == "portrait" and args.back_placement == "mirror-y":
        print(
            "[WARN] page=portrait with back_placement=mirror-y may cause duplex slot mismatch. "
            "For long-edge duplex, try back_placement=mirror-x or auto.",
            file=sys.stderr,
        )

    print(
        "Settings: "
        f"card_format={args.card_format} fit={args.fit} duplex_mode={args.duplex_mode} "
        f"back_pairing={args.back_pairing} "
        f"back_transform={args.back_transform} back_placement={effective_back_placement} "
        f"front_offset_x_mm={args.front_offset_x_mm} front_offset_y_mm={args.front_offset_y_mm} "
        f"back_offset_x_mm={args.back_offset_x_mm} back_offset_y_mm={args.back_offset_y_mm} min_dpi={args.min_dpi}"
    )
    print(f"Inputs: fronts={len(fronts)} backs={len(backs)}")

    if args.min_dpi <= 0:
        print("Quality error: min_dpi must be > 0", file=sys.stderr)
        return 2

    if args.preflight:
        try:
            print_quality_preflight(
                image_paths=fronts + backs,
                card_w_mm=card_w_mm,
                card_h_mm=card_h_mm,
                fit=args.fit,
                min_dpi=args.min_dpi,
            )
        except Exception as e:
            print(f"Quality preflight error: {e}", file=sys.stderr)
            return 2
        return 0

    if args.write_config is not None:
        if args.write_config == "":
            cfg_path = args.config if args.config is not None else Path("settings.json")
        else:
            cfg_path = Path(args.write_config)
        try:
            write_config_json(cfg_path, build_effective_config_dict(args))
            print(f"Wrote config: {cfg_path}")
        except Exception as e:
            print(f"Config write error: {e}", file=sys.stderr)
            return 2

    if args.print_settings:
        print_duplex_checklist(
            duplex_mode=args.duplex_mode,
            back_placement=effective_back_placement,
            back_transform=args.back_transform,
        )

    if args.dry_run:
        front_pages, back_pages, total_pages = estimate_total_pages(
            fronts_count=len(fronts),
            per_page=layout.per_page,
            duplex_mode=args.duplex_mode,
        )
        print("\n=== DRY RUN (no PDF generated) ===")
        print(f"Would write: {args.out}")
        print(f"Front pages: {front_pages}")
        print(f"Back pages:  {back_pages}")
        print(f"Total pages: {total_pages}")
        return 0

    try:
        generate_pdf(
            front_paths=fronts,
            back_paths=backs,
            out_pdf=args.out,
            page_portrait=page_portrait,
            margin_mm=args.margin_mm,
            gap_mm=args.gap_mm,
            fit=args.fit,
            duplex_mode=args.duplex_mode,
            back_pairing=args.back_pairing,
            back_transform=args.back_transform,
            back_placement=effective_back_placement,
            card_w_mm=card_w_mm,
            card_h_mm=card_h_mm,
            front_offset_x_mm=args.front_offset_x_mm,
            front_offset_y_mm=args.front_offset_y_mm,
            back_offset_x_mm=args.back_offset_x_mm,
            back_offset_y_mm=args.back_offset_y_mm,
        )
    except Exception as e:
        print(f"Generation error: {e}", file=sys.stderr)
        return 2

    print(f"Saved: {args.out}")
    return 0
