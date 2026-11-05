"""Observation-only first-level planner for ARC-AGI-3 ls20.

The planner reconstructs the visible player, key pattern, lock pattern, and
rotation tile from frames. It does not inspect or import environment source.
It is deliberately limited to the rotation-only case; unsupported transforms
fall back to the general ARC-AGI-3 policy.
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


def _grid_from_observation(observation: Any) -> list[list[int]] | None:
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if frame[0] and isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        frame = frame[0]
    if not isinstance(frame[0], list):
        return None
    if not all(isinstance(row, list) for row in frame):
        return None
    return frame


def _components(grid: list[list[int]], background: set[int]) -> list[dict[str, Any]]:
    height = min(len(grid), 55)  # exclude the lower HUD from playfield objects
    seen: set[tuple[int, int]] = set()
    result: list[dict[str, Any]] = []
    for y in range(height):
        for x, value in enumerate(grid[y]):
            if value in background or (x, y) in seen:
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
                    if (
                        0 <= ny < height
                        and 0 <= nx < len(grid[ny])
                        and (nx, ny) not in seen
                        and grid[ny][nx] not in background
                    ):
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            xs = [point[0] for point in cells]
            ys = [point[1] for point in cells]
            result.append({
                "cells": cells,
                "colors": colors,
                "area": len(cells),
                "bbox": (min(xs), min(ys), max(xs), max(ys)),
                "center": (
                    round((min(xs) + max(xs)) / 2),
                    round((min(ys) + max(ys)) / 2),
                ),
            })
    return result


def _pattern_from_pixels(
    pixels: list[tuple[int, int]], block_size: int = 1
) -> list[list[int]] | None:
    if not pixels:
        return None
    xs = [point[0] for point in pixels]
    ys = [point[1] for point in pixels]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    width, height = x1 - x0 + 1, y1 - y0 + 1
    if width % block_size or height % block_size:
        return None
    occupied = set(pixels)
    pattern: list[list[int]] = []
    for by in range(y0, y1 + 1, block_size):
        row: list[int] = []
        for bx in range(x0, x1 + 1, block_size):
            filled = any(
                (bx + dx, by + dy) in occupied
                for dy in range(block_size)
                for dx in range(block_size)
            )
            row.append(1 if filled else 0)
        pattern.append(row)
    return pattern


def _rotate_clockwise(pattern: list[list[int]]) -> list[list[int]]:
    return [list(row) for row in zip(*pattern[::-1])]


def _rotation_steps(
    current: list[list[int]], target: list[list[int]]
) -> int | None:
    if not current or len(current) != len(target) or any(
        len(a) != len(b) for a, b in zip(current, target)
    ):
        return None
    candidate = current
    for turns in range(4):
        if candidate == target:
            return turns
        candidate = _rotate_clockwise(candidate)
    return None


def _find_walkable_color(
    grid: list[list[int]], player: dict[str, Any], background: set[int]
) -> int | None:
    boundary: Counter[int] = Counter()
    cells = set(player["cells"])
    for x, y in cells:
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (
                0 <= ny < min(len(grid), 55)
                and 0 <= nx < len(grid[ny])
                and (nx, ny) not in cells
                and grid[ny][nx] in background
            ):
                boundary[grid[ny][nx]] += 1
    if not boundary:
        return None
    return boundary.most_common(1)[0][0]


def _path_to(
    grid: list[list[int]],
    player: dict[str, Any],
    goal: tuple[int, int],
    walkable_color: int,
    goal_colors: set[int],
    panel_bounds: tuple[int, int, int, int] | None = None,
) -> list[tuple[int, int]] | None:
    x0, y0, x1, y1 = player["bbox"]
    step = max(x1 - x0 + 1, y1 - y0 + 1)
    if step <= 0:
        return None
    start = player["center"]
    half_width = (x1 - x0) // 2
    half_height = (y1 - y0) // 2
    passable = {walkable_color} | set(player["colors"]) | set(goal_colors)

    def footprint_is_passable(center: tuple[int, int]) -> bool:
        cx, cy = center
        for fy in range(cy - half_height, cy + half_height + 1):
            for fx in range(cx - half_width, cx + half_width + 1):
                if not (0 <= fy < min(len(grid), 55) and 0 <= fx < len(grid[fy])):
                    return False
                value = grid[fy][fx]
                if value in passable:
                    continue
                if (
                    panel_bounds is not None
                    and panel_bounds[0] <= fx <= panel_bounds[2]
                    and panel_bounds[1] <= fy <= panel_bounds[3]
                    and value in {3, 5}
                ):
                    continue
                return False
        return True

    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        current = queue.popleft()
        if current == goal:
            path: list[tuple[int, int]] = []
            node: tuple[int, int] | None = current
            while node is not None:
                path.append(node)
                node = previous[node]
            return list(reversed(path))
        for dx, dy in ((0, -step), (0, step), (-step, 0), (step, 0)):
            nxt = (current[0] + dx, current[1] + dy)
            if nxt in previous:
                continue
            if not (0 <= nxt[1] < min(len(grid), 55) and 0 <= nxt[0] < len(grid[nxt[1]])):
                continue
            if not footprint_is_passable(nxt):
                continue
            previous[nxt] = current
            queue.append(nxt)
    return None


def _first_action(path: list[tuple[int, int]]) -> str | None:
    if len(path) < 2:
        return None
    dx = path[1][0] - path[0][0]
    dy = path[1][1] - path[0][1]
    unit = (0 if dx == 0 else (1 if dx > 0 else -1),
            0 if dy == 0 else (1 if dy > 0 else -1))
    return DIRECTION_ACTIONS.get(unit)


def infer_ls20_plan(observation: Any) -> dict[str, Any] | None:
    """Infer a route to the rotation tile, then to the matching lock.

    The first visible level's key/lock panels use the same 3x3 binary shape,
    with the key shown at 2x pixel scale. If the lock is a pure rotation of
    the key, the player is routed through the small rotation tile first.
    """
    grid = _grid_from_observation(observation)
    if grid is None or len(grid) < 55 or len(grid[0]) < 55:
        return None

    values = [value for row in grid for value in row]
    counts = Counter(values)
    background = {value for value, _ in counts.most_common(3)}
    components = _components(grid, background)

    players = [
        comp for comp in components
        if comp["area"] >= 15 and 12 in comp["colors"]
        and 20 <= comp["center"][1] < 55
    ]
    switches = [
        comp for comp in components
        if 2 <= comp["area"] <= 8 and comp["colors"] == {0, 1}
        and 18 <= comp["center"][1] < 45
    ]
    if not players or not switches:
        return None
    player = max(players, key=lambda comp: comp["area"])
    switch = min(switches, key=lambda comp: comp["area"])

    door_pixels = [
        (x, y)
        for y, row in enumerate(grid[:20])
        for x, value in enumerate(row)
        if x >= 20 and value == 9
    ]
    key_pixels = [
        (x, y)
        for y, row in enumerate(grid[50:], start=50)
        for x, value in enumerate(row)
        if x < 12 and value == 9
    ]
    door_pattern = _pattern_from_pixels(door_pixels, 1)
    key_pattern = _pattern_from_pixels(key_pixels, 2)
    if door_pattern is None or key_pattern is None:
        return None
    turns = _rotation_steps(key_pattern, door_pattern)
    if turns is None:
        return {
            "status": "unsupported_key_transform",
            "key_pattern": key_pattern,
            "door_pattern": door_pattern,
            "navigation": None,
        }

    walkable = _find_walkable_color(grid, player, background)
    if walkable is None:
        return None

    if turns:
        stage = "visit_rotation_switch"
        goal = switch["center"]
        goal_colors = switch["colors"]
        panel_bounds = None
    else:
        stage = "reach_matching_door"
        door_xs = [x for x, _ in door_pixels]
        door_ys = [y for _, y in door_pixels]
        door_center = (
            round((min(door_xs) + max(door_xs)) / 2),
            round((min(door_ys) + max(door_ys)) / 2),
        )
        goal = door_center
        goal_colors = {9}
        panel_bounds = (
            min(door_xs) - 3, min(door_ys) - 3,
            max(door_xs) + 3, max(door_ys) + 3,
        )

    path = _path_to(
        grid, player, goal, walkable, goal_colors, panel_bounds=panel_bounds
    )
    if path is None:
        return {
            "status": "no_observed_path",
            "stage": stage,
            "key_rotation_steps": turns,
            "player_center": list(player["center"]),
            "target_center": list(goal),
            "walkable_color": walkable,
            "navigation": None,
        }

    action = _first_action(path)
    navigation = None
    if action is not None:
        navigation = {
            "action": action,
            "player_center": list(player["center"]),
            "target_center": list(goal),
            "step_size": max(
                player["bbox"][2] - player["bbox"][0] + 1,
                player["bbox"][3] - player["bbox"][1] + 1,
            ),
            "walkable_color": walkable,
            "stage": stage,
        }
    return {
        "status": "planned",
        "stage": stage,
        "key_rotation_steps": turns,
        "key_matches_door": turns == 0,
        "key_pattern": key_pattern,
        "door_pattern": door_pattern,
        "player_center": list(player["center"]),
        "target_center": list(goal),
        "walkable_color": walkable,
        "path": [list(point) for point in path],
        "navigation": navigation,
    }
