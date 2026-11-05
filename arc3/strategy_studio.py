"""ARC-AGI-3 adaptation of the Quantum Brainstorming Studio.

This is a classical, deterministic strategy-synthesis procedure:
two candidate-generation rounds followed by four explicit refinement passes.
It does not perform quantum computation or claim calibrated strategy probabilities.
"""
from __future__ import annotations

import math
from typing import Any

from arc3.world_model import action_family, action_signature


def _finite_score(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        value = float(value)
        if math.isfinite(value):
            return value
    return 0.0


def brainstorm_action_priors(
    legal_actions: list[Any],
    navigation: dict[str, Any] | None,
    world_model: Any,
    attempted_signatures: set[str] | None = None,
) -> dict[str, Any]:
    """Generate, hybridize, critique, and rank strategies for current legal actions."""
    attempted = attempted_signatures or set()
    rows: list[dict[str, Any]] = []
    preferred_name = navigation.get("action") if isinstance(navigation, dict) else None

    # Round 1: independent candidate strategies.
    for index, action in enumerate(legal_actions):
        signature = action_signature(action)
        family = action_family(action)
        stats = world_model.action_stats(action)
        attempts = int(stats.get("attempts", 0))
        unchanged = int(stats.get("unchanged", 0))
        progress = int(stats.get("explicit_progress", 0))
        wins = int(stats.get("terminal_wins", 0))
        base = _finite_score(action.get("score", 0.0) if isinstance(action, dict) else 0.0)
        route_match = bool(preferred_name and family == preferred_name)
        untried_here = signature not in attempted

        # These are ranking features, not probabilities.
        score = 0.15 + min(0.25, max(0.0, base) / 400.0)
        evidence = []
        if route_match:
            score += 0.35
            evidence.append("matches current visual route hypothesis")
        if progress:
            score += min(0.30, 0.12 * progress)
            evidence.append("action family has observed explicit progress")
        if wins:
            score += min(0.50, 0.25 * wins)
            evidence.append("action family has observed terminal wins")
        if untried_here:
            score += 0.18
            evidence.append("not yet tried in this exact state")
        if attempts >= 2 and unchanged / attempts >= 0.75:
            score -= 0.25
            evidence.append("action family frequently produced unchanged observations")
        rows.append({
            "index": index, "action": action, "signature": signature,
            "family": family, "score": score, "evidence": evidence,
            "generation": "independent",
        })

    # Round 2: hybridize complementary ideas without inventing new legal actions.
    for row in rows:
        hybrid_score = row["score"]
        if row["family"] == preferred_name and row["signature"] not in attempted:
            hybrid_score += 0.08
            row["evidence"].append("hybrid: visual route + fresh experiment")
        if int(world_model.action_stats(row["action"]).get("explicit_progress", 0)) > 0:
            hybrid_score += 0.06
            row["evidence"].append("hybrid: previously useful action + current-state check")
        row["score"] = hybrid_score
        row["generation"] = "hybrid"

    # Four refinement passes: feasibility, evidence, contradiction, and cost.
    for row in rows:
        # Pass 1 — feasibility: only caller-supplied legal actions survive.
        row["feasibility"] = 1.0
        # Pass 2 — evidence: explicit progress/win evidence is stronger than visual guesses.
        stats = world_model.action_stats(row["action"])
        row["evidence_strength"] = min(
            1.0, 0.20 * int(stats.get("explicit_progress", 0))
            + 0.40 * int(stats.get("terminal_wins", 0))
        )
        # Pass 3 — contradiction: repeated no-change outcomes reduce priority.
        attempts = int(stats.get("attempts", 0))
        noop_rate = (int(stats.get("unchanged", 0)) / attempts) if attempts else 0.0
        row["contradiction_penalty"] = 0.30 * noop_rate if attempts >= 2 else 0.0
        # Pass 4 — resource cost: discourage repeating an already-tested action here.
        row["repeat_cost"] = 0.75 if row["signature"] in attempted else 0.0
        row["score"] += (
            0.10 * row["evidence_strength"]
            - row["contradiction_penalty"]
            - row["repeat_cost"]
        )

    # Convert ranking scores into normalized search priors. These are not success
    # probabilities; MCTS uses them only to guide exploration.
    if not rows:
        return {
            "candidate_count": 0, "generation_rounds": 2,
            "refinement_passes": 4, "candidates": [], "priors": {},
        }
    maximum = max(row["score"] for row in rows)
    weights = [math.exp(max(-20.0, min(20.0, row["score"] - maximum))) for row in rows]
    total = sum(weights)
    priors = {row["signature"]: weight / total for row, weight in zip(rows, weights)}
    rows.sort(key=lambda row: (-row["score"], row["index"]))
    public_rows = [
        {key: value for key, value in row.items() if key not in {"action"}}
        | {"action": row["action"]}
        for row in rows[:8]
    ]
    return {
        "candidate_count": len(rows),
        "generation_rounds": 2,
        "refinement_passes": 4,
        "candidates": public_rows,
        "priors": priors,
        "prior_semantics": "normalized strategy preference, not probability of winning",
    }
