"""Squarified treemap layout (Bruls, Huijing & van Wijk, 2000).

Given a rectangle and a list of weighted items, produce a tiling of
sub-rectangles whose areas are proportional to the weights while keeping
each rectangle as close to square as possible. Also provides a radial
(sunburst) layout.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

Rect = Tuple[float, float, float, float]  # x, y, w, h


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _worst_ratio(items: List[float], length: float) -> float:
    """Worst aspect ratio of a row of items laid out along a side."""
    if not items or length <= 0:
        return float("inf")
    row_sum = sum(items)
    r2 = max(length * length * max(items) / (row_sum * row_sum),
             row_sum * row_sum / (length * length * min(items)))
    return r2


def _layout_row(row: List[Tuple[str, float]], rect: Rect,
                horizontal: bool) -> Tuple[List[Tuple[str, Rect]], Rect]:
    """Place one row and return (tiles, remaining rectangle)."""
    x, y, w, h = rect
    total = sum(weight for _, weight in row)
    tiles: List[Tuple[str, Rect]] = []
    if horizontal:
        # row runs along the top, fixed height
        row_h = total / w if w else 0
        offset = 0.0
        for name, weight in row:
            item_w = (weight / total) * w if total else 0
            tiles.append((name, (x + offset, y, item_w, row_h)))
            offset += item_w
        remaining = (x, y + row_h, w, max(h - row_h, 0.0))
    else:
        # row runs along the left, fixed width
        row_w = total / h if h else 0
        offset = 0.0
        for name, weight in row:
            item_h = (weight / total) * h if total else 0
            tiles.append((name, (x, y + offset, row_w, item_h)))
            offset += item_h
        remaining = (x + row_w, y, max(w - row_w, 0.0), h)
    return tiles, remaining


def squarify(items: List[Tuple[str, float]], rect: Rect
             ) -> List[Tuple[str, Rect]]:
    """Lay out weighted items into ``rect`` using the squarified algorithm.

    ``items`` is a list of (label, weight) with non-negative weights.
    Returns a list of (label, (x, y, w, h)) tiles normalized to the
    input rectangle coordinate system.
    """
    # Drop zero/negative weights and sort descending (required by the paper).
    items = [(n, w) for n, w in items if w > 0]
    items.sort(key=lambda t: -t[1])
    if not items:
        return []

    total_weight = sum(w for _, w in items)
    x, y, w, h = rect
    area = w * h
    if area <= 0 or total_weight <= 0:
        return []

    # Scale weights so their total equals the rectangle area.
    scale = area / total_weight
    scaled = [(n, weight * scale) for n, weight in items]

    tiles: List[Tuple[str, Rect]] = []
    current_rect = rect
    queue = list(scaled)

    while queue:
        horizontal = current_rect[2] >= current_rect[3]
        side = current_rect[2] if horizontal else current_rect[3]

        row: List[Tuple[str, float]] = []
        # Greedily add items while the aspect ratio keeps improving.
        while queue:
            candidate = row + [queue[0]]
            cand_vals = [v for _, v in candidate]
            if not row or _worst_ratio(cand_vals, side) <= \
                    _worst_ratio([v for _, v in row], side):
                row.append(queue.pop(0))
            else:
                break

        row_tiles, current_rect = _layout_row(row, current_rect, horizontal)
        tiles.extend(row_tiles)

    return tiles


# ---------------------------------------------------------------------------
# Hierarchical treemap
# ---------------------------------------------------------------------------

def treemap_nodes(node, rect: Rect, depth: int = 0,
                  max_depth: int = 2) -> List[Dict[str, object]]:
    """Build a list of renderable rectangles for a FileNode-like tree.

    The node must expose ``name``, ``size``, ``is_dir`` and
    ``sorted_children()``. Directories above ``max_depth`` are split
    recursively; deeper directories are rendered as single tiles.
    """
    x, y, w, h = rect
    result: List[Dict[str, object]] = []

    if not getattr(node, "is_dir", False):
        result.append({
            "path": node.path, "name": node.name,
            "x": x, "y": y, "w": w, "h": h,
            "size": node.size, "depth": depth, "is_dir": False,
            "category": getattr(node, "category", "other"),
        })
        return result

    if depth >= max_depth:
        result.append({
            "path": node.path, "name": node.name,
            "x": x, "y": y, "w": w, "h": h,
            "size": node.size, "depth": depth, "is_dir": True,
            "category": "dir",
        })
        return result

    children = node.sorted_children()
    items = [(c.name, c.size) for c in children]
    tiles = squarify(items, rect)
    by_name = {c.name: c for c in children}
    for name, tile_rect in tiles:
        child = by_name[name]
        tx, ty, tw, th = tile_rect
        if child.is_dir and depth + 1 < max_depth:
            result.extend(treemap_nodes(child, tile_rect,
                                        depth + 1, max_depth))
        else:
            result.append({
                "path": child.path, "name": child.name,
                "x": tx, "y": ty, "w": tw, "h": th,
                "size": child.size, "depth": depth + 1,
                "is_dir": child.is_dir,
                "category": "dir" if child.is_dir
                            else getattr(child, "category", "other"),
            })
    return result


# ---------------------------------------------------------------------------
# Sunburst (radial) layout
# ---------------------------------------------------------------------------

def sunburst(node, inner_r: float, outer_r: float,
             start: float = 0.0, sweep: float = 6.283185307179586,
             depth: int = 0, max_depth: int = 3
             ) -> List[Dict[str, object]]:
    """Return annular sectors proportional to each node's size.

    Angles are in radians. Each record contains the inner/outer radius and
    the start/end angle, plus the node's name/path and size.
    """
    sectors: List[Dict[str, object]] = []
    thickness = outer_r - inner_r

    def recurse(n, r0, r1, a0, a1, d):
        sectors.append({
            "path": n.path, "name": n.name,
            "r0": r0, "r1": r1, "a0": a0, "a1": a1,
            "size": n.size, "depth": d,
            "is_dir": getattr(n, "is_dir", False),
            "category": getattr(n, "category", "dir"),
        })
        if d >= max_depth or not getattr(n, "is_dir", False):
            return
        # Children share the parent's angular span in proportion to their
        # size relative to the parent (local total).
        local_total = n.size if n.size > 0 else 1
        span = a1 - a0
        angle = a0
        for child in n.sorted_children():
            c_span = span * (child.size / local_total)
            if c_span <= 0:
                continue
            recurse(child, r1, r1 + thickness,
                    angle, angle + c_span, d + 1)
            angle += c_span

    recurse(node, inner_r, outer_r, start, start + sweep, depth)
    return sectors
