"""Bounded MCTS with explicit separation of observed and predicted transitions."""
from __future__ import annotations
import math
import random
from typing import Any
from arc3.world_model import action_signature, state_signature

class BeliefMCTS:
    """Search supplied legal root actions; predictions are one-step leaves only."""
    def __init__(self, world_model: Any, transition_model: Any = None,
                 simulations: int = 64, depth: int = 4, exploration: float = 1.2,
                 seed: int = 0):
        if simulations < 1 or depth < 1:
            raise ValueError("simulations and depth must be positive")
        self.world_model, self.transition_model = world_model, transition_model
        self.simulations, self.depth = simulations, depth
        self.exploration, self.rng = exploration, random.Random(seed)

    @staticmethod
    def _value(observation: Any) -> float:
        if not isinstance(observation, dict):
            return 0.5
        state = str(observation.get("__arc3_state", "")).upper()
        if state == "WIN":
            return 1.0
        if state in {"GAME_OVER", "LOSE", "LOSS"}:
            return 0.0
        completed = observation.get("__arc3_levels_completed")
        if isinstance(completed, int) and completed > 0:
            return min(0.95, 0.65 + 0.05 * completed)
        return 0.5

    def search(self, observation: Any, legal_actions: list[Any],
               priors: dict[str, float] | None = None) -> dict[str, Any]:
        if not legal_actions:
            return {"action": None, "status": "no_legal_actions", "diagnostics": {}}
        priors = priors or {}
        root_id = state_signature(observation)
        stats = {action_signature(a): {"visits": 0, "value": 0.0,
                                       "observed": 0, "predicted": 0}
                 for a in legal_actions}
        for _ in range(self.simulations):
            total = sum(s["visits"] for s in stats.values())
            def score(action):
                key = action_signature(action)
                item = stats[key]
                prior = max(1e-6, float(priors.get(key, 1.0 / len(legal_actions))))
                mean_value = item["value"] / item["visits"] if item["visits"] else 0.0
                return mean_value + (
                    self.exploration * prior * math.sqrt(total + 1) / (1 + item["visits"])
                )
            action = max(legal_actions, key=score)
            key = action_signature(action)
            item = stats[key]
            successor = self.world_model.sampled_successor(root_id, action, self.rng)
            if successor is not None:
                item["observed"] += 1
                value = self._value(self.world_model.state_observations.get(successor))
                current = successor
                for _depth in range(1, self.depth):
                    actions = self.world_model.legal_actions_for_state(current)
                    if not actions:
                        break
                    next_action = self.rng.choice(actions)
                    next_state = self.world_model.sampled_successor(current, next_action, self.rng)
                    if next_state is None:
                        break
                    current = next_state
                    value = self._value(self.world_model.state_observations.get(current))
                    if value in (0.0, 1.0):
                        break
            else:
                predictions = self.transition_model.predict(action, observation) if self.transition_model else []
                if predictions:
                    item["predicted"] += 1
                    prediction = predictions[self.rng.randrange(len(predictions))]
                    confidence = float(prediction.get("confidence_proxy", 0.0))
                    value = 0.5 + confidence * (self._value(prediction["observation"]) - 0.5)
                else:
                    value = 0.5
            item["visits"] += 1
            item["value"] += value
        ranked = []
        for index, action in enumerate(legal_actions):
            key, item = action_signature(action), stats[action_signature(action)]
            ranked.append({
                "index": index, "action": action, "visits": item["visits"],
                "mean_value": round(item["value"] / item["visits"], 6) if item["visits"] else 0.0,
                "observed_rollouts": item["observed"], "predicted_rollouts": item["predicted"],
                "strategy_prior": float(priors.get(key, 1.0 / len(legal_actions))),
            })
        ranked.sort(key=lambda row: (-row["visits"], -row["mean_value"], row["index"]))
        return {"action": ranked[0]["action"], "status": "selected", "diagnostics": {
            "algorithm": "belief_mcts_observed_graph_plus_predicted_leaf",
            "depth_limit": self.depth, "simulations": self.simulations,
            "root_state_id": root_id, "top_candidates": ranked[:8],
            "prediction_semantics": "predicted outcomes are one-step leaves, never observed transitions",
        }}
