"""Small deterministic grid-transformation baseline; not a full ARC-AGI-3 agent."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

Grid = tuple[tuple[int, ...], ...]
Transform = Callable[[Grid], Grid]


def normalize_grid(grid: Sequence[Sequence[int]]) -> Grid:
    if not grid or not grid[0]:
        raise ValueError("grid must be non-empty")
    width = len(grid[0])
    if any(len(row) != width for row in grid):
        raise ValueError("grid must be rectangular")
    if any(not isinstance(cell, int) or isinstance(cell, bool) for row in grid for cell in row):
        raise ValueError("grid cells must be integers")
    return tuple(tuple(row) for row in grid)


def flood_fill_components(grid: Sequence[Sequence[int]], background: int = 0,
                          connectivity: int = 4) -> list[dict]:
    """Return same-colour connected components, excluding background, in stable scan order."""
    g = normalize_grid(grid)
    if connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")
    h, w = len(g), len(g[0])
    directions = [(-1, 0), (0, -1), (0, 1), (1, 0)]
    if connectivity == 8:
        directions = [(dr, dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1) if (dr, dc) != (0, 0)]
    seen: set[tuple[int, int]] = set()
    components = []
    for r in range(h):
        for c in range(w):
            colour = g[r][c]
            if colour == background or (r, c) in seen:
                continue
            queue = deque([(r, c)])
            seen.add((r, c))
            cells = []
            while queue:
                cr, cc = queue.popleft()
                cells.append((cr, cc))
                for dr, dc in directions:
                    nr, nc = cr + dr, cc + dc
                    if (0 <= nr < h and 0 <= nc < w and (nr, nc) not in seen
                            and g[nr][nc] == colour):
                        seen.add((nr, nc))
                        queue.append((nr, nc))
            rows = [p[0] for p in cells]
            cols = [p[1] for p in cells]
            components.append({
                "color": colour, "size": len(cells),
                "cells": tuple(sorted(cells)),
                "bbox": (min(rows), min(cols), max(rows), max(cols)),
            })
    return components


def identity(g: Grid) -> Grid:
    return g


def horizontal_flip(g: Grid) -> Grid:
    return tuple(tuple(reversed(row)) for row in g)


def vertical_flip(g: Grid) -> Grid:
    return tuple(reversed(g))


def rotate_180(g: Grid) -> Grid:
    return vertical_flip(horizontal_flip(g))


def rotate_90(g: Grid) -> Grid:
    return tuple(tuple(g[len(g) - 1 - r][c] for r in range(len(g)))
                 for c in range(len(g[0]))) if len(g) == len(g[0]) else tuple(
                     tuple(g[len(g) - 1 - r][c] for r in range(len(g)))
                     for c in range(len(g[0])))


def rotate_270(g: Grid) -> Grid:
    return rotate_180(rotate_90(g))


TRANSFORMS: tuple[tuple[str, Transform], ...] = (
    ("identity", identity),
    ("horizontal_flip", horizontal_flip),
    ("vertical_flip", vertical_flip),
    ("rotate_180", rotate_180),
    ("rotate_90", rotate_90),
    ("rotate_270", rotate_270),
)


@dataclass(frozen=True)
class Prediction:
    transform: str | None
    grid: Grid | None
    status: str
    candidates_checked: int
    reason: str


def predict(training_pairs: Iterable[tuple[Sequence[Sequence[int]], Sequence[Sequence[int]]]],
            test_input: Sequence[Sequence[int]]) -> Prediction:
    """Select the first transform that matches every demonstration pair exactly."""
    pairs = [(normalize_grid(x), normalize_grid(y)) for x, y in training_pairs]
    test = normalize_grid(test_input)
    if not pairs:
        return Prediction(None, None, "no_prediction", 0, "no training examples")
    survivors = []
    for name, fn in TRANSFORMS:
        try:
            if all(fn(inp) == out for inp, out in pairs):
                survivors.append((name, fn))
        except (IndexError, ValueError):
            continue
    if not survivors:
        return Prediction(None, None, "no_prediction", len(TRANSFORMS),
                          "no supported transform matches all training pairs")
    name, fn = survivors[0]  # Stable tie-break: documented transform order.
    try:
        result = fn(test)
    except (IndexError, ValueError) as exc:
        return Prediction(None, None, "no_prediction", len(TRANSFORMS),
                          f"candidate failed on test input: {exc}")
    return Prediction(name, result, "predicted", len(TRANSFORMS),
                      "exactly consistent with all supplied training pairs")


def grid_to_lists(grid: Grid | None):
    return None if grid is None else [list(row) for row in grid]
