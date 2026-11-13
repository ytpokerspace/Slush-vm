"""Conservative transition templates learned only from real observations."""
from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from arc3.world_model import action_family, canonical_json, state_signature

def _layers(observation: Any):
    if not isinstance(observation, dict):
        return None
    frame = observation.get("frame", observation.get("grid", observation.get("board")))
    if not isinstance(frame, list) or not frame:
        return None
    if not all(isinstance(item, list) for item in frame):
        return None
    # Normalize either a single 2-D grid or a stack of 2-D layers.
    layers = frame if frame[0] and isinstance(frame[0][0], list) else [frame]
    if not layers or any(not isinstance(layer, list) for layer in layers):
        return None
    if any(any(not isinstance(row, list) for row in layer) for layer in layers):
        return None
    return layers

@dataclass(frozen=True)
class CellChange:
    layer: int
    y: int
    x: int
    before: Any
    after: Any

@dataclass(frozen=True)
class GridRule:
    shape: tuple[tuple[int, int], ...]
    changes: tuple[CellChange, ...]

class TransitionLearner:
    """Exact-coordinate templates; never labels a prediction as an observation."""
    def __init__(self, max_rules_per_action: int = 32):
        self.max_rules_per_action = max_rules_per_action
        self.rules = defaultdict(dict)
        self.observed_pairs = 0

    def observe(self, action: Any, before: Any, after: Any) -> bool:
        old, new = _layers(before), _layers(after)
        if old is None or new is None or len(old) != len(new):
            return False
        if any(len(a) != len(b) or any(len(ar) != len(br) for ar, br in zip(a, b))
               for a, b in zip(old, new)):
            return False
        changes = tuple(CellChange(layer, y, x, old[layer][y][x], new[layer][y][x])
                        for layer in range(len(old))
                        for y in range(len(old[layer]))
                        for x in range(len(old[layer][y]))
                        if old[layer][y][x] != new[layer][y][x])
        if not changes:
            return False
        family = action_family(action)
        shape = tuple((len(layer), len(layer[0]) if layer else 0) for layer in old)
        rule = GridRule(shape, changes)
        key = canonical_json([(c.y, c.x, c.before, c.after) for c in changes])
        previous = self.rules[family].get(key)
        self.rules[family][key] = (rule, previous[1] + 1 if previous else 1)
        self.observed_pairs += 1
        if len(self.rules[family]) > self.max_rules_per_action:
            weakest = min(self.rules[family], key=lambda k: self.rules[family][k][1])
            del self.rules[family][weakest]
        return True

    def predict(self, action: Any, observation: Any, limit: int = 4) -> list[dict[str, Any]]:
        layers = _layers(observation)
        if layers is None:
            return []
        shape = tuple((len(layer), len(layer[0]) if layer else 0) for layer in layers)
        matches = []
        for rule, count in self.rules.get(action_family(action), {}).values():
            if rule.shape == shape and all(
                layers[c.layer][c.y][c.x] == c.before for c in rule.changes
            ):
                matches.append((count, rule))
        matches.sort(key=lambda item: (-item[0], len(item[1].changes)))
        results = []
        for count, rule in matches[:max(0, limit)]:
            predicted = deepcopy(observation)
            target = _layers(predicted)
            for change in rule.changes:
                target[change.layer][change.y][change.x] = change.after
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
                          "grid_shape": [list(shape) for shape in rule.shape]}
                         for rule, count in sorted(items.values(), key=lambda x: -x[1])]
                for family, items in self.rules.items()
            },
            "semantics": "exact-coordinate templates; predictions require external verification",
        }
