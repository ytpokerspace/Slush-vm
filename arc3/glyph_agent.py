"""Emoji-native ARC-AGI-3 agent using existing strategy priors and belief MCTS."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from arc3.belief_mcts import BeliefMCTS
from arc3.action_glyph_scorer import ActionProbabilityScorer
from arc3.game_dynamics_memory import GameDynamicsMemory
from arc3.glyph_dsl import DEFAULT_PROGRAM, compile_program, parse_program, render_protocol, validate_program
from arc3.strategy_studio import brainstorm_action_priors
from arc3.transition_learner import TransitionLearner
from arc3.world_model import action_signature
from arc3.world_model import WorldModel

@dataclass
class GlyphArc3Agent:
    simulations: int = 64
    depth: int = 4
    exploration: float = 1.2
    world_model: WorldModel = field(default_factory=WorldModel)
    transition_model: TransitionLearner = field(default_factory=TransitionLearner)
    decisions: int = 0
    action_scorer: ActionProbabilityScorer = field(default_factory=ActionProbabilityScorer)
    dynamics_memory: GameDynamicsMemory = field(default_factory=GameDynamicsMemory)
    last_diagnostics: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.program = parse_program(DEFAULT_PROGRAM)
        validate_program(self.program)

    def select_action(self, observation: Any, legal_actions: list[Any],
                      navigation: dict[str, Any] | None = None,
                      dynamics_context: dict[str, Any] | None = None) -> dict[str, Any]:
        observed = self.world_model.observe(observation)
        self.world_model.register_legal_actions(observation, legal_actions)
        if not legal_actions:
            return {"action": None, "status": "no_legal_actions", "diagnostics": {}}
        studio = brainstorm_action_priors(legal_actions, navigation, self.world_model)
        result = BeliefMCTS(
            self.world_model, self.transition_model, self.simulations, self.depth,
            self.exploration, seed=self.decisions
        ).search(observation, legal_actions, studio["priors"])
        action_scores = self.action_scorer.score(
            observation, legal_actions, self.world_model, studio["priors"],
            result.get("diagnostics", {}).get("top_candidates", []),
        )
        dynamics_context = dynamics_context or {}
        dynamics = self.dynamics_memory.analyze(
            dynamics_context.get("object_tracks"),
            dynamics_context.get("motion_forecast"),
            dynamics_context.get("bonus_candidates"),
            observation=observation,
            legal_actions=legal_actions,
            transition_model=self.transition_model,
            world_model=self.world_model,
        )
        viable_bonus = {
            row["action_signature"]: row
            for row in dynamics["bonus_evaluations"]
            if row.get("status") == "viable"
        }
        # Bonus routes receive only a small, capped preference after passing the
        # evidence and completion-risk gate. They cannot manufacture legal actions.
        route = dynamics.get("minimum_step_route", {})
        route_signature = route.get("first_action_signature") if route.get("status") == "route_found" else None
        for row in action_scores:
            bonus = viable_bonus.get(row["action_signature"])
            if bonus:
                normalized_gain = bonus["net_gain"] / (1.0 + abs(bonus["net_gain"]))
                row["factors"]["bonus_preference"] = round(0.05 * normalized_gain, 6)
            else:
                row["factors"]["bonus_preference"] = 0.0
            # Prefer the first step of a verified shortest route only when it is
            # still present in the current legal action set.
            row["factors"]["observed_route_preference"] = 0.10 if row["action_signature"] == route_signature else 0.0
            row["factors"]["utility_score"] = round(
                row["factors"]["utility_score"]
                + row["factors"]["bonus_preference"]
                + row["factors"]["observed_route_preference"], 6
            )
        action_scores.sort(key=lambda row: (-row["factors"]["utility_score"], row["index"]))
        if action_scores:
            selected_signature = action_scores[0]["action_signature"]
            result["action"] = next(
                action for action in legal_actions
                if action_signature(action) == selected_signature
            )
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
            "action_probability_scores": action_scores,
            "game_dynamics_memory": dynamics,
            "selected_action_glyph": action_scores[0] if action_scores else None,
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
                "game_dynamics_memory": self.dynamics_memory.snapshot(),
                "last_decision": self.last_diagnostics,
                "policy": "emoji DSL + strategy priors + belief MCTS"}
