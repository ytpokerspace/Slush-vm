"""Bounded, evidence-grounded Monte Carlo tree search for ARC-AGI-3.

Searches only transitions observed in this episode. Unknown transitions terminate a
rollout and are evaluated with a transparent prior; the code never fabricates a
successor state. The root action is always selected from the supplied legal actions.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Callable

from arc3.world_model import action_signature, state_signature


@dataclass
class TreeEdge:
    action: Any
    prior: float
    visits: int = 0
    value_sum: float = 0.0
    progress_trials: int = 0
    progress_successes: int = 0
    known_successors: int = 0
    unknown_successors: int = 0
    child_state_id: str | None = None

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0

    @property
    def progress_probability(self) -> float:
        # Uniform Beta(1,1) prior; posterior mean, not a calibrated game-win chance.
        return (self.progress_successes + 1.0) / (self.progress_trials + 2.0)


@dataclass
class TreeNode:
    state_id: str
    visits: int = 0
    edges: dict[str, TreeEdge] = field(default_factory=dict)


class ShallowMCTS:
    def __init__(
        self,
        world_model: Any,
        depth: int = 3,
        simulations: int = 32,
        exploration: float = 1.25,
        seed: int = 0,
    ) -> None:
        if depth < 1 or simulations < 1:
            raise ValueError("depth and simulations must be positive")
        self.world_model = world_model
        self.depth = depth
        self.simulations = simulations
        self.exploration = exploration
        self.rng = random.Random(seed)
        self.nodes: dict[str, TreeNode] = {}

    @staticmethod
    def _wilson(successes: int, trials: int, z: float = 1.96) -> list[float]:
        if trials <= 0:
            return [0.0, 1.0]
        p = successes / trials
        denominator = 1.0 + z * z / trials
        center = (p + z * z / (2.0 * trials)) / denominator
        margin = (
            z * math.sqrt((p * (1.0 - p) / trials) + z * z / (4.0 * trials * trials))
            / denominator
        )
        return [max(0.0, center - margin), min(1.0, center + margin)]

    def _edge_prior(self, action: Any, priors: dict[str, float]) -> float:
        return max(1e-6, float(priors.get(action_signature(action), 1e-6)))

    def _get_node(self, state_id: str) -> TreeNode:
        if state_id not in self.nodes:
            self.nodes[state_id] = TreeNode(state_id=state_id)
        return self.nodes[state_id]

    def _ensure_edges(
        self, node: TreeNode, legal_actions: list[Any], priors: dict[str, float]
    ) -> None:
        for action in legal_actions:
            key = action_signature(action)
            if key not in node.edges:
                stats = self.world_model.edge_stats_by_ids(node.state_id, action)
                node.edges[key] = TreeEdge(
                    action=action,
                    prior=self._edge_prior(action, priors),
                    progress_trials=int(stats.get("attempts", 0)),
                    progress_successes=int(stats.get("verified_progress_or_win", 0)),
                    known_successors=int(stats.get("known_successors", 0)),
                    unknown_successors=int(stats.get("unknown_successors", 0)),
                    child_state_id=stats.get("most_likely_successor"),
                )

    def _select(self, node: TreeNode) -> TreeEdge:
        root_scale = math.sqrt(max(1, node.visits))
        return max(
            node.edges.values(),
            key=lambda edge: (
                edge.mean_value
                + self.exploration * edge.prior * root_scale / (1 + edge.visits),
                edge.prior,
            ),
        )

    def _edge_reward(self, edge: TreeEdge) -> float:
        stats = self.world_model.edge_stats_by_ids(
            self._active_state_id, edge.action
        )
        attempts = int(stats.get("attempts", 0))
        successes = int(stats.get("verified_progress_or_win", 0))
        changed = int(stats.get("changed", 0))
        # Small shaping reward for a new observed state; explicit progress dominates.
        progress_mean = (successes + 1.0) / (attempts + 2.0)
        change_mean = (changed + 1.0) / (attempts + 2.0)
        return min(1.0, 0.80 * progress_mean + 0.15 * change_mean + 0.05 * edge.prior)

    def _simulate(
        self,
        root_state_id: str,
        root_legal_actions: list[Any],
        root_priors: dict[str, float],
        leaf_value: Callable[[str], float] | None,
    ) -> None:
        node = self._get_node(root_state_id)
        path: list[tuple[TreeNode, TreeEdge, float]] = []
        current_state = root_state_id
        value = 0.5
        for depth_index in range(self.depth):
            if depth_index == 0:
                legal = root_legal_actions
            else:
                legal = self.world_model.legal_actions_for_state(current_state)
            if not legal:
                if leaf_value:
                    value = max(0.0, min(1.0, float(leaf_value(current_state))))
                break
            node = self._get_node(current_state)
            self._ensure_edges(node, legal, root_priors if depth_index == 0 else {})
            edge = self._select(node)
            self._active_state_id = current_state
            reward = self._edge_reward(edge)
            successor = self.world_model.sampled_successor(
                current_state, edge.action, self.rng
            )
            if successor is None:
                # Unknown model edge: use a conservative leaf prior and stop.
                value = 0.65 * edge.progress_probability + 0.35 * edge.prior
                edge.unknown_successors += 1
                path.append((node, edge, reward))
                break
            edge.known_successors += 1
            edge.child_state_id = successor
            path.append((node, edge, reward))
            current_state = successor
            node = self._get_node(current_state)
            value = leaf_value(current_state) if leaf_value else 0.5
            value = max(0.0, min(1.0, float(value)))
        # Discounted backup; no environment action is taken during a simulation.
        for parent, edge, reward in reversed(path):
            value = 0.65 * reward + 0.35 * value
            edge.visits += 1
            edge.value_sum += value
            parent.visits += 1

    def search(
        self,
        observation: Any,
        legal_actions: list[Any],
        priors: dict[str, float],
        leaf_value: Callable[[str], float] | None = None,
    ) -> dict[str, Any]:
        root_id = state_signature(observation)
        if not legal_actions:
            return {"action": None, "status": "no_legal_actions", "diagnostics": {}}
        self._active_state_id = root_id
        root = self._get_node(root_id)
        self._ensure_edges(root, legal_actions, priors)
        for _ in range(self.simulations):
            self._simulate(root_id, legal_actions, priors, leaf_value)
        ranked = []
        for index, action in enumerate(legal_actions):
            edge = root.edges[action_signature(action)]
            stats = self.world_model.edge_stats_by_ids(root_id, action)
            trials = int(stats.get("attempts", 0))
            successes = int(stats.get("verified_progress_or_win", 0))
            ranked.append({
                "index": index,
                "action": action,
                "visits": edge.visits,
                "mean_search_value": round(edge.mean_value, 6),
                "strategy_prior": round(edge.prior, 6),
                "observed_trials": trials,
                "observed_progress_or_win": successes,
                "progress_probability_posterior_mean": round(
                    (successes + 1.0) / (trials + 2.0), 6
                ),
                "empirical_success_rate": round(successes / trials, 6) if trials else None,
                "wilson_95_interval": self._wilson(successes, trials),
                "known_successors": edge.known_successors,
                "unknown_successors": edge.unknown_successors,
            })
        ranked.sort(key=lambda row: (-row["visits"], -row["mean_search_value"], row["index"]))
        chosen = ranked[0]
        return {
            "action": chosen["action"],
            "status": "selected",
            "diagnostics": {
                "algorithm": "shallow_mcts_over_observed_transition_graph",
                "depth_limit": self.depth,
                "simulations": self.simulations,
                "exploration_constant": self.exploration,
                "root_state_id": root_id,
                "selected_action": chosen["action"],
                "selected_progress_probability_posterior_mean": chosen["progress_probability_posterior_mean"],
                "selected_empirical_success_rate": chosen["empirical_success_rate"],
                "selected_wilson_95_interval": chosen["wilson_95_interval"],
                "top_candidates": ranked[:8],
                "probability_semantics": (
                    "Beta(1,1) posterior mean for observed explicit level progress or terminal win; "
                    "not a calibrated probability of eventual game completion"
                ),
                "model_boundary": (
                    "Rollouts use only observed transitions. Unknown transitions stop at a conservative "
                    "prior leaf; no unobserved successor is fabricated."
                ),
            },
        }
