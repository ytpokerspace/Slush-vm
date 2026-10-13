#!/usr/bin/env python3
"""Validate task definitions separately from actual measured benchmark results."""
import json
import sys
from pathlib import Path

def main():
    if len(sys.argv) != 2:
        print("usage: validate_benchmark_tasks.py DATASET.json", file=sys.stderr)
        return 64
    try:
        data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = []
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list) or len(tasks) != 20:
        errors.append("starter dataset must contain exactly 20 tasks")
    ids = [t.get("task_id") for t in tasks if isinstance(t, dict)]
    if len(ids) != len(tasks) or len(set(ids)) != len(ids):
        errors.append("every task needs a unique task_id")
    for task in tasks or []:
        if task.get("operation") not in ("normalize", "word_count"):
            errors.append(f"{task.get('task_id')}: unsupported operation")
        if not isinstance(task.get("input"), str) or not isinstance(task.get("expected"), str):
            errors.append(f"{task.get('task_id')}: input and expected must be strings")
        prompts = task.get("prompts", {})
        if any(not isinstance(prompts.get(v), str) or not prompts[v]
               for v in ("conventional", "emoji_shorthand", "semantic_refs")):
            errors.append(f"{task.get('task_id')}: missing one of the three prompts")
        if task.get("measurements") is not None:
            errors.append(f"{task.get('task_id')}: measurements must remain null until actually measured")
    if errors:
        for err in errors:
            print("ERROR:", err, file=sys.stderr)
        return 1
    print(f"OK: {len(tasks)} task definitions; 0 measurements claimed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
