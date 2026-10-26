"""Object-centric visual perception for grid observations.

Produces measurable descriptors and tentative role hypotheses. Shape labels are
geometric descriptions, not semantic certainty; callers should combine them with
motion, context, and action outcomes.
"""
from __future__ import annotations

from collections import Counter, deque
from math import isclose
from typing import Any


def extract_grid(observation: Any) -> list[list[Any]] | None:
    """Extract a 2D grid from common observation shapes."""
    if not isinstance(observation, dict):
        return None
    grid = observation.get("grid", observation.get("board", observation.get("frame")))
    if not isinstance(grid, list) or not grid:
        return None
    # Frame stacks may contain layers of 2D grids.
    if isinstance(grid[0], list) and grid[0] and isinstance(grid[0][0], list):
        grid = grid[0]
    if not grid or not all(isinstance(row, list) for row in grid):
        return None
    return grid


def _components(grid: list[list[Any]], background: set[Any], max_height: int | None) -> list[dict[str, Any]]:
    height = min(len(grid), max_height) if max_height else len(grid)
    seen: set[tuple[int, int]] = set()
    objects: list[dict[str, Any]] = []
    for y in range(height):
        for x, color in enumerate(grid[y]):
            if color in background or (x, y) in seen:
                continue
            queue = deque([(x, y)])
            seen.add((x, y))
            cells: list[tuple[int, int]] = []
            colors: Counter[Any] = Counter()
            while queue:
                cx, cy = queue.popleft()
                cells.append((cx, cy))
                colors[grid[cy][cx]] += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if not (0 <= ny < height and 0 <= nx < len(grid[ny])):
                        continue
                    if (nx, ny) not in seen and grid[ny][nx] not in background:
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            xs = [p[0] for p in cells]
            ys = [p[1] for p in cells]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            width, obj_height = x1 - x0 + 1, y1 - y0 + 1
            area = len(cells)
            density = area / (width * obj_height)
            aspect = width / obj_height
            if area == 1:
                shape = "single_cell"
            elif obj_height == 1:
                shape = "horizontal_line"
            elif width == 1:
                shape = "vertical_line"
            elif width == obj_height and isclose(density, 1.0):
                shape = "filled_square"
            elif isclose(density, 1.0):
                shape = "filled_rectangle"
            elif isclose(aspect, 1.0, rel_tol=0.15) and density >= 0.65:
                shape = "compact_block"
            else:
                shape = "irregular_or_hollow"
            objects.append({
                "cells": [[cx, cy] for cx, cy in cells],
                "colors": [{"value": value, "count": count} for value, count in colors.most_common()],
                "dominant_color": colors.most_common(1)[0][0],
                "area": area,
                "bbox": {"x": x0, "y": y0, "width": width, "height": obj_height,
                         "x2": x1, "y2": y1},
                "center": [round((x0 + x1) / 2, 3), round((y0 + y1) / 2, 3)],
                "aspect_ratio": round(aspect, 4),
                "fill_density": round(density, 4),
                "shape": shape,
            })
    return objects


def perceive_objects(
    observation: Any,
    *,
    background_colors: list[Any] | None = None,
    max_height: int | None = 55,
) -> dict[str, Any]:
    """Describe connected objects and compare each object's relative dimensions.

    If background colors are omitted, the most frequent pixel value is used as a
    conservative baseline. This can fail on multi-color backgrounds; callers can
    pass explicit background colors when known.
    """
    grid = extract_grid(observation)
    if grid is None or not grid or not any(grid):
        return {"status": "insufficient_grid", "objects": [], "background_colors": []}
    flat = [value for row in grid[:max_height] if max_height else grid for value in row]
    if not flat:
        return {"status": "insufficient_grid", "objects": [], "background_colors": []}
    if background_colors is None:
        background = {Counter(flat).most_common(1)[0][0]}
        background_method = "most_frequent_pixel_heuristic"
    else:
        background = set(background_colors)
        background_method = "caller_supplied"
    objects = _components(grid, background, max_height)
    total = max(1, len(objects))
    for obj in objects:
        box = obj["bbox"]
        larger = sum(other["area"] > obj["area"] for other in objects)
        smaller = sum(other["area"] < obj["area"] for other in objects)
        obj["relative_size"] = {
            "area_fraction_of_largest": round(obj["area"] / max(o["area"] for o in objects), 4) if objects else 0.0,
            "rank_by_area": 1 + larger,
            "objects_larger": larger,
            "objects_smaller": smaller,
            "object_count": total,
        }
        obj["relative_dimensions"] = {
            "width_fraction_of_largest_width": round(box["width"] / max(o["bbox"]["width"] for o in objects), 4) if objects else 0.0,
            "height_fraction_of_largest_height": round(box["height"] / max(o["bbox"]["height"] for o in objects), 4) if objects else 0.0,
        }
        # These are deliberately weak candidate roles, never definitive identity.
        roles = []
        if obj["shape"] in ("single_cell", "horizontal_line", "vertical_line"):
            roles.append("possible_marker_or_moving_piece")
        if obj["shape"] in ("filled_square", "filled_rectangle", "compact_block"):
            roles.append("possible_actor_or_solid_obstacle")
        if obj["shape"] == "irregular_or_hollow":
            roles.append("possible_composite_or_hollow_object")
        if obj["relative_size"]["rank_by_area"] == 1:
            roles.append("largest_visible_object_candidate")
        obj["role_hypotheses"] = roles
        obj["identity_confidence"] = 0.0
        obj["identity_note"] = "Geometry alone does not establish semantic identity."
    return {
        "status": "ok",
        "background_colors": sorted(background, key=str),
        "background_method": background_method,
        "object_count": len(objects),
        "objects": [
            {"object_id": f"obj_{i:03d}", **obj}
            for i, obj in enumerate(sorted(objects, key=lambda item: (item["bbox"]["y"], item["bbox"]["x"])), 1)
        ],
        "limitations": [
            "Connected components use 4-neighbor adjacency; diagonal pixels may become separate objects.",
            "The default background estimate can merge or split objects in multi-color scenes.",
            "Role hypotheses are geometric guesses and require temporal/contextual evidence.",
        ],
    }
