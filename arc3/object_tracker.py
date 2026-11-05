"""Open-set object tracking with persistent undetermined variables.

Tracks are geometric hypotheses, not semantic identities. Matching is greedy and
deterministic; it is intended as a baseline for grid observations, not a learned
multi-object tracker.
"""
from __future__ import annotations

from math import hypot
from typing import Any


def _distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    ac, bc = a.get("center", [0, 0]), b.get("center", [0, 0])
    return hypot(float(ac[0]) - float(bc[0]), float(ac[1]) - float(bc[1]))


def update_object_tracks(
    previous: dict[str, Any] | None,
    perception: dict[str, Any],
    *,
    max_distance: float = 8.0,
    max_missed: int = 2,
) -> dict[str, Any]:
    """Associate observed components with prior tracks and retain briefly missing tracks.

    Every track carries identity_status='undetermined' until external evidence
    supports a semantic label. Relevance is an explicit heuristic score from
    geometry, uniqueness, and motion; it is not a probability.
    """
    if max_distance < 0 or max_missed < 0:
        raise ValueError("max_distance and max_missed must be non-negative")
    old_tracks = list((previous or {}).get("tracks", []))
    observations = list(perception.get("objects", []))
    used: set[int] = set()
    tracks: list[dict[str, Any]] = []
    next_id = int((previous or {}).get("next_track_id", 1))

    # Greedy nearest-neighbour association, penalizing incompatible shape/color.
    pairs: list[tuple[float, int, int]] = []
    for ti, track in enumerate(old_tracks):
        for oi, obj in enumerate(observations):
            distance = _distance(track, obj)
            same_color = track.get("dominant_color") == obj.get("dominant_color")
            same_shape = track.get("shape") == obj.get("shape")
            limit = max_distance if same_color else max_distance * 0.5
            if distance <= limit:
                penalty = (0.0 if same_color else 2.0) + (0.0 if same_shape else 1.0)
                pairs.append((distance + penalty, ti, oi))
    matched_tracks: set[int] = set()
    matches: dict[int, int] = {}
    for _, ti, oi in sorted(pairs):
        if ti not in matched_tracks and oi not in used:
            matched_tracks.add(ti)
            used.add(oi)
            matches[oi] = ti

    for oi, obj in enumerate(observations):
        if oi in matches:
            old = old_tracks[matches[oi]]
            track_id = old["track_id"]
            prior_center = old.get("center", obj.get("center", [0, 0]))
            missed = 0
            age = int(old.get("age", 1)) + 1
        else:
            track_id = f"track_{next_id:04d}"
            next_id += 1
            prior_center = obj.get("center", [0, 0])
            missed = 0
            age = 1
        center = obj.get("center", [0, 0])
        motion = [round(float(center[0]) - float(prior_center[0]), 3),
                  round(float(center[1]) - float(prior_center[1]), 3)]
        area = float(obj.get("area", 0))
        count = max(1, int(obj.get("relative_size", {}).get("object_count", len(observations) or 1)))
        color_count = len(obj.get("colors", []))
        # Explainable salience heuristic; no semantic label is inferred from score.
        size_signal = min(1.0, area / 16.0)
        uniqueness_signal = 1.0 / count
        motion_signal = min(1.0, hypot(*motion) / 8.0)
        complexity_signal = min(1.0, color_count / 3.0)
        relevance = round(0.40 * size_signal + 0.25 * uniqueness_signal
                          + 0.20 * motion_signal + 0.15 * complexity_signal, 4)
        tracks.append({
            **obj,
            "track_id": track_id,
            "identity_status": "undetermined",
            "identity_hypotheses": [],
            "identity_confidence": 0.0,
            "track_age": age,
            "missed_frames": missed,
            "motion_delta": motion,
            "relevance": {
                "score": relevance,
                "score_type": "heuristic_salience_not_probability",
                "factors": {
                    "relative_size": round(size_signal, 4),
                    "uniqueness": round(uniqueness_signal, 4),
                    "observed_motion": round(motion_signal, 4),
                    "color_complexity": round(complexity_signal, 4),
                },
                "note": "Relevance must be revised when goal and action-outcome context are available.",
            },
        })

    for ti, old in enumerate(old_tracks):
        if ti in matched_tracks:
            continue
        missed = int(old.get("missed_frames", 0)) + 1
        if missed <= max_missed:
            retained = dict(old)
            retained["missed_frames"] = missed
            retained["visibility"] = "temporarily_unobserved"
            retained["identity_status"] = "undetermined"
            tracks.append(retained)

    tracks.sort(key=lambda item: item["track_id"])
    return {
        "status": "ok" if perception.get("status") == "ok" else perception.get("status", "unknown"),
        "next_track_id": next_id,
        "tracks": tracks,
        "active_track_ids": [t["track_id"] for t in tracks if t.get("missed_frames", 0) == 0],
        "retained_unobserved_track_ids": [t["track_id"] for t in tracks if t.get("missed_frames", 0) > 0],
        "limitations": [
            "Greedy geometric matching can swap identities when objects cross or look alike.",
            "Tracks are retained for a bounded number of missed frames, then expired.",
            "Relevance scores are hand-designed salience heuristics, not calibrated probabilities.",
        ],
    }
