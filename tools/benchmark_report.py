#!/usr/bin/env python3
"""Summarize measured SHUSH benchmark records; never invent missing measurements.

Input JSON:
{"tasks":[{"task_id":"t1","variants":{
  "conventional":{"input_tokens":12,"output_tokens":3,"correct":true,"latency_ms":10},
  "emoji_shorthand":{"input_tokens":8,"output_tokens":4,"correct":true,"latency_ms":11},
  "semantic_refs":{"input_tokens":5,"output_tokens":2,"correct":true,"latency_ms":7}
}}]}
Token values must come from the actual target tokenizer/provider usage metadata.
"""
from __future__ import annotations
import argparse
import json
import math
import sys
from pathlib import Path

VARIANTS = ("conventional", "emoji_shorthand", "semantic_refs")
REQUIRED = ("input_tokens", "output_tokens", "correct", "latency_ms")

class BenchmarkError(ValueError):
    pass

def load_records(path: str | Path) -> dict:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"cannot load benchmark JSON: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list) or not data["tasks"]:
        raise BenchmarkError("input must contain a non-empty tasks array")
    seen = set()
    for task in data["tasks"]:
        if not isinstance(task, dict) or not isinstance(task.get("task_id"), str) or not task["task_id"]:
            raise BenchmarkError("each task needs a non-empty task_id")
        if task["task_id"] in seen:
            raise BenchmarkError(f"duplicate task_id: {task['task_id']}")
        seen.add(task["task_id"])
        variants = task.get("variants")
        if not isinstance(variants, dict):
            raise BenchmarkError(f"{task['task_id']}: variants must be an object")
        for variant in VARIANTS:
            record = variants.get(variant)
            if not isinstance(record, dict):
                raise BenchmarkError(f"{task['task_id']}: missing variant {variant}")
            missing = [field for field in REQUIRED if field not in record]
            if missing:
                raise BenchmarkError(f"{task['task_id']}/{variant}: missing {', '.join(missing)}")
            if type(record["input_tokens"]) is not int or record["input_tokens"] < 0:
                raise BenchmarkError(f"{task['task_id']}/{variant}: input_tokens must be a nonnegative integer")
            if type(record["output_tokens"]) is not int or record["output_tokens"] < 0:
                raise BenchmarkError(f"{task['task_id']}/{variant}: output_tokens must be a nonnegative integer")
            if type(record["correct"]) is not bool:
                raise BenchmarkError(f"{task['task_id']}/{variant}: correct must be boolean")
            latency = record["latency_ms"]
            if isinstance(latency, bool) or not isinstance(latency, (int, float)) or not math.isfinite(latency) or latency < 0:
                raise BenchmarkError(f"{task['task_id']}/{variant}: latency_ms must be finite and nonnegative")
    return data

def summarize(data: dict) -> dict:
    tasks = data["tasks"]
    summaries = {}
    for variant in VARIANTS:
        rows = [task["variants"][variant] for task in tasks]
        total_tokens = sum(row["input_tokens"] + row["output_tokens"] for row in rows)
        summaries[variant] = {
            "task_count": len(rows),
            "correct_count": sum(row["correct"] for row in rows),
            "accuracy": sum(row["correct"] for row in rows) / len(rows),
            "input_tokens_total": sum(row["input_tokens"] for row in rows),
            "output_tokens_total": sum(row["output_tokens"] for row in rows),
            "total_tokens": total_tokens,
            "mean_tokens_per_task": total_tokens / len(rows),
            "mean_latency_ms": sum(row["latency_ms"] for row in rows) / len(rows),
        }
    baseline = summaries["conventional"]["total_tokens"]
    for variant, summary in summaries.items():
        summary["token_reduction_vs_conventional"] = (
            None if baseline == 0 else (baseline - summary["total_tokens"]) / baseline
        )
    return {
        "status": "measured_records_summarized",
        "task_count": len(tasks),
        "source_note": "Derived only from supplied records; this tool does not run models or count tokens.",
        "variants": summaries,
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file with measured records for all three variants")
    parser.add_argument("--output", help="optional path for summary JSON")
    args = parser.parse_args()
    try:
        report = summarize(load_records(args.input))
    except BenchmarkError as exc:
        print(f"BENCHMARK_ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
