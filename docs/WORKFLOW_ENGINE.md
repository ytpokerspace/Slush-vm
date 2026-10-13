# SHUSH Workflow Engine — first executable slice

This is a deliberately small, offline reference implementation for deterministic
workflow composition. It is designed to sit beside the existing SHUSHOS registry;
it does not replace the C VM or claim that every registry capability is implemented.

## Run

From the repository root:

```sh
python3 -m unittest tests.test_workflow_engine -v
python3 tools/workflow_engine.py examples/normalize_and_count.workflow.json
```

The sample engine has two pure, in-memory handlers: `text.normalize@1.0.0`
and `text.word_count@1.0.0`. No network, filesystem mutation, shell execution,
or model API is used.

## Contract

- Canonical capability ID **and exact version** are required.
- Only capabilities with `status: tested` can execute.
- Every required permission must be explicitly granted.
- Inputs and outputs are checked against declared primitive types.
- Prior-step output references use `$step_id.field`.
- Unknown, untested, unauthorized, malformed, or type-incompatible steps fail
  with a stable error code; there is no fallback resolver.
- Handlers are explicitly supplied Python callables; workflow text is never
  evaluated as Python or shell code.

## Important limitation

This is a local prototype, not a sandbox. A registered handler is trusted code.
Do not register untrusted handlers. Resource limits, cancellation, nested
composition, registry-schema integration, emoji parser integration, and C VM
dispatch remain future work. The example's `symbol` field is descriptive;
the current runner resolves canonical IDs, not emoji aliases.

## Benchmark honesty

Passing unit tests demonstrates these tested behaviors only. It does not prove
token savings, improved model accuracy, production security, or performance
advantages. Those require separate, controlled measurements.
