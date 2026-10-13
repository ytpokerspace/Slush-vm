# Running the live SHUSH model benchmark

## What it measures

The live runner sends each of the 20 task prompts in three formats to the same configured chat-completions model: conventional instructions, emoji shorthand, and canonical semantic references. A full run is 60 requests.

It records provider-reported prompt and completion token counts, returned model ID, exact first-answer correctness, and elapsed request time. The shared system prompt defines both emoji and canonical reference syntax so the comparison is interpretable; its tokens are included in provider-reported input usage for every variant.

This is a small starter benchmark, not a statistically conclusive evaluation. One request per task/variant can be affected by model variability and service load. Repeat runs and expand the task set before drawing broad conclusions.

## Run through GitHub Actions

1. In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
2. Add a repository secret named `SHUSH_BENCHMARK_API_KEY` with the API key for the provider you intend to use. Do not commit the key or put it in workflow inputs.
3. Open **Actions → SHUSH live LLM benchmark → Run workflow**.
4. Enter the exact model ID and the provider's OpenAI-compatible API base URL.
5. First run with `max_calls = 3` as a smoke test. Each request may incur charges.
6. If the smoke test works, start another run with `max_calls = 60` for the complete comparison.
7. Download the `shush-benchmark-results` artifact. A full run includes raw JSONL records, an assembled results file, and a summary report.

The workflow never runs model calls on ordinary pushes. It runs only when manually started. The secret is passed through the workflow environment and is not written to result files.

## Run locally

Requires Python 3.10+ and a provider that supports the OpenAI Chat Completions API shape.

Set these environment variables in your shell:
- `SHUSH_BENCHMARK_API_KEY`: provider API key
- `SHUSH_BENCHMARK_MODEL`: exact model ID
- Optional `SHUSH_BENCHMARK_BASE_URL`: defaults to `https://api.openai.com/v1`

Preview without network calls:

```sh
python tools/run_llm_benchmark.py --max-calls 1
```

Make an explicitly enabled 3-call smoke test:

```sh
python tools/run_llm_benchmark.py --run --max-calls 3 --output /tmp/shush_raw_results.jsonl
```

A full run and report:

```sh
python tools/run_llm_benchmark.py --run --max-calls 60 --output /tmp/shush_raw_results.jsonl
python tools/assemble_benchmark_results.py /tmp/shush_raw_results.jsonl --output /tmp/shush_measured_results.json
python tools/benchmark_report.py /tmp/shush_measured_results.json
```

If a request fails, completed JSONL records remain on disk. Rerunning with the same output path resumes missing task/variant pairs. Do not combine different model IDs or providers into one run; the assembler rejects mixed configurations.

## Limits and interpretation

- Token counts must be supplied by provider usage metadata. If the API omits them, the runner fails rather than estimating.
- Input-token counts include the shared system prompt and the variant-specific user prompt. Output-token counts include the model answer.
- Latency is wall-clock time for each HTTP request; it includes provider/network delay, not just model execution.
- Correctness is exact after trimming outer whitespace. The full response is retained in raw records for audit.
- The emoji and canonical forms are prompts to a model, not actual execution through the C capability VM. This benchmark tests model comprehension and prompt-token cost, not end-to-end runtime speed.
- For production claims, include any registry hydration, tool call, validation, translation, and execution overhead in a separate end-to-end benchmark.
- Never publish a token-savings claim from task definitions, prompt character counts, or synthetic test fixtures. Use only actual provider usage records.
