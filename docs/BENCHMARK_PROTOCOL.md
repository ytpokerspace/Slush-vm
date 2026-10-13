# SHUSH benchmark protocol

Compare three modes on the same tasks: conventional instructions, emoji shorthand, and emoji references to exact tested capabilities.

Record per task and mode: input tokens, output tokens, correctness on the first attempt, and elapsed milliseconds. Token counts must come from actual provider usage metadata or the target tokenizer, not character estimates. Include all prompts, registry text, tool calls, and output used in the real path.

The reporter at tools/benchmark_report.py validates these records and calculates totals, accuracy, average tokens per task, mean latency, and token reduction against the conventional baseline. It does not call a model or tokenize prompts.

The checked-in 20-task starter dataset is in `benchmarks/shush_20_tasks.json`. The live runner in `tools/run_llm_benchmark.py` makes provider calls only when explicitly passed `--run`; it records provider usage metadata and exact first-answer correctness. See `docs/RUN_LIVE_BENCHMARK.md` for setup. Task definitions are not measurements. Do not create results from guesses or label synthetic values as measured results.