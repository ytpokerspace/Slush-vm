"""Frame-by-frame next-observation prediction and scoring for discrete visual streams.

This is a baseline evaluator for grid-valued frames (including normalized ARC
observations), not a general video codec or a claim of learned visual prediction.
It predicts persistence by default, estimates per-cell confidence from recent
agreement, and scores forecasts only after the actual next frame is available.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable


Grid = list[list[Any]]


def extract_frame(observation: Any) -> Grid | None:
    """Extract a rectangular-or-ragged 2D grid from common observation shapes."""
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if isinstance(frame[0], list) and frame[0] and isinstance(frame[0][0], list):
        frame = frame[0]
    if not isinstance(frame, list) or not frame or not all(isinstance(row, list) for row in frame):
        return None
    return [list(row) for row in frame]


def predict_next_frame(history: Iterable[Grid], top_k: int = 3) -> dict[str, Any]:
    """Forecast the next grid from recent frames, with per-cell candidate scores.

    The point prediction is persistence (copy the latest frame). Per-cell
    confidence is the recent frequency of the latest value, and alternatives are
    the top-K observed values at that coordinate. Scores are empirical frequencies,
    not calibrated probabilities.
    """
    frames = [frame for frame in history if isinstance(frame, list) and frame
              and all(isinstance(row, list) for row in frame)]
    if not frames:
        raise ValueError("history must contain at least one non-empty grid frame")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")
    latest = frames[-1]
    height = len(latest)
    widths = [len(row) for row in latest]
    recent = frames[-min(5, len(frames)):]
    cells: list[list[dict[str, Any]]] = []
    for y, row in enumerate(latest):
        scored_row = []
        for x, current in enumerate(row):
            values = [f[y][x] for f in recent if y < len(f) and x < len(f[y])]
            counts = Counter(values)
            total = len(values)
            candidates = [
                {"value": value, "score": round(count / total, 4)}
                for value, count in counts.most_common(top_k)
            ]
            latest_frequency = counts[current] / total if total else 0.0
            scored_row.append({
                "x": x, "y": y, "predicted_value": current,
                "confidence": round(latest_frequency, 4),
                "top_candidates": candidates,
            })
        cells.append(scored_row)
    return {
        "prediction": [list(row) for row in latest],
        "prediction_method": "persistence_with_empirical_cell_candidates",
        "history_frames_used": len(recent),
        "shape": {"height": height, "widths": widths},
        "cells": cells,
        "warning": "Candidate scores are empirical frequencies, not calibrated probabilities; moving objects require a learned or motion-aware model.",
    }


def score_frame_prediction(prediction: Any, actual: Any) -> dict[str, Any]:
    """Score a predicted grid against its realized next frame."""
    if not isinstance(prediction, list) or not prediction or not all(isinstance(r, list) for r in prediction):
        raise ValueError("prediction must be a non-empty grid")
    if not isinstance(actual, list) or not actual or not all(isinstance(r, list) for r in actual):
        raise ValueError("actual must be a non-empty grid")
    height = max(len(prediction), len(actual))
    width = max(max((len(r) for r in prediction), default=0),
                max((len(r) for r in actual), default=0))
    total = 0
    correct = 0
    mismatches = []
    for y in range(height):
        for x in range(width):
            p_exists = y < len(prediction) and x < len(prediction[y])
            a_exists = y < len(actual) and x < len(actual[y])
            if not p_exists or not a_exists:
                total += 1
                mismatches.append({"x": x, "y": y, "predicted": None if not p_exists else prediction[y][x],
                                   "actual": None if not a_exists else actual[y][x]})
                continue
            total += 1
            if prediction[y][x] == actual[y][x]:
                correct += 1
            else:
                mismatches.append({"x": x, "y": y, "predicted": prediction[y][x], "actual": actual[y][x]})
    return {
        "frame_accuracy": correct / total if total else 0.0,
        "correct_cells": correct,
        "total_cells": total,
        "mismatch_count": total - correct,
        "shape_match": len(prediction) == len(actual) and [len(r) for r in prediction] == [len(r) for r in actual],
        "mismatches": mismatches[:100],
    }


def score_sequence(frames: Iterable[Grid]) -> dict[str, Any]:
    """Walk a frame sequence causally: predict frame t from frames before t."""
    sequence = list(frames)
    records = []
    for index in range(1, len(sequence)):
        forecast = predict_next_frame(sequence[:index])
        score = score_frame_prediction(forecast["prediction"], sequence[index])
        records.append({"frame_index": index, "prediction": forecast["prediction"], **score})
    cells = sum(r["total_cells"] for r in records)
    correct = sum(r["correct_cells"] for r in records)
    return {
        "frames_scored": len(records),
        "overall_cell_accuracy": correct / cells if cells else None,
        "records": records,
        "note": "Use a held-out chronological sequence; this persistence baseline is a reference point, not evidence of predictive skill beyond persistence.",
    }
