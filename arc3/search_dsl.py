"""Pruned MCTS + beam-search DSL for deterministic, bounded planning.

This module is environment-agnostic: callers provide a transition model and a
state evaluator. It is deliberately not wired into the live ARC runner until a
validated predictive model exists; planning against an imagined model would be
misleading. All limits are explicit and deterministic except MCTS tie-breaking,
which uses a seeded RNG.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
import shlex
from typing import Any, Callable, Hashable, Iterable

State = Any
Action = Any
Transition = Callable[[State, Action], State]
Actions = Callable[[State], Iterable[Action]]
Evaluate = Callable[[State], float]
Terminal = Callable[[State], bool]
Key = Callable[[State], Hashable]


@dataclass(frozen=True)
class SearchConfig:
    iterations: int = 256
    depth: int = 12
    beam_width: int = 8
    branching_limit: int = 12
    max_nodes: int = 2048
    max_children: int = 32
    exploration: float = 1.414
    discount: float = 0.97
    novelty_weight: float = 0.08
    prune_delta: float = 0.35
    seed: int = 7
    top_k: int = 3

    def __post_init__(self) -> None:
        for name in ("iterations", "depth", "beam_width", "branching_limit",
                     "max_nodes", "max_children", "top_k"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        if self.exploration < 0 or not 0 < self.discount <= 1:
            raise ValueError("exploration must be >= 0 and discount in (0, 1]")
        if self.prune_delta < 0:
            raise ValueError("prune_delta must be >= 0")


@dataclass
class Node:
    state: State
    parent: "Node | None" = None
    action: Action | None = None
    visits: int = 0
    value_sum: float = 0.0
    children: list["Node"] | None = None
    untried: list[Action] | None = None

    @property
    def value(self) -> float:
        return self.value_sum / self.visits if self.visits else float("-inf")


@dataclass(frozen=True)
class SearchResult:
    action: Action | None
    score: float
    plan: tuple[Action, ...]
    nodes_created: int
    nodes_pruned: int
    iterations: int
    reason: str
    candidate_summary: tuple[tuple[Action, float, int], ...] = ()


def compile_dsl(source: str) -> SearchConfig:
    """Compile a tiny line-oriented DSL. Example: MCTS 256; BEAM 8; PRUNE DELTA 0.3."""
    values: dict[str, Any] = {}
    aliases = {
        "MCTS": ("iterations", int), "DEPTH": ("depth", int),
        "BEAM": ("beam_width", int), "BRANCH": ("branching_limit", int),
        "NODES": ("max_nodes", int), "CHILDREN": ("max_children", int),
        "UCT": ("exploration", float), "DISCOUNT": ("discount", float),
        "NOVELTY": ("novelty_weight", float), "SEED": ("seed", int),
        "TOPK": ("top_k", int),
    }
    for line_no, raw in enumerate(source.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = shlex.split(line)
        head = parts[0].upper()
        if head == "PRUNE" and len(parts) == 3 and parts[1].upper() == "DELTA":
            values["prune_delta"] = float(parts[2])
        elif head in aliases and len(parts) == 2:
            field, cast = aliases[head]
            values[field] = cast(parts[1])
        else:
            raise ValueError(f"DSL line {line_no}: invalid directive {line!r}")
    return SearchConfig(**values)


def beam_rank(
    initial: State, actions: Actions, transition: Transition, evaluate: Evaluate,
    terminal: Terminal, key: Key, config: SearchConfig,
) -> tuple[list[tuple[float, State, tuple[Action, ...]]], int, int]:
    """Bounded beam search with duplicate-state and score-delta pruning."""
    beam = [(evaluate(initial), initial, ())]
    seen = {key(initial)}
    created, pruned = 1, 0
    best = list(beam)
    for _ in range(config.depth):
        candidates: list[tuple[float, State, tuple[Action, ...]]] = []
        for _, state, plan in beam:
            if terminal(state):
                continue
            ranked_actions = list(actions(state))[:config.branching_limit]
            for action in ranked_actions:
                if created >= config.max_nodes:
                    pruned += 1
                    break
                nxt = transition(state, action)
                created += 1
                state_key = key(nxt)
                if state_key in seen:
                    pruned += 1
                    continue
                seen.add(state_key)
                score = evaluate(nxt) + config.novelty_weight / math.sqrt(1 + len(seen))
                candidates.append((score, nxt, plan + (action,)))
        if not candidates:
            break
        candidates.sort(key=lambda item: item[0], reverse=True)
        ceiling = candidates[0][0] - config.prune_delta
        kept = [item for item in candidates if item[0] >= ceiling][:config.beam_width]
        pruned += len(candidates) - len(kept)
        if kept and (not best or kept[0][0] > best[0][0]):
            best = kept
        beam = kept
    return best, created, pruned


def _uct(node: Node, parent_visits: int, exploration: float) -> float:
    if node.visits == 0:
        return float("inf")
    return node.value + exploration * math.sqrt(math.log(max(1, parent_visits)) / node.visits)


def search(
    initial: State, actions: Actions, transition: Transition, evaluate: Evaluate,
    terminal: Terminal, key: Key, config: SearchConfig | None = None,
) -> SearchResult:
    """Run beam-guided MCTS; requires a trustworthy predictive transition model."""
    cfg = config or SearchConfig()
    ranked, created, pruned = beam_rank(
        initial, actions, transition, evaluate, terminal, key, cfg
    )
    if not ranked or not ranked[0][2]:
        return SearchResult(None, evaluate(initial), (), created, pruned, 0, "no_plan")
    # Seed the tree with the best beam prefix; MCTS then explores bounded children.
    # Rank first-step candidates by estimated next-state value, then let MCTS
    # explore only the top K. This is a heuristic shortlist, not a calibrated
    # probability distribution.
    first_candidates = []
    for action in list(actions(initial))[:cfg.branching_limit]:
        if created >= cfg.max_nodes:
            pruned += 1
            break
        try:
            next_state = transition(initial, action)
            first_candidates.append((evaluate(next_state), action))
        except Exception:
            pruned += 1
    first_candidates.sort(key=lambda pair: pair[0], reverse=True)
    shortlist = [action for _, action in first_candidates[:cfg.top_k]]
    pruned += max(0, len(first_candidates) - len(shortlist))
    if not shortlist:
        return SearchResult(None, evaluate(initial), (), created, pruned, 0, "no_candidates")
    root = Node(initial, children=[], untried=shortlist.copy())
    rng = random.Random(cfg.seed)
    best_action = shortlist[0]
    best_score = first_candidates[0][0]
    seen = {key(initial)}
    iterations = 0
    for _ in range(cfg.iterations):
        iterations += 1
        node = root
        state = initial
        path = [root]
        depth = 0
        while depth < cfg.depth and not terminal(state):
            if node.children is None:
                node.children = []
            if node.untried is None:
                node.untried = []
            if node.untried and created < cfg.max_nodes:
                action = node.untried.pop(rng.randrange(len(node.untried)))
                next_state = transition(state, action)
                state_key = key(next_state)
                if state_key in seen:
                    pruned += 1
                    continue
                seen.add(state_key)
                child_actions = list(actions(next_state))[:min(cfg.branching_limit, cfg.max_children)]
                child = Node(next_state, node, action, children=[], untried=child_actions)
                node.children.append(child)
                node = child
                state = next_state
                path.append(node)
                created += 1
                depth += 1
                break
            if not node.children:
                break
            node = max(node.children[:cfg.max_children], key=lambda child: _uct(child, node.visits, cfg.exploration))
            state = node.state
            path.append(node)
            depth += 1
        reward = evaluate(state)
        # Discounted, bounded rollout: greedily choose top-scoring successor states.
        rollout_state = state
        rollout_score = reward
        for step in range(depth, cfg.depth):
            if terminal(rollout_state) or created >= cfg.max_nodes:
                break
            successors = []
            for action in list(actions(rollout_state))[:cfg.branching_limit]:
                nxt = transition(rollout_state, action)
                if key(nxt) in seen:
                    continue
                successors.append((evaluate(nxt), action, nxt))
            if not successors:
                break
            successors.sort(key=lambda item: item[0], reverse=True)
            cutoff = successors[0][0] - cfg.prune_delta
            successors = [item for item in successors if item[0] >= cutoff][:cfg.beam_width]
            if not successors:
                break
            score, _, rollout_state = successors[0]
            seen.add(key(rollout_state))
            created += 1
            rollout_score += (cfg.discount ** (step + 1)) * score
        for visited in path:
            visited.visits += 1
            visited.value_sum += rollout_score
        first = node
        while first.parent is not None and first.parent is not root:
            first = first.parent
        candidate_action = path[1].action if len(path) > 1 else None
        if candidate_action is not None and rollout_score > best_score:
            best_action, best_score = candidate_action, rollout_score
        if created >= cfg.max_nodes:
            pruned += 1
            break
    # Final choice favors explored root children; the top-K heuristic is a fallback.
    if root.children:
        winner = max(root.children, key=lambda child: (child.visits, child.value))
        best_action = winner.action
        best_score = winner.value if winner.visits else evaluate(winner.state)
    root_children = root.children or []
    summary = tuple((action, float(score), next((child.visits for child in root_children if child.action == action), 0))
                    for score, action in first_candidates[:cfg.top_k])
    plan = ranked[0][2] if ranked and ranked[0][2] and ranked[0][2][0] == best_action else (best_action,)
    return SearchResult(best_action, best_score, plan, created, pruned,
                        iterations, "bounded_search_complete", summary)


def main() -> int:
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsl", help="DSL file path")
    parser.add_argument("--demo", action="store_true", help="run on a small deterministic graph")
    args = parser.parse_args()
    with open(args.dsl, encoding="utf-8") as handle:
        config = compile_dsl(handle.read())
    if not args.demo:
        print(json.dumps({"config": config.__dict__, "status": "compiled",
                          "note": "Import search() and provide state/action callbacks to plan."}))
        return 0
    graph = {0: [1, 2, 3], 1: [4], 2: [5], 3: [6], 4: [7], 5: [7], 6: [0], 7: []}
    goal = 7
    result = search(0, lambda s: graph[s], lambda s, a: a,
                    lambda s: 10.0 if s == goal else -abs(goal - s),
                    lambda s: s == goal, lambda s: s, config)
    print(json.dumps({"action": result.action, "score": result.score,
                      "plan": list(result.plan), "top_candidates": [{"action": action, "heuristic_score": score, "mcts_visits": visits} for action, score, visits in result.candidate_summary], "nodes_created": result.nodes_created,
                      "nodes_pruned": result.nodes_pruned, "iterations": result.iterations,
                      "reason": result.reason}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
