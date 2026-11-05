"""Offline, dependency-free benchmark for frame prediction baselines.

This uses synthetic grid trajectories because it does not require ARC-AGI-3
credentials, a live game server, or user data. Synthetic results validate the
harness and expose controlled behavior; they are not evidence of performance on
real ARC tasks. Replace/add replay sequences from legally obtained observations
for more representative evaluation.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from arc3.frame_prediction import compare_methods

Grid = list[list[int]]


def _grid(width: int, height: int, x: int, y: int, value: int = 2) -> Grid:
    result = [[0 for _ in range(width)] for _ in range(height)]
    result[y][x] = value
    return result


def synthetic_scenarios() -> dict[str, list[Grid]]:
    """Return deterministic trajectories with known simple dynamics."""
    stationary = [[[0, 0, 0], [0, 2, 0], [0, 0, 0]] for _ in range(8)]
    moving = [_grid(7, 3, x, 1) for x in range(1, 6)]
    blinking = []
    for index in range(8):
        frame = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        frame[1][1] = 2 if index % 2 == 0 else 0
        blinking.append(frame)
    return {"stationary_object": stationary, "single_object_motion": moving, "alternating_cell": blinking}


def run_benchmark() -> dict[str, Any]:
    """Score each baseline causally on all built-in synthetic scenarios."""
    scenarios = {}
    rows = []
    for name, frames in synthetic_scenarios().items():
        result = compare_methods(frames)
        scenarios[name] = result
        for entry in result["comparison"]:
            rows.append({
                "scenario": name,
                "method": entry["method"],
                "overall_cell_accuracy": entry["overall_cell_accuracy"],
                "frames_scored": entry["frames_scored"],
            })
    return {
        "benchmark": "offline_synthetic_frame_prediction_v1",
        "requires_network": False,
        "requires_credentials": False,
        "scenarios": scenarios,
        "summary": rows,
        "interpretation": (
            "Synthetic sanity check only. It measures chronological cell accuracy "
            "on hand-designed trajectories and must not be reported as ARC-AGI-3 "
            "task accuracy or general video-prediction performance."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="indent JSON output")
    args = parser.parse_args()
    result = run_benchmark()
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
