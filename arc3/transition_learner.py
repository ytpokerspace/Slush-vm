"""Conservative transition templates learned only from real observations."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from arc3.world_model import action_family, canonical_json, state_signature

def _grid(observation: Any):
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame or not all(isinstance(r, list) for r in frame):
        return None
    if frame[0] and isinstance(frame[0][0], list):
        return None
    return frame

@dataclass(frozen=True)
class CellChange:
    y: int
    x: int
    before: Any
    after: Any

@dataclass(frozen=True)
class GridRule:
    height: int
    width: int
    changes: tuple[CellChange, ...]

class TransitionLearner:
    """Exact-coordinate templates; never labels a prediction as an observation."""
    def __init__(self, max_rules_per_action: int = 32):
        self.max_rules_per_action = max_rules_per_action
        self.rules = defaultdict(dict)
        self.observed_pairs = 0

    def observe(self, action: Any, before: Any, after: Any) -> bool:
        old, new = _grid(before), _grid(after)
        if old is None or new is None or len(old) != len(new):
            return False
        if any(len(a) != len(b) for a, b in zip(old, new)):
            return False
        changes = tuple(CellChange(y, x, old[y][x], new[y][x])
                        for y in range(len(old)) for x in range(len(old[y]))
                        if old[y][x] != new[y][x])
        if not changes:
            return False
        family = action_family(action)
        rule = GridRule(len(old), len(old[0]) if old else 0, changes)
        key = canonical_json([(c.y, c.x, c.before, c.after) for c in changes])
        previous = self.rules[family].get(key)
        self.rules[family][key] = (rule, previous[1] + 1 if previous else 1)
        self.observed_pairs += 1
        if len(self.rules[family]) > self.max_rules_per_action:
            weakest = min(self.rules[family], key=lambda k: self.rules[family][k][1])
            del self.rules[family][weakest]
        return True

    def predict(self, action: Any, observation: Any, limit: int = 4) -> list[dict[str, Any]]:
        grid = _grid(observation)
        if grid is None:
            return []
        h, w = len(grid), len(grid[0]) if grid else 0
        matches = []
        for rule, count in self.rules.get(action_family(action), {}).values():
            if rule.height == h and rule.width == w and all(
                grid[c.y][c.x] == c.before for c in rule.changes
            ):
                matches.append((count, rule))
        matches.sort(key=lambda item: (-item[0], len(item[1].changes)))
        results = []
        for count, rule in matches[:max(0, limit)]:
            predicted = deepcopy(observation)
            target = _grid(predicted)
            for change in rule.changes:
                target[change.y][change.x] = change.after
            results.append({
                "observation": predicted,
                "evidence": "predicted_from_observed_template",
                "support_count": count,
                "confidence_proxy": count / (count + 1.0),
                "source_state": state_signature(observation),
                "rule_change_count": len(rule.changes),
            })
        return results

    def snapshot(self):
        return {
            "observed_pairs": self.observed_pairs,
            "action_families": {
                family: [{"support_count": count, "changed_cells": len(rule.changes),
                          "grid_shape": [rule.height, rule.width]}
                         for rule, count in sorted(items.values(), key=lambda x: -x[1])]
                for family, items in self.rules.items()
            },
            "semantics": "exact-coordinate templates; predictions require external verification",
        }
