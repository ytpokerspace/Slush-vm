"""Evidence-bounded state and action-effect model for ARC-AGI-3.

The model stores observed transitions. It does not pretend to simulate unseen game
states or infer causality beyond the controlled action/observation sequence.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=repr)


def state_signature(observation: Any) -> str:
    return hashlib.sha256(canonical_json(observation).encode("utf-8")).hexdigest()


def action_name(action: Any) -> str:
    if isinstance(action, dict):
        return str(action.get("name", action.get("button", action.get("action", "unknown"))))
    return str(action)


def action_signature(action: Any) -> str:
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
    exact_transitions: dict[str, str] = field(default_factory=dict)
    transition_history: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, observation: Any) -> dict[str, Any]:
        key = state_signature(observation)
        self.state_visits[key] += 1
        return {
            "state_id": key,
            "visit_count": self.state_visits[key],
            "features": observation_features(observation),
        }

    def record_transition(self, action: Any, before: Any, after: Any) -> dict[str, Any]:
        before_key = state_signature(before)
        after_key = state_signature(after)
        family = action_family(action)
        stats = self.action_effects.setdefault(family, ActionEffectStats())
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
        self.exact_transitions[canonical_json([before_key, action_signature(action)])] = after_key
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

    def predict_exact(self, observation: Any, action: Any) -> str | None:
        """Return a next-state signature only for an exactly observed state/action pair."""
        key = canonical_json([state_signature(observation), action_signature(action)])
        return self.exact_transitions.get(key)

    def snapshot(self) -> dict[str, Any]:
        return {
            "observed_states": len(self.state_visits),
            "transition_count": len(self.transition_history),
            "action_effects": {key: value.snapshot() for key, value in self.action_effects.items()},
            "recent_transitions": list(self.transition_history[-20:]),
        }
