#!/usr/bin/env python3
"""Convert completed raw model-run JSONL records into benchmark_report.py input."""
import argparse
import json
import sys
from pathlib import Path

VARIANTS = ("conventional", "emoji_shorthand", "semantic_refs")
REQUIRED = ("task_id", "variant", "input_tokens", "output_tokens", "correct", "latency_ms",
            "model_returned", "measurement_source")

def assemble(raw_path: str, tasks_path: str) -> dict:
    rows = []
    for line_no, line in enumerate(Path(raw_path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_no}: invalid JSON: {exc}") from exc
        missing = [key for key in REQUIRED if key not in row]
        if missing:
            raise ValueError(f"line {line_no}: missing fields {', '.join(missing)}")
        if row["measurement_source"] != "provider_usage_metadata":
            raise ValueError(f"line {line_no}: token counts must come from provider usage metadata")
        if row["variant"] not in VARIANTS:
            raise ValueError(f"line {line_no}: unknown variant {row['variant']!r}")
        if type(row["input_tokens"]) is not int or row["input_tokens"] < 0:
            raise ValueError(f"line {line_no}: invalid input token count")
        if type(row["output_tokens"]) is not int or row["output_tokens"] < 0:
            raise ValueError(f"line {line_no}: invalid output token count")
        if type(row["correct"]) is not bool:
            raise ValueError(f"line {line_no}: correct must be boolean")
        if isinstance(row["latency_ms"], bool) or not isinstance(row["latency_ms"], (int, float)) or row["latency_ms"] < 0:
            raise ValueError(f"line {line_no}: invalid latency")
        rows.append(row)
    by_key = {}
    models = set()
    systems = set()
    for row in rows:
        key = (row["task_id"], row["variant"])
        if key in by_key:
            raise ValueError(f"duplicate measurement: {key[0]}/{key[1]}")
        by_key[key] = row
        models.add(row["model_returned"])
        if "system_prompt" in row:
            systems.add(row["system_prompt"])
    if len(models) != 1:
        raise ValueError(f"expected one returned model across the run, found {sorted(models)}")
    if len(systems) > 1:
        raise ValueError("system prompt changed within this run")
    task_doc = json.loads(Path(tasks_path).read_text(encoding="utf-8"))
    tasks = task_doc.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("task dataset has no tasks")
    expected_keys = {(task["task_id"], variant) for task in tasks for variant in VARIANTS}
    missing_keys = expected_keys - set(by_key)
    extra_keys = set(by_key) - expected_keys
    if missing_keys or extra_keys:
        details = []
        if missing_keys:
            details.append("missing " + ", ".join(f"{t}/{v}" for t, v in sorted(missing_keys)[:8]))
        if extra_keys:
            details.append("unexpected " + ", ".join(f"{t}/{v}" for t, v in sorted(extra_keys)[:8]))
        raise ValueError("run must contain exactly one record for every task/variant: " + "; ".join(details))
    result_tasks = []
    for task in tasks:
        variants = {}
        for variant in VARIANTS:
            row = by_key[(task["task_id"], variant)]
            variants[variant] = {
                "input_tokens": row["input_tokens"],
                "output_tokens": row["output_tokens"],
                "correct": row["correct"],
                "latency_ms": row["latency_ms"],
            }
        result_tasks.append({"task_id": task["task_id"], "variants": variants})
    return {
        "schema_version": "1.0.0",
        "status": "measured_provider_results",
        "model": next(iter(models)),
        "measurement_source": "provider_usage_metadata",
        "system_prompt": next(iter(systems)) if systems else None,
        "task_count": len(result_tasks),
        "tasks": result_tasks,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw_jsonl")
    parser.add_argument("--tasks", default="benchmarks/shush_20_tasks.json")
    parser.add_argument("--output", default="benchmarks/results/shush_measured_results.json")
    args = parser.parse_args()
    try:
        result = assemble(args.raw_jsonl, args.tasks)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ASSEMBLY_ERROR: {exc}", file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Assembled {result['task_count']} tasks across 3 variants into {output}")
    print("Next: python tools/benchmark_report.py " + str(output))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
