from __future__ import annotations

from typing import List


def back_slot_map(*, cols: int, rows: int, placement: str) -> List[int]:
    if cols <= 0 or rows <= 0:
        raise ValueError("cols and rows must be > 0")

    placement = placement.lower().strip()
    valid = {"same", "mirror-x", "mirror-y", "rotate180"}
    if placement not in valid:
        raise ValueError(f"Unknown back placement: {placement}. Valid: {sorted(valid)}")

    mapping: List[int] = []
    for i in range(cols * rows):
        r = i // cols
        c = i % cols

        if placement == "same":
            r2, c2 = r, c
        elif placement == "mirror-x":
            r2, c2 = r, (cols - 1 - c)
        elif placement == "mirror-y":
            r2, c2 = (rows - 1 - r), c
        elif placement == "rotate180":
            r2, c2 = (rows - 1 - r), (cols - 1 - c)
        else:
            raise AssertionError("unreachable")

        mapping.append(r2 * cols + c2)

    return mapping


def resolve_back_placement(*, back_placement: str, page_portrait: bool) -> str:
    back_placement = back_placement.lower().strip()
    if back_placement == "auto":
        return "mirror-x" if page_portrait else "mirror-y"

    valid = {"same", "mirror-x", "mirror-y", "rotate180"}
    if back_placement not in valid:
        raise ValueError(f"Unknown back placement: {back_placement}. Valid: {sorted(valid | {'auto'})}")
    return back_placement
