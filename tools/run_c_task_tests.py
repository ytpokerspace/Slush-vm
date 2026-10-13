#!/usr/bin/env python3
"""Compile the C reference dispatcher and execute every deterministic starter task."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main():
    dataset_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "benchmarks/shush_20_tasks.json"
    try:
        dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot load task dataset: {exc}", file=sys.stderr)
        return 2
    tasks = dataset.get("tasks", [])
    with tempfile.TemporaryDirectory(prefix="shush-c-tests-") as tmp:
        binary = str(Path(tmp) / "shush-capvm")
        compile_cmd = ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
                       str(ROOT / "c/shush_capability_vm.c"), "-o", binary]
        built = subprocess.run(compile_cmd, capture_output=True, text=True)
        if built.returncode:
            print(built.stderr, file=sys.stderr)
            return built.returncode
        passed = 0
        for task in tasks:
            if task["operation"] == "normalize":
                symbol, capability = "🧹", "text.normalize"
            elif task["operation"] == "word_count":
                symbol, capability = "🧮", "text.word_count"
            else:
                print(f"ERROR {task.get('task_id')}: unsupported operation", file=sys.stderr)
                return 2
            result = subprocess.run(
                [binary, "call", "workflow", symbol, capability, "1.0.0",
                 "capability.execute", task["input"]],
                capture_output=True, text=True, encoding="utf-8"
            )
            actual = result.stdout[:-1] if result.stdout.endswith("\n") else result.stdout
            if result.returncode == 0 and actual == task["expected"]:
                passed += 1
                print(f"PASS {task['task_id']} ({task['operation']})")
            else:
                print(f"FAIL {task['task_id']}: expected {task['expected']!r}, got {actual!r}; "
                      f"exit={result.returncode}; stderr={result.stderr.strip()!r}", file=sys.stderr)
        print(f"C task integration tests: {passed}/{len(tasks)} passed")
        return 0 if passed == len(tasks) and len(tasks) == 20 else 1

if __name__ == "__main__":
    raise SystemExit(main())
