from __future__ import annotations

import json
from pathlib import Path


def load_config_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Invalid JSON in config file {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a JSON object (dict): {path}")
    return data


def write_config_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
