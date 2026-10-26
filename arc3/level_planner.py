"""Partitioned memory for level progress and action planning.

This is a small, serializable bookkeeping layer. It records observed facts separately
from hypotheses/plans and never claims a level is complete without an explicit signal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LevelPlanningMemory:
    """Keep progress, scene cues, hypotheses, plan, and outcome history separate."""

    partitions: dict[str, Any] = field(default_factory=lambda: {
        "level_progress": {
            "levels_completed": 0,
            "win_levels": None,
            "level_index": 0,
            "completion_confirmed": False,
        },
        "scene_state": {},
        "goal_hypotheses": [],
        "active_plan": [],
        "action_outcomes": [],
        "uncertainties": [],
    })

    def update_observation(
        self,
        observation: Any,
        navigation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update scene and plan partitions from one observation and optional route cue."""
        if not isinstance(observation, dict):
            self.partitions["uncertainties"] = ["Observation is not a structured mapping."]
            return self.snapshot()

        progress = self.partitions["level_progress"]
        completed = observation.get("__arc3_levels_completed")
        available = observation.get("__arc3_win_levels")
        state = observation.get("__arc3_state")

        if isinstance(completed, int) and not isinstance(completed, bool) and completed >= 0:
            old_completed = progress["levels_completed"]
            progress["levels_completed"] = max(old_completed, completed)
            progress["level_index"] = max(progress["level_index"], completed)
            progress["completion_confirmed"] = completed > old_completed or state == "WIN"
        if isinstance(available, int) and not isinstance(available, bool) and available >= 0:
            progress["win_levels"] = available
        if state == "WIN":
            progress["completion_confirmed"] = True

        frame = observation.get("frame")
        grid = observation.get("grid", observation.get("board"))
        source = frame if frame is not None else grid
        if isinstance(source, list):
            self.partitions["scene_state"] = {
                "frame_shape": self._shape(source),
                "state": state,
                "levels_completed": progress["levels_completed"],
            }

        if navigation:
            self.partitions["goal_hypotheses"] = [{
                "target_center": navigation.get("target_center"),
                "confidence": "heuristic",
                "evidence": ["shared-color cue", "candidate target above player", "path found"],
            }]
            self.partitions["active_plan"] = [{
                "action": navigation.get("action"),
                "target_center": navigation.get("target_center"),
                "step_size": navigation.get("step_size"),
                "status": "proposed",
            }]
            self.partitions["uncertainties"] = []
        else:
            self.partitions["goal_hypotheses"] = []
            self.partitions["active_plan"] = []
            self.partitions["uncertainties"] = [
                "No reliable target/path inferred; use exploration and observe the outcome."
            ]
        return self.snapshot()

    def record_action(
        self,
        action: Any,
        before: Any,
        after: Any,
        max_history: int = 64,
    ) -> dict[str, Any]:
        """Record whether an action changed the observation; do not infer causality."""
        changed = before != after
        outcomes = self.partitions["action_outcomes"]
        outcomes.append({
            "action": action,
            "observation_changed": changed,
            "interpretation": "state changed after action" if changed else "no visible state change",
        })
        del outcomes[:-max_history]
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        """Return a detached JSON-compatible snapshot for logging/checkpointing."""
        return {
            key: value.copy() if isinstance(value, dict) else list(value)
            for key, value in self.partitions.items()
        }

    @staticmethod
    def _shape(value: Any) -> list[Any]:
        """Return bounded structural dimensions without copying pixel data."""
        if not isinstance(value, list):
            return []
        if value and isinstance(value[0], list):
            if value[0] and isinstance(value[0][0], list):
                return [len(value), len(value[0]), len(value[0][0])]
            return [len(value), len(value[0])]
        return [len(value)]
