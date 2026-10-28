"""Midpoint video forecasting and backward scene-change analysis.

This module operates on already-extracted discrete grid frames. It does not
decode MP4s or train a neural video model. Its forecasts are transparent
baselines that can evaluate a future learned model on the same interface.
"""
from __future__ import annotations

from typing import Any, Iterable

from arc3.frame_prediction import predict_next_frame, score_frame_prediction

Grid = list[list[Any]]


def _validate_sequence(frames: Iterable[Grid], timestamps: Iterable[float]) -> tuple[list[Grid], list[float]]:
    fs = list(frames)
    ts = [float(t) for t in timestamps]
    if len(fs) != len(ts) or len(fs) < 2:
        raise ValueError("frames and timestamps must have equal length >= 2")
    if any(ts[i] >= ts[i + 1] for i in range(len(ts) - 1)):
        raise ValueError("timestamps must be strictly increasing")
    if any(not isinstance(frame, list) or not frame or not all(isinstance(row, list) for row in frame) for frame in fs):
        raise ValueError("every frame must be a non-empty grid")
    return fs, ts


def _nearest_index(timestamps: list[float], target: float) -> int:
    return min(range(len(timestamps)), key=lambda i: (abs(timestamps[i] - target), i))


def transition_summary(before: Grid, after: Grid) -> dict[str, Any]:
    """Describe observable grid changes without assigning semantic causes."""
    height = max(len(before), len(after))
    width = max(max((len(r) for r in before), default=0), max((len(r) for r in after), default=0))
    changes = []
    for y in range(height):
        for x in range(width):
            has_before = y < len(before) and x < len(before[y])
            has_after = y < len(after) and x < len(after[y])
            old = before[y][x] if has_before else None
            new = after[y][x] if has_after else None
            if has_before != has_after or old != new:
                changes.append({"x": x, "y": y, "before": old, "after": new})
    return {
        "changed_cells": len(changes),
        "changes": changes[:500],
        "shape_changed": len(before) != len(after) or [len(r) for r in before] != [len(r) for r in after],
        "interpretation": "Observed differences only; cause and object identity are not inferred.",
    }


def evaluate_midpoint(
    frames: Iterable[Grid],
    timestamps: Iterable[float],
    *,
    duration_seconds: float = 5.0,
    midpoint_seconds: float = 2.5,
    method: str = "persistence",
) -> dict[str, Any]:
    """Forecast the frame nearest the midpoint using only frames before it."""
    fs, ts = _validate_sequence(frames, timestamps)
    if duration_seconds <= 0 or not 0 < midpoint_seconds < duration_seconds:
        raise ValueError("require duration > 0 and midpoint between 0 and duration")
    target_time = min(ts[0] + midpoint_seconds, ts[0] + duration_seconds)
    target_idx = _nearest_index(ts, target_time)
    prior_indices = [i for i in range(target_idx) if ts[i] < ts[target_idx]]
    if not prior_indices:
        raise ValueError("clip has no earlier frame from which to forecast midpoint")
    forecast = predict_next_frame([fs[i] for i in prior_indices], method=method)
    actual = fs[target_idx]
    score = score_frame_prediction(forecast["prediction"], actual)
    return {
        "task": "midpoint_forecast",
        "target_timestamp_seconds": ts[target_idx],
        "context_timestamps_seconds": [ts[i] for i in prior_indices],
        "prediction_method": method,
        "predicted_frame": forecast["prediction"],
        "actual_frame": actual,
        "score": score,
        "transition_into_target": transition_summary(fs[target_idx - 1], actual) if target_idx > 0 else None,
        "warning": "Baseline forecast only; confidence scores are not calibrated probabilities.",
    }


def backward_change_analysis(
    frames: Iterable[Grid], timestamps: Iterable[float]
) -> dict[str, Any]:
    """Walk from the clip's end toward its start and report observed transitions.

    This is backward event inspection, not proof of the unique cause of an event.
    """
    fs, ts = _validate_sequence(frames, timestamps)
    transitions = []
    for i in range(len(fs) - 1, 0, -1):
        transitions.append({
            "from_timestamp_seconds": ts[i],
            "to_timestamp_seconds": ts[i - 1],
            "reverse_view": transition_summary(fs[i], fs[i - 1]),
        })
    return {
        "task": "backward_change_analysis",
        "direction": "latest_to_earliest",
        "transitions": transitions,
        "warning": "Backward inspection describes changes in reverse order; it does not uniquely recover causes or hidden frames.",
    }


def analyze_clip(
    frames: Iterable[Grid],
    timestamps: Iterable[float],
    *,
    duration_seconds: float = 5.0,
    midpoint_seconds: float = 2.5,
    method: str = "persistence",
) -> dict[str, Any]:
    """Combine midpoint holdout evaluation with reverse chronological inspection."""
    fs, ts = _validate_sequence(frames, timestamps)
    midpoint = evaluate_midpoint(fs, ts, duration_seconds=duration_seconds,
                                 midpoint_seconds=midpoint_seconds, method=method)
    backward = backward_change_analysis(fs, ts)
    return {
        "clip_duration_seconds": duration_seconds,
        "midpoint_seconds": midpoint_seconds,
        "frame_count": len(fs),
        "midpoint_forecast": midpoint,
        "backward_analysis": backward,
        "status": "baseline_complete",
        "next_step": "Compare multiple methods on held-out clips before training or claiming predictive skill.",
    }
