"""Separate, evidence-gated memory for one-step game dynamics and bonus decisions.

This partition supplements (and never replaces) the world model, transition learner,
or hierarchical gameplay event log. Forecasts remain predictions until matched against
a subsequent real observation. Bonus pursuit requires explicit measurable reward and
completion-risk evidence; unknown semantics are not treated as a bonus.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from math import hypot
from typing import Any

from arc3.world_model import action_signature, state_signature


def _valid_probability(value: Any) -> bool:
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and 0.0 <= float(value) <= 1.0
    )


def _position(track: dict[str, Any]) -> list[float] | None:
    center = track.get("center")
    if not isinstance(center, (list, tuple)) or len(center) < 2:
        return None
    try:
        return [float(center[0]), float(center[1])]
    except (TypeError, ValueError):
        return None


@dataclass
class GameDynamicsMemory:
    """Track forecast accuracy and evaluate only explicitly evidenced bonus routes."""

    max_records: int = 256
    step_cost_per_step: float = 0.0
    minimum_net_bonus_gain: float = 0.0
    records: list[dict[str, Any]] = field(default_factory=list)
    pending_predictions: dict[str, dict[str, list[float]]] = field(default_factory=dict)
    decisions: int = 0

    def predict_object_positions(
        self, tracks: dict[str, Any] | None, motion_forecast: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Linear one-frame extrapolation from observed track deltas; heuristic only."""
        predictions = []
        for track in (tracks or {}).get("tracks", []):
            if not isinstance(track, dict) or track.get("missed_frames", 0):
                continue
            current = _position(track)
            delta = track.get("motion_delta")
            if current is None or not isinstance(delta, (list, tuple)) or len(delta) < 2:
                continue
            try:
                dx, dy = float(delta[0]), float(delta[1])
            except (TypeError, ValueError):
                continue
            predictions.append({
                "track_id": track.get("track_id"),
                "current_position": current,
                "predicted_next_position": [round(current[0] + dx, 3), round(current[1] + dy, 3)],
                "observed_delta": [dx, dy],
                "evidence": "last_observed_track_delta",
                "confidence_type": "heuristic_not_calibrated_probability",
            })
        scenarios = (motion_forecast or {}).get("scenarios", [])
        return {
            "status": "available" if predictions else "insufficient_track_motion",
            "horizon_frames": 1,
            "objects": predictions,
            "motion_scenarios": deepcopy(scenarios),
            "predictions_are_observations": False,
        }

    def evaluate_bonus_candidates(
        self, candidates: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Reject bonuses lacking measurable gain, step cost, or completion-risk evidence.

        Candidate contract: score_gain, collection_probability, extra_steps,
        completion_probability_before, completion_probability_after, and an
        action_signature identifying the legal action that starts the route.
        Probabilities must be evidence-backed by the caller; this method does not
        manufacture confidence from visual appearance.
        """
        results = []
        for candidate in candidates or []:
            if not isinstance(candidate, dict):
                continue
            gain = candidate.get("score_gain")
            probability = candidate.get("collection_probability")
            extra_steps = candidate.get("extra_steps")
            before = candidate.get("completion_probability_before")
            after = candidate.get("completion_probability_after")
            signature = candidate.get("action_signature")
            evidence = candidate.get("evidence")
            if (
                not isinstance(gain, (int, float)) or isinstance(gain, bool) or gain <= 0
                or not _valid_probability(probability)
                or not isinstance(extra_steps, int) or isinstance(extra_steps, bool) or extra_steps < 0
                or not _valid_probability(before) or not _valid_probability(after)
                or not isinstance(signature, str) or not signature
                or evidence not in {"verified_history", "environment_metadata"}
            ):
                results.append({
                    "status": "rejected_insufficient_evidence",
                    "reason": "Requires measurable reward, collection odds, extra steps, completion odds, legal-action signature and evidence provenance.",
                })
                continue
            if float(after) < float(before):
                results.append({
                    "status": "rejected_completion_risk",
                    "action_signature": signature,
                    "completion_probability_before": float(before),
                    "completion_probability_after": float(after),
                })
                continue
            expected_gain = float(gain) * float(probability)
            step_cost = int(extra_steps) * max(0.0, float(self.step_cost_per_step))
            net_gain = expected_gain - step_cost
            if net_gain <= self.minimum_net_bonus_gain:
                results.append({
                    "status": "rejected_no_measurable_net_gain",
                    "action_signature": signature,
                    "expected_bonus_gain": round(expected_gain, 6),
                    "step_opportunity_cost": round(step_cost, 6),
                    "net_gain": round(net_gain, 6),
                })
                continue
            results.append({
                "status": "viable",
                "action_signature": signature,
                "expected_bonus_gain": round(expected_gain, 6),
                "step_opportunity_cost": round(step_cost, 6),
                "net_gain": round(net_gain, 6),
                "extra_steps": extra_steps,
                "completion_probability_before": float(before),
                "completion_probability_after": float(after),
                "evidence": evidence,
            })
        return results

    def analyze(
        self,
        tracks: dict[str, Any] | None,
        motion_forecast: dict[str, Any] | None,
        bonus_candidates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        self.decisions += 1
        dynamics = self.predict_object_positions(tracks, motion_forecast)
        bonuses = self.evaluate_bonus_candidates(bonus_candidates)
        viable = [row for row in bonuses if row.get("status") == "viable"]
        return {
            "decision": self.decisions,
            "object_dynamics": dynamics,
            "bonus_evaluations": bonuses,
            "viable_bonus_action_signatures": [row["action_signature"] for row in viable],
            "bonus_policy": "pursue only evidenced positive net gain with no reduction in completion probability",
        }

    def record_transition(
        self, before: Any, after: Any, before_tracks: dict[str, Any] | None,
        after_tracks: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Compare pending one-step predictions with positions from the actual next frame."""
        before_id = state_signature(before)
        predicted = {
            row["track_id"]: row["predicted_next_position"]
            for row in self.predict_object_positions(before_tracks).get("objects", [])
            if row.get("track_id") is not None
        }
        actual = {
            track.get("track_id"): _position(track)
            for track in (after_tracks or {}).get("tracks", [])
            if isinstance(track, dict) and track.get("track_id") is not None
            and _position(track) is not None and track.get("missed_frames", 0) == 0
        }
        comparisons = []
        for track_id, expected in predicted.items():
            observed = actual.get(track_id)
            if observed is None:
                continue
            comparisons.append({
                "track_id": track_id,
                "predicted_position": expected,
                "observed_position": observed,
                "euclidean_error": round(hypot(expected[0] - observed[0], expected[1] - observed[1]), 4),
            })
        record = {
            "before_state": before_id,
            "after_state": state_signature(after),
            "prediction_comparisons": comparisons,
            "prediction_count": len(predicted),
            "matched_count": len(comparisons),
            "semantics": "actual positions are observed; predicted positions remain separately labeled",
        }
        self.records.append(record)
        self.records = self.records[-self.max_records:]
        return deepcopy(record)

    def snapshot(self) -> dict[str, Any]:
        return {
            "decisions": self.decisions,
            "records_retained": len(self.records),
            "recent_records": deepcopy(self.records[-8:]),
            "step_cost_per_step": self.step_cost_per_step,
            "minimum_net_bonus_gain": self.minimum_net_bonus_gain,
            "memory_partition": "game_dynamics; separate from world_model, transition_model and gameplay_memory",
        }
