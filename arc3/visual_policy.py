"""Observation-only visual navigation heuristic for grid-like ARC-AGI-3 games.

The heuristic uses frame pixels and legal action names only. It does not inspect
environment source. It is intentionally conservative and falls back to exploration
when a moving object and a plausible shared-color target cannot be identified.
"""
from __future__ import annotations

from collections import Counter, deque
from typing import Any

DIRECTION_ACTIONS = {
    (0, -1): "ACTION1",
    (0, 1): "ACTION2",
    (-1, 0): "ACTION3",
    (1, 0): "ACTION4",
}


def extract_grid(observation: Any) -> list[list[int]] | None:
    """Return the first 2D layer from a normalized observation."""
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if isinstance(frame[0], list) and frame[0] and not isinstance(frame[0][0], list):
        grid = frame
    elif isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        grid = frame[0]
    else:
        return None
    if not all(isinstance(row, list) for row in grid):
        return None
    return grid


def _components(grid: list[list[int]], background: set[int]) -> list[dict[str, Any]]:
    """Find connected non-background components in the visible playfield."""
    height = len(grid)
    width = max((len(row) for row in grid), default=0)
    seen: set[tuple[int, int]] = set()
    result: list[dict[str, Any]] = []
    for y, row in enumerate(grid):
        if y >= 55:
            continue  # Avoid common HUD/status bars at the bottom of 64x64 frames.
        for x, value in enumerate(row):
            if x >= width or value in background or (x, y) in seen:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            cells: list[tuple[int, int]] = []
            colors: set[int] = set()
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                colors.add(grid[cy][cx])
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if not (0 <= ny < min(height, 55) and 0 <= nx < len(grid[ny])):
                        continue
                    if (nx, ny) not in seen and grid[ny][nx] not in background:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            xs = [point[0] for point in cells]
            ys = [point[1] for point in cells]
            result.append({
                "cells": cells,
                "colors": colors,
                "area": len(cells),
                "bbox": (min(xs), min(ys), max(xs), max(ys)),
                "center": (round((min(xs) + max(xs)) / 2), round((min(ys) + max(ys)) / 2)),
            })
    return result


def infer_navigation(observation: Any) -> dict[str, Any] | None:
    """Infer a first-step direction toward a smaller shared-color target.

    Background colors are conservatively estimated as the three most common pixel
    values. The player candidate is the largest non-background component in the
    central playfield. A smaller component sharing one of its colors and lying
    above it is treated as a possible goal. A 4-neighbor BFS over the most common
    adjacent background color plans at the player's sprite step size.
    """
    grid = extract_grid(observation)
    if grid is None or not grid:
        return None
    values = [value for row in grid for value in row]
    counts = Counter(values)
    background = {value for value, _ in counts.most_common(3)}
    components = _components(grid, background)

    player_candidates = [
        comp for comp in components
        if comp["area"] >= 8 and 16 <= comp["center"][1] < 55
    ]
    if not player_candidates:
        return None
    player = max(player_candidates, key=lambda comp: comp["area"])
    px, py = player["center"]
    player_colors = player["colors"]

    target_candidates = [
        comp for comp in components
        if comp is not player
        and 2 <= comp["area"] < player["area"]
        and comp["colors"] & player_colors
        and comp["center"][1] < py
    ]
    if not target_candidates:
        return None
    target = min(
        target_candidates,
        key=lambda comp: ((comp["center"][0] - px) ** 2 + (comp["center"][1] - py) ** 2),
    )
    tx, ty = target["center"]

    # Estimate traversable color from the visible ring around the player component.
    boundary_values: Counter[int] = Counter()
    player_cells = set(player["cells"])
    for x, y in player_cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= ny < min(len(grid), 55) and 0 <= nx < len(grid[ny]):
                value = grid[ny][nx]
                if (nx, ny) not in player_cells and value in background:
                    boundary_values[value] += 1
    if not boundary_values:
        return None

    # Prefer the observed corridor color on the direct ray toward the target.
    # This avoids a wall/floor tie when the sprite is inside a narrow corridor.
    ray_values: list[int] = []
    if px == tx:
        for y in range(min(py, ty) + 1, max(py, ty)):
            value = grid[y][px]
            if value in background and value not in player_colors and value not in target["colors"]:
                ray_values.append(value)
    elif py == ty:
        for x in range(min(px, tx) + 1, max(px, tx)):
            value = grid[py][x]
            if value in background and value not in player_colors and value not in target["colors"]:
                ray_values.append(value)
    ray_color = Counter(ray_values).most_common(1)[0][0] if ray_values else None
    if ray_color is not None and ray_color in boundary_values:
        walkable = ray_color
    else:
        max_boundary_count = max(boundary_values.values())
        tied = [color for color, count in boundary_values.items() if count == max_boundary_count]
        # When the local boundary is tied, prefer the less prevalent background
        # color rather than arbitrarily treating the surrounding wall as floor.
        walkable = min(tied, key=lambda color: counts[color])

    # Sprite displacement is estimated from the player's bounding box.
    x0, y0, x1, y1 = player["bbox"]
    step = max(2, round(max(x1 - x0 + 1, y1 - y0 + 1)))
    target_colors = target["colors"]
    passable = {walkable} | target_colors | player_colors

    start = (px, py)

    # Sprite centers need not land on an occupied target pixel. Treat a center as
    # reaching the target when the player's estimated footprint overlaps any
    # target cell; this handles hollow/asymmetric target sprites.
    radius = max(1, step // 2)
    def reaches_target(position: tuple[int, int]) -> bool:
        return any(
            abs(position[0] - x) <= radius and abs(position[1] - y) <= radius
            for x, y in target["cells"]
        )

    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    goal_node: tuple[int, int] | None = None
    while queue:
        current = queue.popleft()
        if reaches_target(current):
            goal_node = current
            break
        for dx, dy in ((0, -step), (0, step), (-step, 0), (step, 0)):
            nxt = (current[0] + dx, current[1] + dy)
            nx, ny = nxt
            if nxt in previous or not (0 <= ny < min(len(grid), 55) and 0 <= nx < len(grid[ny])):
                continue
            if grid[ny][nx] not in passable and not reaches_target(nxt):
                continue
            previous[nxt] = current
            queue.append(nxt)

    if goal_node is None:
        return None
    node = goal_node
    while previous[node] is not None and previous[node] != start:
        node = previous[node]  # Walk backward to the first step after start.
    dx = node[0] - px
    dy = node[1] - py
    unit = (0 if dx == 0 else (1 if dx > 0 else -1),
            0 if dy == 0 else (1 if dy > 0 else -1))
    action_name = DIRECTION_ACTIONS.get(unit)
    if action_name is None:
        return None
    return {
        "action": action_name,
        "player_center": [px, py],
        "target_center": [tx, ty],
        "step_size": step,
        "walkable_color": walkable,
        "target_area": target["area"],
    }


def score_navigation_candidates(
    action_records: list[dict[str, Any]], navigation: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Attach a strong preference for the inferred legal direction, if available."""
    if navigation is None:
        return action_records
    preferred = navigation["action"]
    return [
        {**record, "score": 100.0 if record.get("name") == preferred else 0.0}
        for record in action_records
    ]
