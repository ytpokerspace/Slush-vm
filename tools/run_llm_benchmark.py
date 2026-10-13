#!/usr/bin/env python3
"""Run the 20-task SHUSH comparison against an OpenAI-compatible chat API.

No network calls happen unless --run is supplied. API keys are read only from
SHUSH_BENCHMARK_API_KEY; never put credentials in the repository or CLI args.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VARIANTS = ("conventional", "emoji_shorthand", "semantic_refs")
SYSTEM_PROMPT = (
    "You perform exact text utilities. Normalize means replace each run of "
    "whitespace with one ASCII space and trim leading/trailing whitespace. "
    "Word count means count whitespace-delimited words. Interpret 🧹(STRING) "
    "as normalize and 🧮(STRING) as word_count. Interpret "
    "workflow.text.normalize@1.0.0(STRING) as normalize and "
    "workflow.text.word_count@1.0.0(STRING) as word_count. STRING is a "
    "JSON-quoted string literal. Return only the result, no explanation. "
    "For normalize, return the resulting string without added quotation marks. "
    "For word_count, return only a base-10 integer."
)

def request_completion(base_url: str, api_key: str, model: str, prompt: str, timeout: float):
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }).encode("utf-8")
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={"Authorization": "Bearer " + api_key,
                 "Content-Type": "application/json"},
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        # Do not print request headers or secrets.
        detail = exc.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"API HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"API request failed: {exc}") from None
    elapsed_ms = round((time.perf_counter() - start) * 1000, 3)
    try:
        content = body["choices"][0]["message"]["content"]
        usage = body["usage"]
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        returned_model = body.get("model", model)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"API response missing chat content or token usage: {exc}") from None
    if not isinstance(content, str):
        raise RuntimeError("API returned non-text content; this harness expects text-only chat completions")
    if type(input_tokens) is not int or type(output_tokens) is not int:
        raise RuntimeError("Provider did not return integer prompt_tokens and completion_tokens; refusing to estimate")
    return content, input_tokens, output_tokens, elapsed_ms, returned_model

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="required to make billable API calls")
    parser.add_argument("--model", default=os.getenv("SHUSH_BENCHMARK_MODEL"))
    parser.add_argument("--base-url", default=os.getenv("SHUSH_BENCHMARK_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--input", default=str(ROOT / "benchmarks/shush_20_tasks.json"))
    parser.add_argument("--output", default=str(ROOT / "benchmarks/results/shush_raw_results.jsonl"))
    parser.add_argument("--max-calls", type=int, default=60, help="cap calls for a small smoke run")
    parser.add_argument("--timeout", type=float, default=45.0)
    args = parser.parse_args()
    if not args.run:
        print("Preview only; no model calls made. Add --run to explicitly enable API calls.")
        print("Expected maximum calls:", args.max_calls)
        print("Each call may incur provider charges.")
        return 0
    if not args.model:
        print("ERROR: supply --model or SHUSH_BENCHMARK_MODEL", file=sys.stderr)
        return 2
    api_key = os.getenv("SHUSH_BENCHMARK_API_KEY")
    if not api_key:
        print("ERROR: set SHUSH_BENCHMARK_API_KEY in your environment", file=sys.stderr)
        return 2
    if not (1 <= args.max_calls <= 60):
        print("ERROR: --max-calls must be between 1 and 60", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("ERROR: --timeout must be positive", file=sys.stderr)
        return 2
    try:
        data = json.loads(Path(args.input).read_text(encoding="utf-8"))
        tasks = data["tasks"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"ERROR: cannot read task dataset: {exc}", file=sys.stderr)
        return 2
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if output.exists():
        for line in output.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            existing.add((row["task_id"], row["variant"]))
    calls = 0
    try:
        with output.open("a", encoding="utf-8") as stream:
            for task in tasks:
                for variant in VARIANTS:
                    key = (task["task_id"], variant)
                    if key in existing:
                        continue
                    if calls >= args.max_calls:
                        print(f"Paused after {calls} new calls. Rerun with same output to resume.")
                        return 0
                    prompt = task["prompts"][variant]
                    answer, in_tok, out_tok, latency, returned_model = request_completion(
                        args.base_url, api_key, args.model, prompt, args.timeout
                    )
                    normalized_answer = answer.strip()
                    if task["operation"] == "normalize":
                        correct = normalized_answer == task["expected"]
                    else:
                        correct = normalized_answer == task["expected"]
                    row = {
                        "task_id": task["task_id"],
                        "variant": variant,
                        "operation": task["operation"],
                        "expected": task["expected"],
                        "prompt": prompt,
                        "system_prompt": SYSTEM_PROMPT,
                        "answer": answer,
                        "correct": correct,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "latency_ms": latency,
                        "model_requested": args.model,
                        "model_returned": returned_model,
                        "base_url": args.base_url,
                        "measurement_source": "provider_usage_metadata",
                    }
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                    stream.flush()
                    existing.add(key)
                    calls += 1
                    print(f"{task['task_id']} {variant}: {'PASS' if correct else 'FAIL'} "
                          f"{in_tok}+{out_tok} tokens, {latency} ms")
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("Completed records are preserved; rerun with the same output path to resume.", file=sys.stderr)
        return 1
    print(f"Recorded {calls} new calls in {output}")
    print("A completed dataset requires 60 unique task/variant records.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
