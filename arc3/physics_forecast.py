"""Physics-informed trajectory hypotheses for tracked video objects.

This is a deterministic kinematics scaffold, not a trained visual model. It consumes
object detections/tracks from an upstream vision system and forecasts positions.
Coordinates use image convention: x grows right, y grows down. Acceleration is
estimated from observations unless gravity_px_s2 is supplied explicitly.
"""
from __future__ import annotations

from math import isfinite
from typing import Any, Iterable


def _validate_observations(observations: Iterable[dict[str, Any]]) -> list[dict[str, float]]:
    rows = []
    for item in observations:
        if not isinstance(item, dict):
            raise ValueError("each observation must be a mapping with t, x, and y")
        try:
            row = {key: float(item[key]) for key in ("t", "x", "y")}
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("each observation must contain numeric t, x, and y") from exc
        if not all(isfinite(value) for value in row.values()):
            raise ValueError("observation values must be finite")
        rows.append(row)
    if len(rows) < 2:
        raise ValueError("at least two observations are required")
    if any(rows[i]["t"] >= rows[i + 1]["t"] for i in range(len(rows) - 1)):
        raise ValueError("observation timestamps must be strictly increasing")
    return rows


def _velocity(rows: list[dict[str, float]], key: str) -> float:
    """Least-squares velocity across observed positions, in pixels/second."""
    times = [row["t"] for row in rows]
    values = [row[key] for row in rows]
    mean_t = sum(times) / len(times)
    mean_v = sum(values) / len(values)
    denominator = sum((t - mean_t) ** 2 for t in times)
    if denominator == 0:
        raise ValueError("timestamps must span a non-zero interval")
    return sum((t - mean_t) * (v - mean_v) for t, v in zip(times, values)) / denominator


def _acceleration(rows: list[dict[str, float]], key: str) -> float:
    """Estimate acceleration from endpoint velocity change; noisy by design."""
    first_dt = rows[1]["t"] - rows[0]["t"]
    last_dt = rows[-1]["t"] - rows[-2]["t"]
    first_v = (rows[1][key] - rows[0][key]) / first_dt
    last_v = (rows[-1][key] - rows[-2][key]) / last_dt
    elapsed = rows[-1]["t"] - rows[0]["t"]
    return (last_v - first_v) / elapsed if elapsed > 0 else 0.0


def _simulate(
    x: float, y: float, vx: float, vy: float, ax: float, ay: float,
    horizon_seconds: float, step_seconds: float, ground_y: float | None = None,
    restitution: float = 0.65,
) -> list[dict[str, float | bool]]:
    states = []
    t = step_seconds
    current_vy = vy
    bounced = False
    while t <= horizon_seconds + 1e-9:
        px = x + vx * t + 0.5 * ax * t * t
        py = y + current_vy * t + 0.5 * ay * t * t
        collision = ground_y is not None and py >= ground_y and current_vy + ay * t > 0
        if collision:
            py = ground_y
            current_vy = -(current_vy + ay * t) * restitution
            # Continue the post-impact segment from the collision time; this
            # simple model allows one bounce and is intentionally not a rigid-body solver.
            remaining = max(0.0, t - (ground_y - y) / max(1e-9, current_vy if current_vy > 0 else 1e-9))
            py = ground_y + current_vy * remaining + 0.5 * ay * remaining * remaining
            bounced = True
        states.append({"t": round(t, 6), "x": px, "y": py, "bounce_contact": bool(collision)})
        t += step_seconds
    return states


def forecast_trajectory(
    observations: Iterable[dict[str, Any]],
    *,
    horizon_seconds: float = 1.0,
    step_seconds: float = 0.1,
    gravity_px_s2: float | None = None,
    ground_y: float | None = None,
    restitution: float = 0.65,
) -> dict[str, Any]:
    """Return ranked kinematic futures from observed object-center coordinates.

    Hypothesis ranking is an engineering default, not a calibrated probability.
    """
    rows = _validate_observations(observations)
    if not isfinite(horizon_seconds) or horizon_seconds <= 0:
        raise ValueError("horizon_seconds must be finite and > 0")
    if not isfinite(step_seconds) or step_seconds <= 0 or step_seconds > horizon_seconds:
        raise ValueError("step_seconds must be finite, > 0, and <= horizon_seconds")
    if gravity_px_s2 is not None and not isfinite(gravity_px_s2):
        raise ValueError("gravity_px_s2 must be finite when supplied")
    if ground_y is not None and not isfinite(ground_y):
        raise ValueError("ground_y must be finite when supplied")
    if not 0 <= restitution <= 1:
        raise ValueError("restitution must be in [0, 1]")

    x, y = rows[-1]["x"], rows[-1]["y"]
    vx, vy = _velocity(rows, "x"), _velocity(rows, "y")
    ax, observed_ay = _acceleration(rows, "x"), _acceleration(rows, "y")
    ay = observed_ay if gravity_px_s2 is None else gravity_px_s2

    hypotheses = [
        {"name": "constant_velocity", "rank_score": 0.45,
         "states": _simulate(x, y, vx, vy, 0.0, 0.0, horizon_seconds, step_seconds)},
        {"name": "observed_acceleration", "rank_score": 0.35,
         "states": _simulate(x, y, vx, vy, ax, ay, horizon_seconds, step_seconds)},
    ]
    if ground_y is not None:
        hypotheses.append({
            "name": "gravity_with_ground_contact", "rank_score": 0.20,
            "states": _simulate(x, y, vx, vy, ax, ay, horizon_seconds, step_seconds,
                                ground_y=ground_y, restitution=restitution),
        })
    hypotheses.sort(key=lambda item: item["rank_score"], reverse=True)
    return {
        "schema": "physics_trajectory_hypotheses_v1",
        "observations_used": len(rows),
        "last_observed": rows[-1],
        "estimated_state": {
            "vx_px_per_second": vx, "vy_px_per_second": vy,
            "ax_px_per_second_squared": ax,
            "ay_px_per_second_squared": ay,
            "gravity_source": "provided" if gravity_px_s2 is not None else "estimated_from_track",
        },
        "horizon_seconds": horizon_seconds,
        "hypotheses": hypotheses,
        "limitations": [
            "Requires object coordinates from a separate vision/tracking stage.",
            "Image-space trajectories are not true world-space physics unless camera motion and perspective are handled.",
            "Contact, rotation, friction, board-skater coupling, and occlusion are not fully modeled.",
            "rank_score values are heuristic rankings, not probabilities.",
            "This module predicts object-center trajectories, not rendered future video frames, and is not a trained model.",
        ],
    }
