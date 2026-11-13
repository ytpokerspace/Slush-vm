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
            family = world_model.action_stats(action)
            exact_history = world_model.action_signature_stats(action)
            family_attempts = int(family.get("attempts", 0))
            family_progress = int(family.get("explicit_progress", 0)) + int(family.get("terminal_wins", 0))
            exact_attempts = int(exact_history.get("attempts", 0))
            exact_progress = int(exact_history.get("explicit_progress", 0)) + int(exact_history.get("terminal_wins", 0))
            # Exact action history includes click coordinates and survives changing
            # screen states; family history generalizes across coordinates.
            if exact_attempts:
                attempts = exact_attempts
                progress = exact_progress
                changed = int(exact_history.get("changed", 0))
                wins = int(exact_history.get("terminal_wins", 0))
                evidence_scope = "exact_action_history"
            elif family_attempts:
                attempts = family_attempts
                progress = family_progress
                changed = int(family.get("changed", 0))
                wins = int(family.get("terminal_wins", 0))
                evidence_scope = "action_family"
            else:
                attempts = int(edge.get("attempts", 0))
                progress = int(edge.get("verified_progress_or_win", 0))
                changed = int(edge.get("changed", 0))
                wins = int(edge.get("terminal_wins", 0))
                evidence_scope = "exact_state_action"
            p_progress = (progress + self.alpha) / (attempts + self.alpha + self.beta)
            p_change = (changed + self.alpha) / (attempts + self.alpha + self.beta)
            # Reward trying new legal actions/coordinates. A changed screen alone
            # is weak evidence and cannot outweigh repeated lack of progress.
            information_bonus = (
                self.exploration_weight / math.sqrt(exact_attempts + 1)
                + 0.12 / math.sqrt(family_attempts + 1)
            )
            stagnation_penalty = (
                min(0.30, 0.075 * family_attempts)
                if family_attempts >= 2 and family_progress == 0 else 0.0
            )
            repeat_penalty = (
                min(0.36, 0.30 * exact_attempts)
                if exact_attempts >= 1 and exact_progress == 0 else 0.0
            )
            strategy_prior = max(0.0, float(strategy_priors.get(signature, 0.0)))
            mcts = mcts_by_signature.get(signature, {})
            mcts_value = float(mcts.get("mean_value", 0.5))
            mcts_visits = int(mcts.get("visits", 0))
            # Ranking utility is a transparent weighted heuristic. The separate
            # posterior fields remain interpretable and are not called win odds.
            utility = (
                0.65 * p_progress
                + 0.05 * p_change
                + 0.15 * min(1.0, mcts_value)
                + 0.15 * min(1.0, strategy_prior)
                + information_bonus
                - stagnation_penalty
                - repeat_penalty
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
                    "stagnation_penalty": round(stagnation_penalty, 6),
                    "repeat_penalty": round(repeat_penalty, 6),
                    "family_attempts": family_attempts,
                    "exact_action_attempts": exact_attempts,
                    "family_confirmed_progress": family_progress,
                    "exact_action_confirmed_progress": exact_progress,
                    "utility_score": round(utility, 6),
                },
            })
        output.sort(key=lambda row: (-row["factors"]["utility_score"], row["index"]))
        for rank, row in enumerate(output, 1):
            row["rank"] = rank
        return output
