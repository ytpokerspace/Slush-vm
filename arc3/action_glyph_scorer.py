"""Map legal ARC actions to EGP glyph commands and evidence-weighted scores.

Glyphs are an executable-facing representation of environment-provided actions,
not a source of new actions. Probability fields are smoothed empirical estimates;
they are not calibrated win probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from arc3.world_model import action_signature, state_signature


ACTION_GLYPHS = {
    "up": "⬆️", "north": "⬆️", "move_up": "⬆️",
    "down": "⬇️", "south": "⬇️", "move_down": "⬇️",
    "left": "⬅️", "west": "⬅️", "move_left": "⬅️",
    "right": "➡️", "east": "➡️", "move_right": "➡️",
    "click": "🖱️", "tap": "🖱️", "touch": "🖱️",
    "wait": "⏳", "noop": "⏳", "no_op": "⏳",
    "undo": "↩️", "back": "↩️",
}
GENERIC_ACTION_GLYPH = "🎮"


def _name(action: Any) -> str:
    if isinstance(action, dict):
        return str(action.get("name", action.get("button", action.get("action", "unknown"))))
    return str(getattr(action, "name", action))


def _intent(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    for token, glyph in ACTION_GLYPHS.items():
        if normalized == token or normalized.endswith("_" + token) or normalized.startswith(token + "_"):
            return glyph
    return GENERIC_ACTION_GLYPH


def encode_action(action_record: dict[str, Any]) -> dict[str, Any]:
    """Encode one already-legal action record without changing its payload."""
    name = _name(action_record)
    payload = action_record.get("data") if isinstance(action_record, dict) else None
    glyph = _intent(name)
    if isinstance(payload, dict) and {"x", "y"}.issubset(payload):
        glyph = "🖱️"
    return {
        "glyph": glyph,
        "operation": "environment_action",
        "action_name": name,
        "payload": dict(payload) if isinstance(payload, dict) else None,
        "legal_source": "current_environment_action_space",
        "action_signature": action_signature(action_record),
    }


@dataclass
class ActionProbabilityScorer:
    """Score legal actions from exact-edge outcomes, family history and priors."""

    alpha: float = 1.0
    beta: float = 1.0
    exploration_weight: float = 0.08

    def score(
        self,
        observation: Any,
        action_records: list[dict[str, Any]],
        world_model: Any,
        strategy_priors: dict[str, float] | None = None,
        mcts_candidates: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        strategy_priors = strategy_priors or {}
        mcts_by_signature = {
            action_signature(row.get("action")): row
            for row in (mcts_candidates or [])
            if isinstance(row, dict) and row.get("action") is not None
        }
        state_id = state_signature(observation)
        output = []
        for index, action in enumerate(action_records):
            signature = action_signature(action)
            edge = world_model.edge_stats_by_ids(state_id, action)
            attempts = int(edge.get("attempts", 0))
            progress = int(edge.get("verified_progress_or_win", 0))
            changed = int(edge.get("changed", 0))
            wins = int(edge.get("terminal_wins", 0))
            evidence_scope = "exact_state_action"
            if attempts == 0:
                # The exact state may be new every turn. Use action-family history
                # as weaker prior evidence, while labeling that scope explicitly.
                family = world_model.action_stats(action)
                attempts = int(family.get("attempts", 0))
                progress = min(attempts, int(family.get("explicit_progress", 0)) + int(family.get("terminal_wins", 0)))
                changed = int(family.get("changed", 0))
                wins = int(family.get("terminal_wins", 0))
                evidence_scope = "action_family"
            p_progress = (progress + self.alpha) / (attempts + self.alpha + self.beta)
            p_change = (changed + self.alpha) / (attempts + self.alpha + self.beta)
            # Exploration is explicitly a value bonus, not a success probability.
            information_bonus = self.exploration_weight / math.sqrt(attempts + 1)
            strategy_prior = max(0.0, float(strategy_priors.get(signature, 0.0)))
            mcts = mcts_by_signature.get(signature, {})
            mcts_value = float(mcts.get("mean_value", 0.5))
            mcts_visits = int(mcts.get("visits", 0))
            # Ranking utility is a transparent weighted heuristic. The separate
            # posterior fields remain interpretable and are not called win odds.
            utility = (
                0.60 * p_progress
                + 0.15 * p_change
                + 0.15 * min(1.0, mcts_value)
                + 0.10 * min(1.0, strategy_prior)
                + information_bonus
            )
            encoded = encode_action(action)
            output.append({
                "index": index,
                **encoded,
                "probability": {
                    "verified_progress_or_win": round(p_progress, 6),
                    "observation_change": round(p_change, 6),
                    "evidence_attempts": attempts,
                    "evidence_scope": evidence_scope,
                    "verified_progress_or_win_count": progress,
                    "terminal_win_count": wins,
                    "calibration": "beta_binomial_smoothed_empirical",
                    "status": "evidence_backed" if attempts else "prior_only",
                },
                "factors": {
                    "mcts_mean_value": round(mcts_value, 6),
                    "mcts_visits": mcts_visits,
                    "strategy_prior": round(strategy_prior, 6),
                    "information_bonus": round(information_bonus, 6),
                    "utility_score": round(utility, 6),
                },
            })
        output.sort(key=lambda row: (-row["factors"]["utility_score"], row["index"]))
        for rank, row in enumerate(output, 1):
            row["rank"] = rank
        return output
