"""Emoji-native ARC-AGI-3 agent using existing strategy priors and belief MCTS."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from arc3.belief_mcts import BeliefMCTS
from arc3.glyph_dsl import DEFAULT_PROGRAM, compile_program, parse_program, render_protocol, validate_program
from arc3.strategy_studio import brainstorm_action_priors
from arc3.transition_learner import TransitionLearner
from arc3.world_model import WorldModel

@dataclass
class GlyphArc3Agent:
    simulations: int = 64
    depth: int = 4
    exploration: float = 1.2
    world_model: WorldModel = field(default_factory=WorldModel)
    transition_model: TransitionLearner = field(default_factory=TransitionLearner)
    decisions: int = 0
    last_diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.program = parse_program(DEFAULT_PROGRAM)
        validate_program(self.program)

    def select_action(self, observation: Any, legal_actions: list[Any],
                      navigation: dict[str, Any] | None = None) -> dict[str, Any]:
        observed = self.world_model.observe(observation)
        self.world_model.register_legal_actions(observation, legal_actions)
        if not legal_actions:
            return {"action": None, "status": "no_legal_actions", "diagnostics": {}}
        studio = brainstorm_action_priors(legal_actions, navigation, self.world_model)
        result = BeliefMCTS(
            self.world_model, self.transition_model, self.simulations, self.depth,
            self.exploration, seed=self.decisions
        ).search(observation, legal_actions, studio["priors"])
        self.decisions += 1
        self.last_diagnostics = {
            "decision": self.decisions, "state_id": observed["state_id"],
            "dsl_operations": [item.operation for item in self.program.instructions],
            "dsl_compiled": compile_program(self.program),
            "glyph_protocol": render_protocol({
                "grid_shape": observed.get("shape"),
                "legal_action_count": len(legal_actions),
                "selected_action": result.get("action", {}).get("name") if isinstance(result.get("action"), dict) else None,
                "object_count": len(observed.get("objects", [])) if isinstance(observed.get("objects"), list) else None,
                "mcts_depth": self.depth, "mcts_simulations": self.simulations,
                "outcome": "pending",
            }),
            "strategy_studio": studio, "belief_mcts": result.get("diagnostics", {}),
            "transition_learner": self.transition_model.snapshot(),
        }
        result["diagnostics"] = self.last_diagnostics
        return result

    def record_transition(self, action: Any, before: Any, after: Any) -> dict[str, Any]:
        event = self.world_model.record_transition(action, before, after)
        learned = self.transition_model.observe(action, before, after)
        self.world_model.observe(after)
        return {"observed_transition": event, "grid_template_learned": learned}

    def snapshot(self):
        return {"decisions": self.decisions, "world_model": self.world_model.snapshot(),
                "transition_model": self.transition_model.snapshot(),
                "last_decision": self.last_diagnostics,
                "policy": "emoji DSL + strategy priors + belief MCTS"}
