# SHUSH benchmark protocol

Compare three modes on the same tasks: conventional instructions, emoji shorthand, and emoji references to exact tested capabilities.

Record per task and mode: input tokens, output tokens, correctness on the first attempt, and elapsed milliseconds. Token counts must come from actual provider usage metadata or the target tokenizer, not character estimates. Include all prompts, registry text, tool calls, and output used in the real path.

The reporter at tools/benchmark_report.py validates these records and calculates totals, accuracy, average tokens per task, mean latency, and token reduction against the conventional baseline. It does not call a model or tokenize prompts.

The previously mentioned 20-task dataset was not present in the checked-in repository when this protocol was added. Do not create results from guesses or label synthetic values as measured results.