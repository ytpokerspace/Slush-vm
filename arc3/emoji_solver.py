"""
ARC-AGI-3 emoji-policy adapter for SHUSH/Slush-vm.

This is a deterministic baseline policy adapter, not a claim of solved ARC-AGI-3
tasks. It accepts normalized observations and legal actions, persists policy state
between CLI calls, and emits diagnostics. Only the Python standard library is used.
"""
from __future__ import annotations

import json
import math
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

EMOJI_PROGRAM = "📥➡️👁️➡️🧠➡️🧩➡️🎯➡️⚙️➡️📤 ♻️🔁🧠🔍🛑"
STATE_SCHEMA_VERSION = 1


def stable_key(value: Any) -> str:
    """Canonical JSON key for state/action comparison."""
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
    """Use the full observation for loop detection; summary is only diagnostic."""
    return stable_key(observation)


@dataclass
class Arc3EmojiSolver:
    """Deterministic action selector that only returns actions from the legal list."""
    max_repeated_state: int = 3
    seen_states: Counter[str] = field(default_factory=Counter)
    attempted_by_state: dict[str, set[str]] = field(default_factory=dict)
    turns: int = 0

    def to_state(self) -> dict[str, Any]:
        """Return JSON-serializable policy state for the next CLI invocation."""
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "turns": self.turns,
            "seen_states": dict(self.seen_states),
            "attempted_by_state": {
                key: sorted(actions) for key, actions in self.attempted_by_state.items()
            },
        }

    @classmethod
    def from_state(cls, state: Any, max_repeated_state: int = 3) -> "Arc3EmojiSolver":
        """Restore a saved state, rejecting incompatible or malformed snapshots."""
        solver = cls(max_repeated_state=max_repeated_state)
        if not isinstance(state, dict) or state.get("schema_version") != STATE_SCHEMA_VERSION:
            return solver
        turns = state.get("turns", 0)
        if isinstance(turns, int) and not isinstance(turns, bool) and turns >= 0:
            solver.turns = turns
        seen = state.get("seen_states", {})
        if isinstance(seen, dict):
            for key, count in seen.items():
                if isinstance(key, str) and isinstance(count, int) and not isinstance(count, bool) and count > 0:
                    solver.seen_states[key] = count
        attempted = state.get("attempted_by_state", {})
        if isinstance(attempted, dict):
            for key, actions in attempted.items():
                if isinstance(key, str) and isinstance(actions, list) and all(isinstance(a, str) for a in actions):
                    solver.attempted_by_state[key] = set(actions)
        return solver

    def restore_history(self, history: Iterable[dict[str, Any]]) -> None:
        """Reconstruct state from records containing both observation and action."""
        for record in history:
            if not isinstance(record, dict) or "observation" not in record or "action" not in record:
                continue
            key = state_key(record["observation"])
            self.seen_states[key] += 1
            self.attempted_by_state.setdefault(key, set()).add(stable_key(record["action"]))
            self.turns += 1

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
                "diagnostics": {
                    "turn": self.turns,
                    "state": grid_summary(observation),
                    "history_length": len(list(history)),
                },
            }

        key = state_key(observation)
        self.seen_states[key] += 1
        attempted = self.attempted_by_state.setdefault(key, set())
        historical = list(history)

        scored = []
        for index, action in enumerate(actions):
            score = None
            if isinstance(action, dict):
                raw = action.get("score", action.get("priority"))
                if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    try:
                        candidate_score = float(raw)
                        if math.isfinite(candidate_score):
                            score = candidate_score
                    except (OverflowError, ValueError):
                        score = None
            scored.append((score, index, action))

        # Rank scored actions first, then unscored legal actions, preserving input order
        # for ties. Never let one repeatedly-scored action starve other legal actions.
        start_index = self.turns % len(actions)
        candidates = sorted(
            scored,
            key=lambda item: (
                item[0] is None,
                -(item[0] if item[0] is not None else 0.0),
                (item[1] - start_index) % len(actions),
            ),
        )
        chosen = next((a for _, _, a in candidates if stable_key(a) not in attempted), None)
        if chosen is None:
            chosen = candidates[0][2]
        rationale = "highest provided score among untried legal actions; global round-robin tie-break prevents first-action starvation"

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
    history = request.get("history", [])
    if not isinstance(history, list):
        print(json.dumps({"error": "history must be a JSON array"}), file=sys.stdout)
        return 2

    saved_state = request.get("solver_state")
    solver = Arc3EmojiSolver.from_state(saved_state)
    if saved_state is None:
        solver.restore_history(history)
    result = solver.choose_action(request["observation"], actions, history)
    result["solver_state"] = solver.to_state()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
