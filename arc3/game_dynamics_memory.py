"""Separate, evidence-gated memory for one-step game dynamics and bonus decisions.

This partition supplements (and never replaces) the world model, transition learner,
or hierarchical gameplay event log. Forecasts remain predictions until matched against
a subsequent real observation. Bonus pursuit requires explicit measurable reward and
completion-risk evidence; unknown semantics are not treated as a bonus.
"""
from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from math import hypot
from typing import Any

from arc3.object_perception import perceive_objects
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
    step_cost_per_step: float | None = None
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
            if extra_steps > 0 and self.step_cost_per_step is None:
                results.append({
                    "status": "rejected_insufficient_evidence",
                    "reason": "No configured score-to-step exchange rate; extra-step opportunity cost cannot be measured.",
                    "action_signature": signature,
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
            step_cost = int(extra_steps) * max(0.0, float(self.step_cost_per_step or 0.0))
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

    def predict_action_outcomes(
        self, observation: Any, legal_actions: list[Any], transition_model: Any,
    ) -> list[dict[str, Any]]:
        """Predict candidate-specific next scenes only from matching observed templates."""
        rows = []
        for action in legal_actions:
            predictions = transition_model.predict(action, observation, limit=2) if transition_model else []
            outcomes = []
            for prediction in predictions:
                predicted_observation = prediction.get("observation")
                perception = perceive_objects(predicted_observation)
                outcomes.append({
                    "predicted_objects": [
                        {
                            "center": obj.get("center"),
                            "bbox": obj.get("bbox"),
                            "shape": obj.get("shape"),
                            "dominant_color": obj.get("dominant_color"),
                        }
                        for obj in perception.get("objects", [])
                    ],
                    "support_count": prediction.get("support_count", 0),
                    "confidence_proxy": prediction.get("confidence_proxy", 0.0),
                    "evidence": prediction.get("evidence", "unknown"),
                    "prediction_is_observation": False,
                })
            rows.append({
                "action_signature": action_signature(action),
                "action_name": action.get("name", "unknown") if isinstance(action, dict) else str(action),
                "prediction_count": len(outcomes),
                "outcomes": outcomes,
                "status": "observed_template_prediction" if outcomes else "no_matching_observed_template",
            })
        return rows

    def shortest_observed_route(
        self, observation: Any, world_model: Any,
    ) -> dict[str, Any]:
        """Find the fewest-step route to a previously observed progress/win state.

        This is exact BFS over the bounded observed transition graph only. It does
        not invent edges or claim an optimal route through unobserved game states.
        """
        start = state_signature(observation)
        adjacency: dict[str, list[dict[str, Any]]] = {}
        goals: set[str] = set()
        for event in getattr(world_model, "transition_history", []):
            before = event.get("before_state")
            after = event.get("after_state")
            action = event.get("action")
            if not isinstance(before, str) or not isinstance(after, str) or action is None:
                continue
            adjacency.setdefault(before, []).append({
                "after_state": after,
                "action_signature": action_signature(action),
                "action": deepcopy(action),
            })
            if event.get("explicit_progress_observed") or event.get("terminal_win_observed"):
                goals.add(after)
        if not goals:
            return {
                "status": "no_observed_progress_route",
                "known_edges": sum(len(edges) for edges in adjacency.values()),
                "optimality_scope": "observed_transition_graph_only",
            }
        queue = deque([(start, [])])
        visited = {start}
        while queue:
            state_id, path = queue.popleft()
            if state_id in goals:
                return {
                    "status": "route_found",
                    "shortest_observed_steps": len(path),
                    "first_action_signature": path[0]["action_signature"] if path else None,
                    "path": path,
                    "known_edges": sum(len(edges) for edges in adjacency.values()),
                    "optimality_scope": "shortest_path_within_bounded_observed_transition_graph",
                }
            for edge in adjacency.get(state_id, []):
                successor = edge["after_state"]
                if successor in visited:
                    continue
                visited.add(successor)
                queue.append((successor, path + [edge]))
        return {
            "status": "no_observed_progress_route",
            "known_edges": sum(len(edges) for edges in adjacency.values()),
            "optimality_scope": "observed_transition_graph_only",
        }

    def analyze(
        self,
        tracks: dict[str, Any] | None,
        motion_forecast: dict[str, Any] | None,
        bonus_candidates: list[dict[str, Any]] | None = None,
        observation: Any = None,
        legal_actions: list[Any] | None = None,
        transition_model: Any = None,
        world_model: Any = None,
    ) -> dict[str, Any]:
        self.decisions += 1
        dynamics = self.predict_object_positions(tracks, motion_forecast)
        action_predictions = self.predict_action_outcomes(
            observation, legal_actions or [], transition_model
        ) if observation is not None else []
        route = self.shortest_observed_route(observation, world_model) if observation is not None and world_model is not None else {"status": "not_evaluated"}
        bonuses = self.evaluate_bonus_candidates(bonus_candidates)
        viable = [row for row in bonuses if row.get("status") == "viable"]
        return {
            "decision": self.decisions,
            "object_dynamics": dynamics,
            "action_conditioned_predictions": action_predictions,
            "minimum_step_route": route,
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
