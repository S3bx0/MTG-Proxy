from __future__ import annotations

import sys
from typing import Sequence

from proxgen.cli import main as _main
from proxgen.config import load_config_json, write_config_json


def main(argv: Sequence[str]) -> int:
    return _main(argv)


__all__ = [
    "main",
    "load_config_json",
    "write_config_json",
]


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
