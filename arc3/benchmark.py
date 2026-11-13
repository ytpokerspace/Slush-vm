"""Repeatable ARC-AGI-3 live benchmark harness for the emoji exploration baseline.

Runs a bounded set of game/seed episodes through the official SDK runner and writes
machine-readable per-run results plus aggregate metrics. A non-winning episode is a
valid result; infrastructure failures are reported separately.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def extract_result(stdout: str) -> dict[str, Any] | None:
    """Find the runner's final JSON object even if the SDK printed extra log lines."""
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and "game_id" in parsed and "steps" in parsed:
            return parsed
    return None


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate outcomes without treating an incomplete run as a win."""
    # An error record may contain steps=0 for timeout/no-output; it is not an executed episode.
    valid = [r for r in results if isinstance(r.get("steps"), int) and not r.get("error")]
    wins = sum(1 for r in valid if r.get("won") is True)
    levels = sum(int(r.get("levels_completed") or 0) for r in valid)
    win_levels = sum(int(r.get("win_levels") or 0) for r in valid)
    actions = sum(int(r.get("steps") or 0) for r in valid)
    failures = sum(1 for r in results if r.get("error"))
    return {
        "runs_requested": len(results),
        "runs_executed": len(valid),
        "runs_failed": failures,
        "wins": wins,
        "win_rate": wins / len(valid) if valid else 0.0,
        "total_actions": actions,
        "total_levels_completed": levels,
        "total_levels_available_reported": win_levels,
        "level_completion_fraction": levels / win_levels if win_levels else 0.0,
        "results": results,
    }


def summarize_policy_comparison(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize each policy and paired differences on identical game/seed runs."""
    policies = sorted({str(row.get("policy", "legacy")) for row in results})
    by_policy = {
        policy: summarize_results([row for row in results if row.get("policy", "legacy") == policy])
        for policy in policies
    }
    paired = []
    keys = sorted({
        (row.get("game_id"), row.get("seed"))
        for row in results if row.get("game_id") is not None and row.get("seed") is not None
    }, key=lambda item: (str(item[0]), int(item[1])))
    indexed = {
        (row.get("policy", "legacy"), row.get("game_id"), row.get("seed")): row
        for row in results
    }
    if "legacy" in policies and "glyph" in policies:
        for game_id, seed in keys:
            baseline = indexed.get(("legacy", game_id, seed))
            candidate = indexed.get(("glyph", game_id, seed))
            if not baseline or not candidate:
                continue
            valid = not baseline.get("error") and not candidate.get("error")
            paired.append({
                "game_id": game_id,
                "seed": seed,
                "valid_pair": valid,
                "legacy_won": baseline.get("won"),
                "glyph_won": candidate.get("won"),
                "legacy_steps": baseline.get("steps"),
                "glyph_steps": candidate.get("steps"),
                "glyph_minus_legacy_steps": (
                    int(candidate["steps"]) - int(baseline["steps"]) if valid else None
                ),
                "legacy_levels_completed": baseline.get("levels_completed"),
                "glyph_levels_completed": candidate.get("levels_completed"),
            })
    valid_pairs = [row for row in paired if row["valid_pair"]]
    return {
        "policies": by_policy,
        "paired_comparisons": paired,
        "paired_summary": {
            "pairs_requested": len(paired),
            "pairs_valid": len(valid_pairs),
            "glyph_wins_not_legacy": sum(
                row["glyph_won"] is True and row["legacy_won"] is not True
                for row in valid_pairs
            ),
            "legacy_wins_not_glyph": sum(
                row["legacy_won"] is True and row["glyph_won"] is not True
                for row in valid_pairs
            ),
            "mean_glyph_minus_legacy_steps": (
                sum(row["glyph_minus_legacy_steps"] for row in valid_pairs)
                / len(valid_pairs) if valid_pairs else None
            ),
        },
    }


def run_episode(
    game_id: str,
    seed: int,
    max_actions: int,
    click_strategy: str,
    max_click_points: int,
    save_recording: bool,
    timeout_seconds: int,
    policy: str = "legacy",
) -> dict[str, Any]:
    command = [
        sys.executable, "-m", "arc3.arc_agi_runner",
        "--game-id", game_id,
        "--policy", policy,
        "--seed", str(seed),
        "--max-actions", str(max_actions),
        "--click-strategy", click_strategy,
        "--max-click-points", str(max_click_points),
    ]
    if save_recording:
        command.append("--save-recording")
    try:
        completed = subprocess.run(
            command, text=True, capture_output=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired:
        return {
            "game_id": game_id, "seed": seed, "steps": 0, "won": False,
            "error": f"episode timed out after {timeout_seconds} seconds",
        }

    result = extract_result(completed.stdout)
    if result is None:
        detail = (completed.stderr or completed.stdout or "runner produced no output").strip()
        return {
            "game_id": game_id, "seed": seed, "steps": 0, "won": False,
            "error": detail[-2000:],
            "runner_exit_code": completed.returncode,
        }
    result["runner_exit_code"] = completed.returncode
    result["policy"] = policy
    if completed.returncode != 0:
        result["error"] = (completed.stderr or "runner returned nonzero exit status").strip()[-2000:]
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", default="ls20", help="Comma-separated game IDs")
    parser.add_argument("--seeds", default="0,1,2", help="Comma-separated integer seeds")
    parser.add_argument("--max-actions", type=int, default=32)
    parser.add_argument("--click-strategy", choices=("foreground", "scan", "center"), default="foreground")
    parser.add_argument("--max-click-points", type=int, default=16)
    parser.add_argument("--run-timeout", type=int, default=180)
    parser.add_argument("--save-recording", action="store_true")
    parser.add_argument("--policies", default="legacy,glyph",
                        help="Comma-separated policies to compare on identical game/seed pairs")
    parser.add_argument("--output", default="arc3-benchmark.json")
    args = parser.parse_args()
    if args.max_actions < 1 or args.max_click_points < 1 or args.run_timeout < 1:
        parser.error("action budget, click-point budget, and timeout must be positive")

    games = [part.strip() for part in args.games.split(",") if part.strip()]
    try:
        seeds = [int(part.strip()) for part in args.seeds.split(",") if part.strip()]
    except ValueError:
        parser.error("--seeds must be comma-separated integers")
    policies = [part.strip() for part in args.policies.split(",") if part.strip()]
    if not games or not seeds or not policies:
        parser.error("--games, --seeds, and --policies must each contain at least one value")
    if len(set(policies)) != len(policies) or any(p not in {"legacy", "glyph"} for p in policies):
        parser.error("--policies accepts each of: legacy, glyph (no duplicates)")

    results = []
    for game_id in games:
        for seed in seeds:
            for policy in policies:
                result = run_episode(
                    game_id, seed, args.max_actions, args.click_strategy,
                    args.max_click_points, args.save_recording, args.run_timeout,
                    policy=policy,
                )
                result.setdefault("policy", policy)
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)

    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "aggregate_all_policy_runs": summarize_results(results),
        "policies": policies,
        "comparison": summarize_policy_comparison(results),
        "click_strategy": args.click_strategy,
        "max_actions_per_run": args.max_actions,
        "games": games,
        "seeds": seeds,
        "note": "Exploration metrics only; not a claim of benchmark-level solving.",
    })
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({
        "summary": {k: v for k, v in report.items() if k != "results"},
        "output": args.output,
    }, ensure_ascii=False))
    return 1 if report["runs_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
