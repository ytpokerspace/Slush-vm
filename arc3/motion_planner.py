"""Heuristic what-if motion forecasting for grid observations.

Probabilities are normalized heuristic scenario weights, not calibrated likelihoods.
This module deliberately reports uncertainty and keeps forecasts separate from facts.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

SCENARIO_PRIORS = {
    "continue": 0.60,
    "stop": 0.25,
    "reverse": 0.15,
}


def _grid(observation: Any) -> list[list[Any]] | None:
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        frame = frame[0]
    if not isinstance(frame[0], list):
        return None
    return frame


def _centers(grid: list[list[Any]]) -> dict[str, tuple[float, float]]:
    cells: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            if value not in (0, "0", None):
                cells[str(value)].append((x, y))
    centers = {}
    for color, points in cells.items():
        centers[color] = (
            sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points),
        )
    return centers


def forecast_motion(
    previous_observation: Any,
    current_observation: Any,
    horizon: int = 1,
) -> dict[str, Any]:
    """Forecast color-centroid motion with continue/stop/reverse what-if scenarios."""
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 8:
        raise ValueError("horizon must be an integer from 1 to 8")
    previous = _grid(previous_observation)
    current = _grid(current_observation)
    if previous is None or current is None:
        return {"status": "insufficient_observations", "scenarios": [], "best_scenario": None}
    before, now = _centers(previous), _centers(current)
    tracks = []
    for color in sorted(set(before) & set(now)):
        vx, vy = now[color][0] - before[color][0], now[color][1] - before[color][1]
        if abs(vx) + abs(vy) < 0.01:
            continue
        tracks.append({"color": color, "position": [round(now[color][0], 3), round(now[color][1], 3)],
                       "velocity": [round(vx, 3), round(vy, 3)]})
    if not tracks:
        return {
            "status": "no_motion_detected",
            "scenarios": [],
            "best_scenario": None,
            "probabilities_are_calibrated": False,
        }

    scenarios = []
    for name, probability in SCENARIO_PRIORS.items():
        predictions = []
        for track in tracks:
            x, y = track["position"]
            vx, vy = track["velocity"]
            if name == "continue":
                dx, dy = vx * horizon, vy * horizon
            elif name == "stop":
                dx, dy = 0.0, 0.0
            else:
                dx, dy = -vx * horizon, -vy * horizon
            predictions.append({
                "color": track["color"],
                "predicted_center": [round(x + dx, 3), round(y + dy, 3)],
                "velocity": track["velocity"],
            })
        scenarios.append({
            "name": name,
            "probability": probability,
            "horizon_frames": horizon,
            "predictions": predictions,
        })
    best = max(scenarios, key=lambda item: item["probability"])
    return {
        "status": "forecast_available",
        "scenarios": scenarios,
        "best_scenario": best["name"],
        "best_probability": best["probability"],
        "tracks": tracks,
        "probabilities_are_calibrated": False,
        "warning": "Heuristic priors only; validate against future frames before treating them as likelihoods.",
    }
