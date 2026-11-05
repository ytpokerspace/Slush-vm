"""Task-memory partitioning and concise decision traces for search agents.

This module intentionally emits a compact rationale/decision record, not private
chain-of-thought. It ranks memory items by task relevance, expected utility,
recency, and cost, then allocates a bounded context budget across task partitions.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
from typing import Iterable


_WORDS = re.compile(r"[a-z0-9_]+")


def terms(text: str) -> set[str]:
    return {w for w in _WORDS.findall(text.lower()) if len(w) > 1}


@dataclass(frozen=True)
class MemoryItem:
    memory_id: str
    text: str
    task_tags: tuple[str, ...] = ()
    utility: float = 0.0
    recency: float = 0.0
    token_cost: int = 1
    points_value: float = 0.0


@dataclass(frozen=True)
class RankedMemory:
    memory_id: str
    partition: str
    relevance: float
    utility_score: float
    token_cost: int
    selected: bool
    reason_code: str


@dataclass(frozen=True)
class MemoryPlan:
    selected_ids: tuple[str, ...]
    primary_ids: tuple[str, ...]
    side_task_ids: tuple[str, ...]
    archive_ids: tuple[str, ...]
    estimated_tokens: int
    trace: tuple[dict[str, object], ...]


def _similarity(query_terms: set[str], item: MemoryItem) -> float:
    body = terms(item.text)
    tags = set().union(*(terms(tag) for tag in item.task_tags)) if item.task_tags else set()
    union = query_terms | body | tags
    if not union:
        return 0.0
    return len(query_terms & (body | tags)) / len(union)


def partition_memory(
    task: str,
    memories: Iterable[MemoryItem],
    token_budget: int = 1200,
    side_task_share: float = 0.20,
    min_relevance: float = 0.04,
) -> MemoryPlan:
    """Choose a bounded context set, reserving a capped slice for useful side tasks."""
    if token_budget < 1:
        raise ValueError("token_budget must be >= 1")
    if not 0.0 <= side_task_share <= 0.5:
        raise ValueError("side_task_share must be between 0 and 0.5")
    q = terms(task)
    ranked = []
    for item in memories:
        if item.token_cost < 1:
            raise ValueError(f"memory {item.memory_id!r} has invalid token_cost")
        relevance = _similarity(q, item)
        # Reward relevant, useful and recent memories, but penalize expensive items.
        score = (0.68 * relevance + 0.18 * max(0.0, item.utility)
                 + 0.08 * max(0.0, item.recency)
                 + 0.06 * max(0.0, item.points_value)) / (item.token_cost ** 0.5)
        if relevance >= 0.35:
            partition = "primary"
        elif relevance >= min_relevance:
            partition = "side_task"
        else:
            partition = "archive"
        ranked.append((score, relevance, item, partition))
    ranked.sort(key=lambda row: (row[3] == "primary", row[0]), reverse=True)

    side_budget = int(token_budget * side_task_share)
    primary_budget = token_budget - side_budget
    selected: list[tuple[float, float, MemoryItem, str]] = []
    used_primary = used_side = 0
    for row in ranked:
        score, relevance, item, partition = row
        if partition == "archive":
            continue
        if partition == "primary":
            if used_primary + item.token_cost <= primary_budget:
                selected.append(row)
                used_primary += item.token_cost
        elif used_side + item.token_cost <= side_budget:
            selected.append(row)
            used_side += item.token_cost

    chosen = {row[2].memory_id for row in selected}
    trace = []
    for score, relevance, item, partition in ranked:
        keep = item.memory_id in chosen
        reason = ("selected_primary" if keep and partition == "primary" else
                  "selected_side_task" if keep else
                  "budget_or_relevance_pruned" if partition != "archive" else
                  "archived_low_relevance")
        trace.append(asdict(RankedMemory(
            item.memory_id, partition, round(relevance, 4), round(score, 4),
            item.token_cost, keep, reason
        )))
    primary = tuple(row[2].memory_id for row in selected if row[3] == "primary")
    side = tuple(row[2].memory_id for row in selected if row[3] == "side_task")
    archive = tuple(row[2].memory_id for row in ranked if row[2].memory_id not in chosen)
    return MemoryPlan(
        tuple(row[2].memory_id for row in selected), primary, side, archive,
        used_primary + used_side, tuple(trace)
    )


def trace_decision(
    task: str, chosen_action: str, evidence: list[str],
    alternatives_rejected: list[str], memory_ids: list[str], confidence: float,
) -> dict[str, object]:
    """Return an auditable short decision summary, not hidden internal reasoning."""
    return {
        "task": task,
        "chosen_action": chosen_action,
        "evidence": evidence[:5],
        "alternatives_rejected": alternatives_rejected[:5],
        "memory_ids_used": memory_ids[:20],
        "confidence": round(max(0.0, min(1.0, confidence)), 3),
        "trace_type": "concise_decision_record",
    }
