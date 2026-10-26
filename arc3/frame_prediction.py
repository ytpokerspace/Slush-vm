"""Causal frame prediction baselines for discrete grid observations.

Methods are simple, auditable baselines, not learned video models. Candidate
scores are heuristic/empirical scores, not calibrated probabilities.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

Grid = list[list[Any]]


def extract_frame(observation: Any) -> Grid | None:
    """Extract a grid from common observation keys."""
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if frame and isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        frame = frame[0]
    if not frame or not all(isinstance(row, list) for row in frame):
        return None
    return [list(row) for row in frame]


def _valid_frames(history: Iterable[Grid]) -> list[Grid]:
    frames = [f for f in history if isinstance(f, list) and f and all(isinstance(r, list) for r in f)]
    if not frames:
        raise ValueError("history must contain at least one non-empty grid frame")
    return frames


def _copy_grid(grid: Grid) -> Grid:
    return [list(row) for row in grid]


def _persistence(frames: list[Grid]) -> Grid:
    return _copy_grid(frames[-1])


def _motion(frames: list[Grid]) -> Grid:
    """Translate each cell's value by its most recent single-step displacement.

    This deliberately conservative baseline only moves a value when it occurs
    exactly once in each of the last two frames. Otherwise that value stays put.
    It is not object tracking and may be ambiguous for backgrounds/repeated cells.
    """
    latest = _copy_grid(frames[-1])
    if len(frames) < 2:
        return latest
    previous, current = frames[-2], frames[-1]

    def unique_positions(grid: Grid) -> dict[Any, tuple[int, int]] | None:
        positions: dict[Any, tuple[int, int]] = {}
        duplicates: set[Any] = set()
        for y, row in enumerate(grid):
            for x, value in enumerate(row):
                try:
                    if value in positions:
                        duplicates.add(value)
                    else:
                        positions[value] = (x, y)
                except TypeError:
                    return None
        for value in duplicates:
            positions.pop(value, None)
        return positions

    prev_pos, curr_pos = unique_positions(previous), unique_positions(current)
    if prev_pos is None or curr_pos is None:
        return latest
    height = len(latest)
    widths = [len(row) for row in latest]
    output = _copy_grid(latest)
    # Only relocate unique non-background-like values; infer the most common
    # value as background and avoid moving it as a whole-grid object.
    counts = Counter(v for row in current for v in row)
    background = counts.most_common(1)[0][0] if counts else None
    for value, (x, y) in curr_pos.items():
        if value == background or value not in prev_pos:
            continue
        px, py = prev_pos[value]
        dx, dy = x - px, y - py
        nx, ny = x + dx, y + dy
        if (dx or dy) and 0 <= ny < height and 0 <= nx < len(output[ny]):
            output[y][x] = background
            output[ny][nx] = value
    return output


def _change_aware(frames: list[Grid]) -> Grid:
    """Use a short per-cell history when a coordinate has changed repeatedly.

    If a cell changed in both of the last two transitions, predict its recent
    modal value; otherwise preserve the latest value. This is a simple
    change-frequency baseline, not a semantic object model.
    """
    latest = _copy_grid(frames[-1])
    if len(frames) < 3:
        return latest
    older, previous, current = frames[-3:]
    output = _copy_grid(current)
    for y, row in enumerate(current):
        for x, value in enumerate(row):
            if (y >= len(previous) or x >= len(previous[y])
                    or y >= len(older) or x >= len(older[y])):
                continue
            before, prior = older[y][x], previous[y][x]
            if before != prior and prior != value:
                values = [f[y][x] for f in frames[-min(5, len(frames)):]
                          if y < len(f) and x < len(f[y])]
                counts = Counter(values)
                # On ties, Counter preserves first-seen order; latest value is
                # the safe fallback so the heuristic remains deterministic.
                winner, count = counts.most_common(1)[0]
                if sum(1 for n in counts.values() if n == count) > 1:
                    winner = value
                output[y][x] = winner
    return output


def predict_next_frame(history: Iterable[Grid], top_k: int = 3, method: str = "persistence") -> dict[str, Any]:
    """Predict the next grid with one of three explicit baseline methods."""
    frames = _valid_frames(history)
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    methods = {"persistence": _persistence, "motion": _motion, "change_aware": _change_aware}
    if method not in methods:
        raise ValueError(f"unknown method {method!r}; choose from {', '.join(methods)}")
    prediction = methods[method](frames)
    recent = frames[-min(5, len(frames)):]
    cells = []
    for y, row in enumerate(prediction):
        scored_row = []
        for x, predicted in enumerate(row):
            values = [f[y][x] for f in recent if y < len(f) and x < len(f[y])]
            counts = Counter(values)
            total = len(values)
            scored_row.append({
                "x": x, "y": y, "predicted_value": predicted,
                "confidence": round(counts[predicted] / total, 4) if total else 0.0,
                "top_candidates": [{"value": v, "score": round(c / total, 4)}
                                   for v, c in counts.most_common(top_k)] if total else [],
            })
        cells.append(scored_row)
    return {
        "prediction": prediction,
        "prediction_method": method,
        "history_frames_used": len(recent),
        "shape": {"height": len(prediction), "widths": [len(r) for r in prediction]},
        "cells": cells,
        "warning": "Baseline heuristic only; scores are not calibrated probabilities and repeated cell values make motion ambiguous.",
    }


def score_frame_prediction(prediction: Any, actual: Any) -> dict[str, Any]:
    """Score exact cell agreement, penalizing shape differences."""
    if not isinstance(prediction, list) or not prediction or not all(isinstance(r, list) for r in prediction):
        raise ValueError("prediction must be a non-empty grid")
    if not isinstance(actual, list) or not actual or not all(isinstance(r, list) for r in actual):
        raise ValueError("actual must be a non-empty grid")
    height = max(len(prediction), len(actual))
    width = max(max((len(r) for r in prediction), default=0), max((len(r) for r in actual), default=0))
    correct, total, mismatches = 0, 0, []
    for y in range(height):
        for x in range(width):
            pe = y < len(prediction) and x < len(prediction[y])
            ae = y < len(actual) and x < len(actual[y])
            p = prediction[y][x] if pe else None
            a = actual[y][x] if ae else None
            total += 1
            if pe and ae and p == a:
                correct += 1
            else:
                mismatches.append({"x": x, "y": y, "predicted": p, "actual": a})
    return {
        "frame_accuracy": correct / total if total else 0.0,
        "correct_cells": correct, "total_cells": total,
        "mismatch_count": total - correct,
        "shape_match": len(prediction) == len(actual) and [len(r) for r in prediction] == [len(r) for r in actual],
        "mismatches": mismatches[:100],
    }


def score_sequence(frames: Iterable[Grid], method: str = "persistence") -> dict[str, Any]:
    """Predict each frame from earlier frames only, preventing future leakage."""
    sequence = list(frames)
    records = []
    for index in range(1, len(sequence)):
        forecast = predict_next_frame(sequence[:index], method=method)
        score = score_frame_prediction(forecast["prediction"], sequence[index])
        records.append({"frame_index": index, "prediction": forecast["prediction"], **score})
    cells = sum(r["total_cells"] for r in records)
    correct = sum(r["correct_cells"] for r in records)
    return {
        "method": method, "frames_scored": len(records),
        "overall_cell_accuracy": correct / cells if cells else None,
        "records": records,
        "note": "Chronological holdout scoring; compare methods on the same sequence. This is not evidence of general video-prediction skill.",
    }


def compare_methods(frames: Iterable[Grid]) -> dict[str, Any]:
    """Compare all baselines on exactly the same chronological frames."""
    sequence = list(frames)
    names = ("persistence", "motion", "change_aware")
    results = {name: score_sequence(sequence, method=name) for name in names}
    ranked = sorted(
        ((name, result["overall_cell_accuracy"]) for name, result in results.items()
         if result["overall_cell_accuracy"] is not None),
        key=lambda pair: pair[1], reverse=True,
    )
    return {
        "comparison": [{"method": name, "overall_cell_accuracy": score,
                        "frames_scored": results[name]["frames_scored"]}
                       for name, score in ranked],
        "results": results,
        "warning": "A winner on one sequence is not necessarily better on other tasks; use multiple held-out sequences.",
    }


def rank_action_forecasts(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank action forecasts by measured validation accuracy, then optional reward.

    Each candidate must provide action and validation_accuracy (0..1). This
    function ranks evidence about a model, not action quality itself; reward is
    an explicit secondary tie-breaker and is never inferred from prediction score.
    """
    ranked = []
    for item in candidates:
        if not isinstance(item, dict) or "action" not in item:
            raise ValueError("each candidate must be a dict with action and validation_accuracy")
        accuracy = item.get("validation_accuracy")
        reward = item.get("estimated_reward", 0.0)
        if not isinstance(accuracy, (int, float)) or isinstance(accuracy, bool) or not 0 <= accuracy <= 1:
            raise ValueError("validation_accuracy must be numeric in [0, 1]")
        if not isinstance(reward, (int, float)) or isinstance(reward, bool):
            raise ValueError("estimated_reward must be numeric")
        ranked.append({**item, "forecast_rank_score": float(accuracy)})
    return sorted(ranked, key=lambda x: (x["forecast_rank_score"], x.get("estimated_reward", 0.0)), reverse=True)
