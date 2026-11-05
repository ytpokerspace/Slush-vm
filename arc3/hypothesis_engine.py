"""Transparent hypothesis ledger for ARC-AGI-3 exploration.

Evidence labels are qualitative bookkeeping, not calibrated probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Hypothesis:
    hypothesis_id: str
    category: str
    statement: str
    source: str
    support_count: int = 0
    refute_count: int = 0
    evidence: list[str] = field(default_factory=list)
    explicitly_verified: bool = False

    @property
    def status(self) -> str:
        if self.explicitly_verified:
            return "explicitly_verified"
        if self.support_count and self.refute_count:
            return "mixed_evidence"
        if self.support_count:
            return "supported_but_unverified"
        return "unverified"

    def add_evidence(self, description: str, supports: bool) -> None:
        if supports:
            self.support_count += 1
        else:
            self.refute_count += 1
        self.evidence.append(description)
        del self.evidence[:-12]

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.hypothesis_id,
            "category": self.category,
            "statement": self.statement,
            "source": self.source,
            "support_count": self.support_count,
            "refute_count": self.refute_count,
            "status": self.status,
            "evidence": list(self.evidence),
        }


@dataclass
class HypothesisEngine:
    """Track explicit facts separately from visual and behavioral hypotheses."""
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    explicit_facts: list[dict[str, Any]] = field(default_factory=list)
    max_facts: int = 64

    def _get(
        self, hypothesis_id: str, category: str, statement: str, source: str
    ) -> Hypothesis:
        if hypothesis_id not in self.hypotheses:
            self.hypotheses[hypothesis_id] = Hypothesis(
                hypothesis_id, category, statement, source
            )
        return self.hypotheses[hypothesis_id]

    def observe(self, observation: Any, navigation: dict[str, Any] | None = None) -> None:
        if not isinstance(observation, dict):
            return
        state = str(observation.get("__arc3_state") or "").upper()
        if state == "WIN":
            h = self._get(
                "terminal-win", "completion",
                "The environment explicitly reported a win state.", "environment"
            )
            h.explicitly_verified = True
            self._fact("terminal_win", {"state": state})
        completed = observation.get("__arc3_levels_completed")
        if isinstance(completed, int) and not isinstance(completed, bool) and completed > 0:
            h = self._get(
                "level-progress", "progress",
                "The environment reported one or more completed levels.", "environment"
            )
            h.explicitly_verified = True
            self._fact("levels_completed", {"value": completed})
        if navigation:
            target = navigation.get("target_center")
            h = self._get(
                "visual-target-candidate", "goal_candidate",
                "The visual heuristic identified a possible target and route.",
                "visual_heuristic"
            )
            h.add_evidence(f"Candidate target center: {target!r}", True)

    def record_transition(self, event: dict[str, Any]) -> None:
        family = str(event.get("action_family", "unknown"))
        h = self._get(
            f"action-change:{family}", "action_effect",
            f"Action family {family!r} has been associated with visible state changes.",
            "observed_transition"
        )
        changed = bool(event.get("observation_changed"))
        h.add_evidence(
            "Observation changed after this action." if changed
            else "No visible observation change followed this action.",
            changed,
        )
        if event.get("explicit_progress_observed"):
            progress = self._get(
                f"action-progress:{family}", "progress_effect",
                f"Action family {family!r} preceded explicitly reported level progress.",
                "environment_feedback"
            )
            progress.add_evidence("Environment reported increased completed-level count.", True)
        if event.get("terminal_win_observed"):
            win = self._get(
                f"action-win:{family}", "completion_effect",
                f"Action family {family!r} immediately preceded an explicit win signal.",
                "environment_feedback"
            )
            win.add_evidence("Environment reported WIN after the action.", True)

    def _fact(self, kind: str, payload: dict[str, Any]) -> None:
        self.explicit_facts.append({"kind": kind, **payload})
        del self.explicit_facts[:-self.max_facts]

    def snapshot(self) -> dict[str, Any]:
        return {
            "hypotheses": [h.snapshot() for h in self.hypotheses.values()],
            "explicit_facts": list(self.explicit_facts),
            "warning": "Hypothesis support counts are evidence bookkeeping, not probabilities.",
        }
