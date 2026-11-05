"""Integrated observation/learning/action-selection loop for ARC-AGI-3.

This is a bounded, evidence-driven agent controller. It does not invent a game
transition simulator: planning uses observed outcomes and the current legal-action
list supplied by the official environment.
"""
from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from arc3.hypothesis_engine import HypothesisEngine
from arc3.world_model import (
    WorldModel, action_family, action_signature, canonical_json, state_signature,
)


@dataclass
class Arc3CognitiveAgent:
    """UPI-ARC3 controller combining world-model evidence and hypothesis tracking."""
    max_state_action_memory: int = 128
    world_model: WorldModel = field(default_factory=WorldModel)
    hypothesis_engine: HypothesisEngine = field(default_factory=HypothesisEngine)
    attempts_by_state: OrderedDict[str, set[str]] = field(default_factory=OrderedDict)
    decisions: int = 0
    last_diagnostics: dict[str, Any] = field(default_factory=dict)

    def _attempts(self, state_id: str) -> set[str]:
        attempts = self.attempts_by_state.get(state_id)
        if attempts is None:
            attempts = set()
            self.attempts_by_state[state_id] = attempts
        self.attempts_by_state.move_to_end(state_id)
        while len(self.attempts_by_state) > self.max_state_action_memory:
            self.attempts_by_state.popitem(last=False)
        return attempts

    @staticmethod
    def _base_score(action: Any) -> float:
        if isinstance(action, dict):
            value = action.get("score", action.get("priority", 0.0))
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                number = float(value)
                if math.isfinite(number):
                    return number
        return 0.0

    def select_action(
        self,
        observation: Any,
        legal_action_records: list[Any],
        navigation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Choose only from supplied legal action records; return auditable factors."""
        self.hypothesis_engine.observe(observation, navigation)
        observed = self.world_model.observe(observation)
        state_id = observed["state_id"]
        attempted = self._attempts(state_id)
        if not legal_action_records:
            self.last_diagnostics = {
                "status": "no_legal_actions", "state_id": state_id,
                "features": observed["features"],
            }
            return {"action": None, "status": "no_legal_actions",
                    "diagnostics": dict(self.last_diagnostics)}

        ranked = []
        for index, action in enumerate(legal_action_records):
            key = action_signature(action)
            family = action_family(action)
            stats = self.world_model.action_stats(action)
            tries = int(stats["attempts"])
            unchanged = int(stats["unchanged"])
            progress = int(stats["explicit_progress"])
            wins = int(stats["terminal_wins"])
            already_tried = key in attempted

            # These are transparent heuristic utilities, not probabilities.
            novelty_bonus = 8.0 if not already_tried else -12.0
            family_exploration_bonus = 3.0 / math.sqrt(1.0 + tries)
            no_change_penalty = (
                5.0 * unchanged / tries if tries >= 2 else 0.0
            )
            evidence_bonus = min(20.0, 8.0 * progress) + min(40.0, 20.0 * wins)
            base = self._base_score(action)
            total = (
                base + novelty_bonus + family_exploration_bonus
                - no_change_penalty + evidence_bonus
            )
            ranked.append({
                "index": index, "action": action, "key": key,
                "family": family, "score": total, "base_score": base,
                "novelty_bonus": novelty_bonus,
                "family_exploration_bonus": family_exploration_bonus,
                "no_change_penalty": no_change_penalty,
                "observed_progress_bonus": evidence_bonus,
                "already_tried_in_state": already_tried,
                "historical_attempts_for_family": tries,
            })

        # Stable tie-breaking preserves the environment-provided legal-action order.
        ranked.sort(key=lambda row: (-row["score"], row["index"]))
        chosen = ranked[0]
        attempted.add(chosen["key"])
        self.decisions += 1
        self.last_diagnostics = {
            "status": "selected",
            "decision": self.decisions,
            "state_id": state_id,
            "state_visit_count": observed["visit_count"],
            "state_features": observed["features"],
            "legal_action_count": len(legal_action_records),
            "unique_actions_tried_in_state": len(attempted),
            "all_actions_previously_tried_in_state": all(
                row["already_tried_in_state"] for row in ranked
            ),
            "selected_action": chosen["action"],
            "selected_action_score": round(chosen["score"], 4),
            "selected_factors": {
                key: round(value, 4) if isinstance(value, float) else value
                for key, value in chosen.items()
                if key not in {"action", "key", "index", "score"}
            },
            "top_candidates": [
                {
                    "action": row["action"],
                    "score": round(row["score"], 4),
                    "already_tried": row["already_tried_in_state"],
                }
                for row in ranked[:5]
            ],
            "score_semantics": "heuristic utility; not a calibrated probability",
        }
        return {
            "action": chosen["action"],
            "status": "selected",
            "diagnostics": dict(self.last_diagnostics),
        }

    def record_transition(self, action: Any, before: Any, after: Any) -> dict[str, Any]:
        """Update empirical transition records and evidence ledger after an action."""
        event = self.world_model.record_transition(action, before, after)
        self.hypothesis_engine.record_transition(event)
        self.world_model.observe(after)
        return event

    def snapshot(self) -> dict[str, Any]:
        return {
            "decisions": self.decisions,
            "world_model": self.world_model.snapshot(),
            "hypothesis_engine": self.hypothesis_engine.snapshot(),
            "recent_decision": dict(self.last_diagnostics),
        }
