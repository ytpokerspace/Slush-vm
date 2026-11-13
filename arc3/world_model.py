"""Evidence-bounded state and action-effect model for ARC-AGI-3.

The model stores observed transitions. It does not pretend to simulate unseen game
states or infer causality beyond the controlled action/observation sequence.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any
import random


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=repr)


def state_signature(observation: Any) -> str:
    return hashlib.sha256(canonical_json(observation).encode("utf-8")).hexdigest()


def action_name(action: Any) -> str:
    if isinstance(action, dict):
        return str(action.get("name", action.get("button", action.get("action", "unknown"))))
    return str(action)


def action_signature(action: Any) -> str:
    """Identify the environment action, excluding ephemeral policy-ranking metadata."""
    if isinstance(action, dict):
        action = {
            key: value for key, value in action.items()
            if key not in {"score", "priority", "strategy_prior", "mcts_score", "diagnostics"}
        }
    return canonical_json(action)


def action_family(action: Any) -> str:
    """Generalize action records by action name, not by unverified game semantics."""
    return action_name(action)


def observation_features(observation: Any) -> dict[str, Any]:
    """Extract conservative structural features from grid/frame observations."""
    if not isinstance(observation, dict):
        return {"kind": type(observation).__name__}
    source = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(source, list):
        return {
            "kind": "structured",
            "keys": sorted(str(key) for key in observation),
            "state": observation.get("__arc3_state"),
            "levels_completed": observation.get("__arc3_levels_completed"),
        }
    if source and isinstance(source[0], list) and source[0] and isinstance(source[0][0], list):
        layers = source
    else:
        layers = [source]
    shapes: list[list[int]] = []
    counts: Counter[str] = Counter()
    nonzero = 0
    cells = 0
    for layer in layers:
        if not isinstance(layer, list):
            continue
        rows = [row for row in layer if isinstance(row, list)]
        shapes.append([len(rows), max((len(row) for row in rows), default=0)])
        for row in rows:
            for cell in row:
                counts[canonical_json(cell)] += 1
                cells += 1
                if cell not in (0, "0", None, False):
                    nonzero += 1
    return {
        "kind": "frame" if "frame" in observation else "grid",
        "layer_shapes": shapes,
        "cell_count": cells,
        "nonzero_count": nonzero,
        "distinct_values": len(counts),
        "value_counts": dict(counts.most_common(16)),
        "state": observation.get("__arc3_state"),
        "levels_completed": observation.get("__arc3_levels_completed"),
    }


@dataclass
class ActionEffectStats:
    attempts: int = 0
    changed: int = 0
    unchanged: int = 0
    novel_next_states: int = 0
    explicit_progress: int = 0
    terminal_wins: int = 0
    recent: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "novel_next_states": self.novel_next_states,
            "explicit_progress": self.explicit_progress,
            "terminal_wins": self.terminal_wins,
            "recent": list(self.recent[-12:]),
        }


@dataclass
class WorldModel:
    """A bounded empirical record of observed states and action outcomes."""
    max_history: int = 256
    state_visits: Counter[str] = field(default_factory=Counter)
    action_effects: dict[str, ActionEffectStats] = field(default_factory=dict)
    action_signature_effects: dict[str, ActionEffectStats] = field(default_factory=dict)
    exact_transitions: dict[str, str] = field(default_factory=dict)
    transition_history: list[dict[str, Any]] = field(default_factory=list)
    max_states: int = 128
    state_observations: dict[str, Any] = field(default_factory=dict)
    state_legal_actions: dict[str, list[Any]] = field(default_factory=dict)
    state_order: list[str] = field(default_factory=list)
    transition_counts: dict[str, Counter[str]] = field(default_factory=dict)
    edge_outcomes: dict[str, dict[str, int]] = field(default_factory=dict)

    def _remember_state(self, key: str, observation: Any) -> None:
        if key not in self.state_observations:
            self.state_order.append(key)
        self.state_observations[key] = observation
        while len(self.state_order) > self.max_states:
            expired = self.state_order.pop(0)
            self.state_observations.pop(expired, None)
            self.state_legal_actions.pop(expired, None)

    def observe(self, observation: Any) -> dict[str, Any]:
        key = state_signature(observation)
        self.state_visits[key] += 1
        self._remember_state(key, observation)
        return {
            "state_id": key,
            "visit_count": self.state_visits[key],
            "features": observation_features(observation),
        }

    def register_legal_actions(self, observation: Any, legal_actions: list[Any]) -> str:
        """Remember only actions explicitly supplied as legal by the environment."""
        key = state_signature(observation)
        self._remember_state(key, observation)
        self.state_legal_actions[key] = list(legal_actions)
        return key

    def legal_actions_for_state(self, state_id: str) -> list[Any]:
        return list(self.state_legal_actions.get(state_id, []))

    @staticmethod
    def _edge_key(state_id: str, action: Any) -> str:
        return canonical_json([state_id, action_signature(action)])

    def edge_stats_by_ids(self, state_id: str, action: Any) -> dict[str, Any]:
        key = self._edge_key(state_id, action)
        stats = self.edge_outcomes.get(key, {})
        successors = self.transition_counts.get(key, Counter())
        return {
            "attempts": int(stats.get("attempts", 0)),
            "changed": int(stats.get("changed", 0)),
            "verified_progress_or_win": int(stats.get("verified_progress_or_win", 0)),
            "explicit_progress": int(stats.get("explicit_progress", 0)),
            "terminal_wins": int(stats.get("terminal_wins", 0)),
            "known_successors": len(successors),
            "unknown_successors": 1 if not successors else 0,
            "most_likely_successor": successors.most_common(1)[0][0] if successors else None,
        }

    def sampled_successor(self, state_id: str, action: Any, rng: random.Random) -> str | None:
        """Sample only from successor states actually observed for this exact edge."""
        counts = self.transition_counts.get(self._edge_key(state_id, action))
        if not counts:
            return None
        population: list[str] = []
        for successor, count in counts.items():
            population.extend([successor] * count)
        return rng.choice(population)

    def record_transition(self, action: Any, before: Any, after: Any) -> dict[str, Any]:
        before_key = state_signature(before)
        after_key = state_signature(after)
        family = action_family(action)
        stats = self.action_effects.setdefault(family, ActionEffectStats())
        exact_stats = self.action_signature_effects.setdefault(action_signature(action), ActionEffectStats())
        changed = before_key != after_key
        progress_before = before.get("__arc3_levels_completed") if isinstance(before, dict) else None
        progress_after = after.get("__arc3_levels_completed") if isinstance(after, dict) else None
        progress = (
            isinstance(progress_before, int) and isinstance(progress_after, int)
            and progress_after > progress_before
        )
        terminal = isinstance(after, dict) and str(after.get("__arc3_state", "")).upper() == "WIN"
        next_was_seen = self.state_visits[after_key] > 0
        stats.attempts += 1
        stats.changed += int(changed)
        stats.unchanged += int(not changed)
        stats.novel_next_states += int(changed and not next_was_seen)
        stats.explicit_progress += int(progress)
        stats.terminal_wins += int(terminal)
        exact_stats.attempts += 1
        exact_stats.changed += int(changed)
        exact_stats.unchanged += int(not changed)
        exact_stats.novel_next_states += int(changed and not next_was_seen)
        exact_stats.explicit_progress += int(progress)
        exact_stats.terminal_wins += int(terminal)
        event = {
            "action": action,
            "action_family": family,
            "before_state": before_key,
            "after_state": after_key,
            "observation_changed": changed,
            "next_state_previously_seen": next_was_seen,
            "explicit_progress_observed": progress,
            "terminal_win_observed": terminal,
        }
        stats.recent.append(event)
        del stats.recent[:-12]
        edge_key = self._edge_key(before_key, action)
        self.exact_transitions[edge_key] = after_key
        self.transition_counts.setdefault(edge_key, Counter())[after_key] += 1
        edge = self.edge_outcomes.setdefault(edge_key, {
            "attempts": 0, "changed": 0, "verified_progress_or_win": 0,
            "explicit_progress": 0, "terminal_wins": 0,
        })
        edge["attempts"] += 1
        edge["changed"] += int(changed)
        edge["verified_progress_or_win"] += int(progress or terminal)
        edge["explicit_progress"] += int(progress)
        edge["terminal_wins"] += int(terminal)
        self._remember_state(before_key, before)
        self._remember_state(after_key, after)
        self.transition_history.append(event)
        del self.transition_history[:-self.max_history]
        return event

    def action_stats(self, action: Any) -> dict[str, Any]:
        stats = self.action_effects.get(action_family(action))
        return stats.snapshot() if stats else {
            "attempts": 0, "changed": 0, "unchanged": 0,
            "novel_next_states": 0, "explicit_progress": 0,
            "terminal_wins": 0, "recent": [],
        }

    def action_signature_stats(self, action: Any) -> dict[str, Any]:
        """Return episode-wide outcomes for this exact action, including click data."""
        stats = self.action_signature_effects.get(action_signature(action))
        return stats.snapshot() if stats else {
            "attempts": 0, "changed": 0, "unchanged": 0,
            "novel_next_states": 0, "explicit_progress": 0,
            "terminal_wins": 0, "recent": [],
        }

    def predict_exact(self, observation: Any, action: Any) -> str | None:
        """Return a next-state signature only for an exactly observed state/action pair."""
        key = self._edge_key(state_signature(observation), action)
        return self.exact_transitions.get(key)

    def snapshot(self) -> dict[str, Any]:
        return {
            "observed_states": len(self.state_visits),
            "stored_state_snapshots": len(self.state_observations),
            "states_with_legal_action_records": len(self.state_legal_actions),
            "observed_transition_edges": len(self.transition_counts),
            "transition_count": len(self.transition_history),
            "action_effects": {key: value.snapshot() for key, value in self.action_effects.items()},
            "action_signature_effects": {key: value.snapshot() for key, value in self.action_signature_effects.items()},
            "recent_transitions": list(self.transition_history[-20:]),
        }
