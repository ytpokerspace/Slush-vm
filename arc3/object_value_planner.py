"""Object-local decision states and global relative-value arbitration.

This is a heuristic planning scaffold, not a learned policy. Inputs should be
grounded in observations or explicitly labelled estimates by the caller.
"""
from __future__ import annotations

from typing import Any


DEFAULT_WEIGHTS = {
    "goal": 1.0,
    "success": 1.0,
    "information": 0.5,
    "risk": 1.0,
    "cost": 0.25,
}


def score_objective(
    objective: dict[str, Any],
    *,
    feasibility_threshold: float = 0.35,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Score one candidate and decide whether to pursue, prepare, or defer it.

    Expected numeric fields: goal_value, success_probability, information_value,
    risk, action_cost. Values are clamped to [0, 1]; missing values default to 0.
    """
    if not 0.0 <= feasibility_threshold <= 1.0:
        raise ValueError("feasibility_threshold must be between 0 and 1")
    w = {**DEFAULT_WEIGHTS, **(weights or {})}

    def unit(name: str) -> float:
        value = float(objective.get(name, 0.0))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0 and 1")
        return value

    goal = unit("goal_value")
    success = unit("success_probability")
    information = unit("information_value")
    risk = unit("risk")
    cost = unit("action_cost")
    utility = (
        w["goal"] * goal * success
        + w["information"] * information
        - w["risk"] * risk
        - w["cost"] * cost
    )
    if success >= feasibility_threshold and utility > 0:
        decision = "pursue"
    elif information > 0 and risk <= 0.35 and cost <= 0.5:
        decision = "prepare"
    else:
        decision = "defer"
    return {
        "objective_id": str(objective.get("objective_id", "unnamed")),
        "utility": round(utility, 6),
        "success_probability": success,
        "decision": decision,
        "feasibility_threshold": feasibility_threshold,
        "probability_is_calibrated": bool(objective.get("probability_is_calibrated", False)),
    }


def arbitrate_objectives(
    objectives: list[dict[str, Any]],
    *,
    feasibility_threshold: float = 0.35,
    weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Rank objective candidates while preserving deferred goals for reevaluation."""
    scored = [
        score_objective(item, feasibility_threshold=feasibility_threshold, weights=weights)
        for item in objectives
    ]
    scored.sort(key=lambda item: (item["decision"] == "pursue", item["utility"]), reverse=True)
    active = next((item for item in scored if item["decision"] == "pursue"), None)
    if active is None:
        active = next((item for item in scored if item["decision"] == "prepare"), None)
    return {
        "active_objective": active["objective_id"] if active else None,
        "decision": active["decision"] if active else "idle",
        "ranked_objectives": scored,
        "deferred_objectives": [
            item["objective_id"] for item in scored if item["decision"] == "defer"
        ],
        "probabilities_are_calibrated": all(
            item["probability_is_calibrated"] for item in scored
        ) if scored else False,
        "warning": "Heuristic arbitration only; calibrate estimates against observed outcomes.",
    }
