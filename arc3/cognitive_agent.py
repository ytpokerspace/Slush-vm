"""Integrated ARC-AGI-3 strategy synthesis and shallow-MCTS controller."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from arc3.hypothesis_engine import HypothesisEngine
from arc3.shallow_mcts import ShallowMCTS
from arc3.strategy_studio import brainstorm_action_priors
from arc3.world_model import WorldModel, action_signature, state_signature


@dataclass
class Arc3CognitiveAgent:
    """UPI-ARC3 agent: brainstorm alternatives, then search a few observed steps."""
    max_state_action_memory: int = 128
    mcts_depth: int = 3
    mcts_simulations: int = 32
    mcts_exploration: float = 1.25
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

    def _leaf_value(self, state_id: str) -> float:
        observation = self.world_model.state_observations.get(state_id)
        if not isinstance(observation, dict):
            return 0.5
        state = str(observation.get("__arc3_state") or "").upper()
        if state == "WIN":
            return 1.0
        if state in {"GAME_OVER", "LOSE", "LOSS"}:
            return 0.0
        completed = observation.get("__arc3_levels_completed")
        if isinstance(completed, int) and not isinstance(completed, bool) and completed > 0:
            return min(0.95, 0.65 + 0.05 * completed)
        return 0.5

    def select_action(
        self,
        observation: Any,
        legal_action_records: list[Any],
        navigation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Choose a supplied legal action using Studio priors and bounded MCTS."""
        self.hypothesis_engine.observe(observation, navigation)
        observed = self.world_model.observe(observation)
        state_id = observed["state_id"]
        attempted = self._attempts(state_id)
        if not legal_action_records:
            self.last_diagnostics = {
                "status": "no_legal_actions",
                "state_id": state_id,
                "features": observed["features"],
            }
            return {
                "action": None, "status": "no_legal_actions",
                "diagnostics": dict(self.last_diagnostics),
            }

        self.world_model.register_legal_actions(observation, legal_action_records)
        studio = brainstorm_action_priors(
            legal_action_records, navigation, self.world_model, attempted
        )
        search = ShallowMCTS(
            self.world_model,
            depth=self.mcts_depth,
            simulations=self.mcts_simulations,
            exploration=self.mcts_exploration,
            seed=self.decisions,
        )
        result = search.search(
            observation, legal_action_records, studio["priors"], self._leaf_value
        )
        chosen = result["action"]
        if chosen is None:
            self.last_diagnostics = {
                "status": result["status"], "state_id": state_id,
                "strategy_studio": studio,
                "mcts": result.get("diagnostics", {}),
            }
            return {"action": None, "status": result["status"],
                    "diagnostics": dict(self.last_diagnostics)}

        attempted.add(action_signature(chosen))
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
                action_signature(action) in attempted for action in legal_action_records
            ),
            "selected_action": chosen,
            "strategy_studio": studio,
            "mcts": result["diagnostics"],
            "decision_policy": "strategy synthesis followed by shallow evidence-grounded MCTS",
        }
        return {
            "action": chosen,
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
            "search_configuration": {
                "algorithm": "shallow MCTS over observed transitions",
                "depth": self.mcts_depth,
                "simulations": self.mcts_simulations,
                "exploration": self.mcts_exploration,
            },
        }
