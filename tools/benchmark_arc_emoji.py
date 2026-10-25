#!/usr/bin/env python3
"""Deterministic synthetic benchmark; does not measure ARC-AGI-3 performance."""
import json
import platform
import random
import statistics
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arc_emoji.solver import TRANSFORMS, normalize_grid, predict, grid_to_lists

SEED = 20261025
TASKS = 120


def apply(name, grid):
    return dict(TRANSFORMS)[name](normalize_grid(grid))


def main():
    rng = random.Random(SEED)
    tasks = []
    names = [name for name, _ in TRANSFORMS]
    for i in range(TASKS):
        size = 3 + (i % 3)
        grid = [[rng.randrange(1, 6) for _ in range(size)] for _ in range(size)]
        name = names[i % len(names)]
        tasks.append((name, grid, apply(name, grid)))
    latencies = []
    correct = 0
    failures = []
    for i, (name, grid, expected) in enumerate(tasks):
        start = time.perf_counter_ns()
        result = predict([(grid, expected)], grid)
        elapsed = time.perf_counter_ns() - start
        latencies.append(elapsed / 1_000_000)
        ok = result.status == "predicted" and grid_to_lists(result.grid) == [list(r) for r in expected]
        correct += int(ok)
        if not ok:
            failures.append({"task": i, "expected_transform": name,
                             "status": result.status, "selected_transform": result.transform,
                             "reason": result.reason})
    report = {
        "benchmark_type": "synthetic_unit_benchmark_not_arc_agi_3",
        "seed": SEED, "tasks": TASKS, "python": platform.python_version(),
        "platform": platform.platform(), "exact_grid_match_rate": correct / TASKS,
        "correct": correct, "failures": failures,
        "latency_ms": {"median": statistics.median(latencies),
                       "p95": sorted(latencies)[int(0.95 * (len(latencies) - 1))],
                       "mean": statistics.mean(latencies)},
        "limitations": [
            "Synthetic square grids only; no official ARC-AGI-3 environment.",
            "Candidate set is limited to six geometric transforms.",
            "Symmetric grids can make the generating transform unidentifiable.",
            "Timing depends on host hardware and load."
        ]
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
