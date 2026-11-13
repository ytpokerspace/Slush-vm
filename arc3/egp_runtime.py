"""Environment execution bridge for EGP-ARC3.

The agent reasons over normalized observations and legal action records. This
module is the narrow, explicit boundary that turns one selected EGP action into
one real environment step. It never invents actions or assumes game mechanics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EGPEnvironmentRuntime:
    """Execute selected actions through an ARC environment's public step API."""

    environment: Any
    actions_executed: int = 0
    last_trace: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _action_name(action: Any) -> str:
        return str(getattr(action, "name", action))

    def act(
        self,
        legal_actions: list[Any],
        selected_action: Any,
        selected_record: dict[str, Any],
        fallback_data: dict[str, Any] | None = None,
    ) -> Any:
        """Validate and execute exactly one action supplied by the environment.

        Complex-action payloads come from the selected candidate. A fallback is
        used only when the caller explicitly supplies one. The environment's
        returned frame is passed through unchanged for independent verification.
        """
        if selected_action not in legal_actions:
            raise ValueError("EGP refused an action not present in the current legal action space")

        expected_name = self._action_name(selected_action)
        record_name = str(selected_record.get("name", ""))
        if record_name != expected_name:
            raise ValueError(
                f"selected record/action mismatch: {record_name!r} != {expected_name!r}"
            )

        is_complex = callable(getattr(selected_action, "is_complex", None)) and selected_action.is_complex()
        action_data = selected_record.get("data") if is_complex else None
        if is_complex and not isinstance(action_data, dict):
            action_data = dict(fallback_data) if fallback_data is not None else None
        if is_complex and not isinstance(action_data, dict):
            raise ValueError("complex legal action requires a structured data payload")

        # This is the only environment side effect in the EGP bridge.
        next_observation = self.environment.step(selected_action, data=action_data)
        self.actions_executed += 1
        self.last_trace = {
            "glyph": "▶️",
            "operation": "act",
            "action": expected_name,
            "action_data": action_data,
            "action_index": self.actions_executed,
            "observation_returned": next_observation is not None,
            "verification_required": True,
        }
        return next_observation

    def snapshot(self) -> dict[str, Any]:
        return {
            "runtime": "EGPEnvironmentRuntime",
            "actions_executed": self.actions_executed,
            "last_trace": dict(self.last_trace),
            "environment_attached": self.environment is not None,
        }
