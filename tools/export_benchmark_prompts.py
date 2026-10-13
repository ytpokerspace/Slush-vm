#!/usr/bin/env python3
"""Export the 20-task set as 60 labeled prompts for controlled model runs."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("conventional", "emoji_shorthand", "semantic_refs")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(ROOT / "benchmarks/shush_20_tasks.json"))
    parser.add_argument("--output", default=str(ROOT / "benchmarks/shush_20_prompts.jsonl"))
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    tasks = data.get("tasks", [])
    rows = []
    for task in tasks:
        for variant in VARIANTS:
            rows.append({
                "task_id": task["task_id"],
                "variant": variant,
                "operation": task["operation"],
                "input": task["input"],
                "expected": task["expected"],
                "prompt": task["prompts"][variant],
                "measurement": {
                    "model": None,
                    "model_version": None,
                    "provider": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "correct_first_attempt": None,
                    "latency_ms": None,
                    "notes": None
                }
            })
    Path(args.output).write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\\n" for row in rows),
        encoding="utf-8"
    )
    print(f"Exported {len(rows)} prompts to {args.output}")
    print("Measurement fields are blank; populate only from actual runs.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
