from __future__ import annotations

import io
import re
import secrets
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from statistics import mean
from threading import Lock
from typing import List, Optional, Tuple

from flask import Flask, Response, flash, render_template, request, send_from_directory, session

import planechase_proxygen
from proxgen.card_formats import CARD_FORMATS, DEFAULT_CARD_FORMAT


APP_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = APP_ROOT / "output"
SETTINGS_PATH = APP_ROOT / "settings.json"
PT_PER_MM = 72.0 / 25.4
PROXYGEN_RUN_LOCK = Lock()


UI_DEFAULTS = {
    "out_name": "planechase_gui.pdf",
    "page": "auto",
    "fit": "cover",
    "card_format": DEFAULT_CARD_FORMAT.key,
    "card_orientation": "auto",
    "duplex_mode": "paired",
    "back_pairing": "smart",
    "back_transform": "rotate180",
    "back_placement": "auto",
    "gap_mm": "3.0",
    "margin_mm": "5.0",
    "front_offset_x_mm": "0.0",
    "front_offset_y_mm": "0.0",
    "back_offset_x_mm": "0.0",
    "back_offset_y_mm": "0.0",
}


def normalize_output_name(value: object) -> str:
    output_name = str(value or "").strip() or "planechase_gui.pdf"
    path = Path(output_name)
    if (
        not output_name
        or path.name != output_name
        or path.drive
        or path.is_absolute()
        or "/" in output_name
        or "\\" in output_name
    ):
        raise ValueError("Nazwa pliku musi być samą nazwą bez folderów.")
    if path.suffix.lower() != ".pdf":
        raise ValueError("Plik wynikowy musi mieć rozszerzenie .pdf.")
    return output_name


def run_proxygen(argv: List[str]) -> Tuple[int, str]:
    """Run planechase_proxygen.main(argv) and capture stdout/stderr."""

    buf_out = io.StringIO()
    buf_err = io.StringIO()

    try:
        # stdout/stderr are process-wide; serialize runs so concurrent requests do not mix logs.
        with PROXYGEN_RUN_LOCK:
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                code = int(planechase_proxygen.main(argv))
    except SystemExit as e:
        code = int(getattr(e, "code", 1) or 0)
    except Exception:
        code = 1
        buf_err.write("\n" + traceback.format_exc() + "\n")

    out = buf_out.getvalue()
    err = buf_err.getvalue()
    combined = out
    if err.strip():
        combined += "\n" + err
    return code, combined.strip()


def build_common_args(form: dict) -> List[str]:
    args: List[str] = []

    out_name = normalize_output_name(form.get("out_name"))

    # Always write into output/ to keep things simple.
    out_path = OUTPUT_DIR / out_name
    args += ["--out", str(out_path)]

    # Numeric options
    for key, flag in [
        ("gap_mm", "--gap-mm"),
        ("margin_mm", "--margin-mm"),
        ("front_offset_x_mm", "--front-offset-x-mm"),
        ("front_offset_y_mm", "--front-offset-y-mm"),
        ("back_offset_x_mm", "--back-offset-x-mm"),
        ("back_offset_y_mm", "--back-offset-y-mm"),
    ]:
        val = (form.get(key) or "").strip()
        if val:
            args += [flag, val]

    # Enum options
    for key, flag, allowed in [
        ("page", "--page", {"auto", "portrait", "landscape"}),
        ("fit", "--fit", {"contain", "cover"}),
        ("card_format", "--card-format", set(CARD_FORMATS)),
        ("card_orientation", "--card-orientation", {"auto", "portrait", "landscape"}),
        ("duplex_mode", "--duplex-mode", {"paired", "separate"}),
        ("back_pairing", "--back-pairing", {"smart", "strict"}),
        ("back_transform", "--back-transform", {"none", "rotate180", "mirror-x", "mirror-y"}),
        ("back_placement", "--back-placement", {"auto", "same", "mirror-x", "mirror-y", "rotate180"}),
    ]:
        val = (form.get(key) or "").strip()
        if val in allowed:
            args += [flag, val]

    return args


def load_ui_defaults() -> dict:
    defaults = dict(UI_DEFAULTS)
    if not SETTINGS_PATH.exists():
        return defaults

    try:
        cfg = planechase_proxygen.load_config_json(SETTINGS_PATH)
    except Exception:
        return defaults

    for key in [
        "page",
        "fit",
        "card_format",
        "card_orientation",
        "duplex_mode",
        "back_pairing",
        "back_transform",
        "back_placement",
    ]:
        val = cfg.get(key)
        if val is not None:
            defaults[key] = str(val)

    for key in [
        "gap_mm",
        "margin_mm",
        "front_offset_x_mm",
        "front_offset_y_mm",
        "back_offset_x_mm",
        "back_offset_y_mm",
    ]:
        val = cfg.get(key)
        if val is not None:
            defaults[key] = str(val)

    return defaults


def _extract_slot_rects_with_page_translate(page) -> Tuple[List[Tuple[float, float, float, float]], Tuple[float, float]]:
    content = page.get_contents()
    if content is None:
        return [], (0.0, 0.0)

    raw = content.get_data().decode("latin-1", errors="ignore")
    rect_re = re.compile(r"n\s+([\-0-9.]+)\s+([\-0-9.]+)\s+([\-0-9.]+)\s+([\-0-9.]+)\s+re\s+W\*\s+n")
    cm_re = re.compile(r"1\s+0\s+0\s+1\s+([\-0-9.]+)\s+([\-0-9.]+)\s+cm")

    tx, ty = 0.0, 0.0
    for mx, my in cm_re.findall(raw):
        x = float(mx)
        y = float(my)
        if abs(x) > 1e-9 or abs(y) > 1e-9:
            tx, ty = x, y
            break

    rects: List[Tuple[float, float, float, float]] = []
    for x, y, w, h in rect_re.findall(raw):
        rects.append((float(x) + tx, float(y) + ty, float(w), float(h)))
    return rects, (tx, ty)


def _pair_indices(total_pages: int, duplex_mode: str) -> List[Tuple[int, int]]:
    if total_pages < 2 or total_pages % 2 != 0:
        return []

    mode = duplex_mode.lower().strip()
    if mode == "paired":
        return [(i, i + 1) for i in range(0, total_pages, 2)]
    if mode == "separate":
        half = total_pages // 2
        return [(i, i + half) for i in range(half)]
    return []


def build_alignment_report(*, pdf_path: Path, duplex_mode: str) -> str:
    try:
        import PyPDF2
    except Exception:
        return "Alignment report skipped: install PyPDF2 to enable PDF geometry checks."

    try:
        reader = PyPDF2.PdfReader(str(pdf_path))
    except Exception as e:
        return f"Alignment report skipped: cannot read PDF ({e})."

    pairs = _pair_indices(len(reader.pages), duplex_mode)
    if not pairs:
        return "Alignment report skipped: unsupported page pairing for this PDF."

    lines: List[str] = ["=== ALIGNMENT REPORT (PDF geometry) ==="]
    all_ok = True

    for front_i, back_i in pairs:
        front_slots, front_translate = _extract_slot_rects_with_page_translate(reader.pages[front_i])
        back_slots, back_translate = _extract_slot_rects_with_page_translate(reader.pages[back_i])

        if not front_slots or not back_slots:
            all_ok = False
            lines.append(
                f"Pair p{front_i + 1}/p{back_i + 1}: missing slot rectangles in content stream (cannot verify)."
            )
            continue

        front_x = [x for x, _, _, _ in front_slots]
        front_y = [y for _, y, _, _ in front_slots]
        back_x = [x for x, _, _, _ in back_slots]
        back_y = [y for _, y, _, _ in back_slots]
        dx_pt = mean(back_x) - mean(front_x)
        dy_pt = mean(back_y) - mean(front_y)
        dx_mm = dx_pt / PT_PER_MM
        dy_mm = dy_pt / PT_PER_MM

        back_set = {(round(x, 3), round(y, 3), round(w, 3), round(h, 3)) for x, y, w, h in back_slots}
        match = True
        for x, y, w, h in front_slots:
            probe = (round(x + dx_pt, 3), round(y + dy_pt, 3), round(w, 3), round(h, 3))
            if probe not in back_set:
                match = False
                break

        all_ok = all_ok and match
        lines.append(
            f"Pair p{front_i + 1}/p{back_i + 1}: match={match} delta=({dx_mm:.3f}mm, {dy_mm:.3f}mm) "
            f"front_translate_pt={front_translate} back_translate_pt={back_translate}"
        )

    lines.append(f"Overall: {'OK' if all_ok else 'CHECK NEEDED'}")
    lines.append("Note: this validates PDF geometry only (not printer duplex mechanical drift).")
    return "\n".join(lines)


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = secrets.token_urlsafe(32)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @app.context_processor
    def inject_csrf_token() -> dict:
        csrf_token = session.get("csrf_token")
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)
            session["csrf_token"] = csrf_token
        return {"csrf_token": csrf_token}

    @app.get("/")
    def index() -> str:
        defaults = load_ui_defaults()
        return render_template("index.html", defaults=defaults, log=None, last_pdf=None, scroll_to_alignment=False)

    @app.post("/run")
    def run() -> str:
        expected_csrf_token = session.get("csrf_token")
        provided_csrf_token = request.form.get("csrf_token")
        if not (
            expected_csrf_token
            and provided_csrf_token
            and secrets.compare_digest(provided_csrf_token, expected_csrf_token)
        ):
            flash("Nieprawidłowy token bezpieczeństwa. Odśwież stronę i spróbuj ponownie.")
            return render_template(
                "index.html",
                defaults=load_ui_defaults(),
                log=None,
                last_pdf=None,
                scroll_to_alignment=False,
            )

        action = (request.form.get("action") or "generate").strip()
        try:
            args = build_common_args(request.form)
            out_name = normalize_output_name(request.form.get("out_name"))
        except ValueError as exc:
            flash(str(exc))
            return render_template(
                "index.html",
                defaults=dict(request.form),
                log=None,
                last_pdf=None,
                scroll_to_alignment=False,
            )
        history_path = OUTPUT_DIR / "rename_history.jsonl"

        last_pdf: Optional[str] = None
        scroll_to_alignment = False
        is_generate_action = action in {"generate", "generate_verify"}

        if action == "dry_run":
            args = ["--dry-run", "--print-settings"] + args
        elif action == "generate":
            # no extra flags
            pass
        elif action == "generate_verify":
            # Generation already includes alignment verification in GUI log.
            scroll_to_alignment = True
        elif action == "calibration_sheet":
            args = ["--calibration-sheet"] + args
        elif action == "suggest_renames":
            args = ["--suggest-back-renames"] + args
        elif action == "export_rename_script":
            script_path = OUTPUT_DIR / "rename_back_files.ps1"
            args = [
                "--suggest-back-renames",
                "--write-rename-script",
                str(script_path),
                "--rename-history-file",
                str(history_path),
            ] + args
        elif action == "apply_renames_preview":
            args = [
                "--suggest-back-renames",
                "--apply-back-renames",
                "--rename-history-file",
                str(history_path),
            ] + args
        elif action == "apply_renames_yes":
            args = [
                "--suggest-back-renames",
                "--apply-back-renames",
                "--rename-history-file",
                str(history_path),
                "--yes",
            ] + args
        elif action == "undo_renames_preview":
            args = ["--undo-back-renames", "--rename-history-file", str(history_path)] + args
        elif action == "undo_renames_yes":
            args = ["--undo-back-renames", "--rename-history-file", str(history_path), "--yes"] + args
        elif action == "print_settings":
            args = ["--dry-run", "--print-settings"] + args
        elif action == "write_config":
            # Writes to settings.json in project root
            args = ["--write-config", str(APP_ROOT / "settings.json")] + args
        else:
            flash(f"Unknown action: {action}")
            return render_template(
                "index.html",
                defaults=dict(request.form),
                log=None,
                last_pdf=None,
                scroll_to_alignment=False,
            )

        code, log = run_proxygen(args)

        out_path = OUTPUT_DIR / out_name
        if is_generate_action and code == 0 and out_path.exists():
            last_pdf = out_name
            alignment = build_alignment_report(
                pdf_path=out_path,
                duplex_mode=(request.form.get("duplex_mode") or "paired"),
            )
            if log.strip():
                log = f"{log}\n\n{alignment}"
            else:
                log = alignment
        elif action == "calibration_sheet" and code == 0 and out_path.exists():
            last_pdf = out_name

        if code != 0:
            flash("Wystąpił błąd (zobacz log).")

        # Re-render with the same values the user entered
        defaults = dict(request.form)
        return render_template(
            "index.html",
            defaults=defaults,
            log=log,
            last_pdf=last_pdf,
            scroll_to_alignment=scroll_to_alignment,
        )

    @app.get("/output/<path:filename>")
    def download_output(filename: str) -> Response:
        return send_from_directory(OUTPUT_DIR, filename, as_attachment=False)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=False)
