# SHUSH semantic-reference benchmark

## Status and scope

This is the benchmark protocol, not a claim of measured gains. Do not fill results with estimates. Run the three arms on the same task corpus, with identical semantic requirements, runtime limits, and test suites.

## Arms

- **A — ordinary generation:** ask the model to produce ordinary source code.
- **B — emoji-native, no references:** ask it to produce SHUSH/emoji-native expressions that inline their implementations.
- **C — emoji-native, verified references:** ask it to use only exact registry IDs and versions; resolve them, check types/permissions/test status, then execute the resolved implementation.

Use the same model/version, prompt information, sampling settings, task order (randomized or counterbalanced), and execution environment. Repeat each task multiple times. Keep the model-facing prompt and all generated output for audit.

## Required per-run fields

Record one row per generated attempt:

`task_id,arm,model,model_version,prompt_tokens,generated_tokens,repair_tokens,registry_maintenance_tokens,first_pass_correct,resolver_attempted,resolver_correct,resolver_failure,execution_ms,validation_ms,notes`

- **Prompt tokens:** input tokens counted by the actual model tokenizer.
- **Generated tokens:** output tokens counted by that tokenizer; never estimate from characters.
- **Repair tokens:** all tokens consumed by retries, debugging, and corrections.
- **Registry maintenance tokens:** amortized tokens spent authoring, reviewing, testing, versioning, and updating the registry. Report both raw and amortized values, with the amortization rule stated.
- **First-pass correctness:** exact required output and all tests pass without repair.
- **Resolver accuracy:** correct resolutions / all attempted resolutions. Also report unsafe or incompatible resolutions; the required value is zero.
- **Execution time:** measure generation separately from compile/resolve/runtime and validation. Report median and p95, not just the mean.
- **Maintenance cost:** human minutes, CI time, registry size, and number of changes required per capability.

## Core equations

Total token cost per task:

`total_tokens = prompt_tokens + generated_tokens + repair_tokens + amortized_registry_maintenance_tokens`

First-pass correctness rate:

`correct_first_pass / total_attempts`

Resolver accuracy:

`correct_resolutions / attempted_resolutions`

Also report task success after repair, median/p95 wall-clock latency, and total cost per successful task. A shorter generated expression is not a win if maintenance, retries, or failures erase the savings.

## Acceptance gates

1. Resolver rejects unknown IDs and versions, wrong arity/types, missing permissions, and unverified capabilities with explicit errors.
2. No silent fallback and zero incompatible dispatches in adversarial tests.
3. All three arms execute the same task set and are checked against the same oracle.
4. Publish raw run rows, task corpus, tokenizer identity, environment, and analysis script.
5. Claim a benefit only if C improves total cost per successful task without reducing correctness beyond a predeclared tolerance. Include confidence intervals across tasks/runs.

## Current implementation limitation

The current repository did not contain `shushc.c` or an existing VM source when inspected. The initial scaffold therefore tests the resolver independently; it does not yet claim compiler/VM integration or benchmark results. The registry is represented in JSON and the C resolver currently uses a matching compiled-in entry. The next integration step is to generate the C table from `registry.json` and connect resolution to the actual parser/dispatcher once the runtime source is available.
