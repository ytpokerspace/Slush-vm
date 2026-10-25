"""
ARC-AGI-3 emoji-policy adapter for SHUSH/Slush-vm.

This is a deterministic baseline policy adapter, not a claim of solved ARC-AGI-3
tasks. It accepts a normalized observation and legal actions from an environment
adapter, tracks repeated states, and chooses a legal action reproducibly.
Only the Python standard library is required.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

# Emoji-only program surface: each line is a pipeline stage.
EMOJI_PROGRAM = "📥➡️👁️➡️🧠➡️🧩➡️🎯➡️⚙️➡️📤 ♻️🔁🧠🔍🛑"

def stable_key(value: Any) -> str:
    """Canonical JSON key for action/state comparison."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def grid_summary(observation: Any) -> dict[str, Any]:
    """Extract conservative, task-agnostic features from common grid observations."""
    if not isinstance(observation, dict):
        return {"kind": type(observation).__name__}
    grid = observation.get("grid", observation.get("board"))
    if not isinstance(grid, list):
        return {"kind": "structured", "keys": sorted(str(k) for k in observation.keys())}
    rows = [row for row in grid if isinstance(row, list)]
    values = [cell for row in rows for cell in row]
    counts = Counter(stable_key(v) for v in values)
    return {
        "kind": "grid",
        "height": len(rows),
        "widths": [len(row) for row in rows],
        "cell_count": len(values),
        "distinct_values": len(counts),
        "value_counts": sorted(counts.values(), reverse=True),
    }

def state_key(observation: Any) -> str:
    """Use the full observation for loop detection; summary is only for diagnostics."""
    return stable_key(observation)

@dataclass
class Arc3EmojiSolver:
    """Small, deterministic action selector that never invents an illegal action."""
    max_repeated_state: int = 3
    seen_states: Counter[str] = field(default_factory=Counter)
    attempted_by_state: dict[str, set[str]] = field(default_factory=dict)
    turns: int = 0

    def choose_action(
        self,
        observation: Any,
        legal_actions: Iterable[Any],
        history: Iterable[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        actions = list(legal_actions)
        if not actions:
            return {
                "action": None,
                "status": "no_legal_actions",
                "program": EMOJI_PROGRAM,
                "diagnostics": {"turn": self.turns, "state": grid_summary(observation)},
            }

        key = state_key(observation)
        self.seen_states[key] += 1
        attempted = self.attempted_by_state.setdefault(key, set())
        historical = list(history)

        # If the environment exposes scores, honor them, but only among legal actions.
        scored = []
        for index, action in enumerate(actions):
            score = None
            if isinstance(action, dict):
                raw = action.get("score", action.get("priority"))
                if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    score = float(raw)
            scored.append((score, index, action))

        scored_with_values = [item for item in scored if item[0] is not None]
        if scored_with_values:
            candidates = sorted(scored_with_values, key=lambda item: (-item[0], item[1]))
            chosen = next((a for _, _, a in candidates if stable_key(a) not in attempted), None)
            if chosen is None:
                chosen = candidates[0][2]
            rationale = "highest provided score among legal actions"
        else:
            chosen = next((a for a in actions if stable_key(a) not in attempted), None)
            if chosen is None:
                # Deterministic fallback: cycle through the legal action list.
                chosen = actions[self.turns % len(actions)]
            rationale = "first untried legal action for this state; deterministic fallback on exhaustion"

        attempted.add(stable_key(chosen))
        self.turns += 1
        repeated = self.seen_states[key] >= self.max_repeated_state
        return {
            "action": chosen,
            "status": "possible_loop" if repeated else "ok",
            "program": EMOJI_PROGRAM,
            "diagnostics": {
                "turn": self.turns,
                "state": grid_summary(observation),
                "state_revisits": self.seen_states[key] - 1,
                "legal_action_count": len(actions),
                "history_length": len(historical),
                "rationale": rationale,
                "warning": "Repeated observation detected; consider a different policy or reset." if repeated else None,
            },
        }

def main() -> int:
    """Read one JSON request from stdin and emit one JSON response."""
    try:
        request = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(json.dumps({"error": f"invalid JSON input: {exc.msg}"}), file=sys.stdout)
        return 2
    if not isinstance(request, dict):
        print(json.dumps({"error": "request must be a JSON object"}), file=sys.stdout)
        return 2
    if "observation" not in request:
        print(json.dumps({"error": "missing required field: observation"}), file=sys.stdout)
        return 2
    actions = request.get("legal_actions", [])
    if not isinstance(actions, list):
        print(json.dumps({"error": "legal_actions must be a JSON array"}), file=sys.stdout)
        return 2
    solver = Arc3EmojiSolver()
    print(json.dumps(solver.choose_action(
        request["observation"], actions, request.get("history", [])
    ), ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
