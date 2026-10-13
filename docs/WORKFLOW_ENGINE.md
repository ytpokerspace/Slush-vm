# SHUSH Workflow Engine — vocabulary-integrated prototype

This offline reference runner now resolves emoji through the project's
`registry/vocabulary.json` and explicit `registry/workflow_aliases.json`
before resolving an exact, versioned capability in
`examples/demo_capabilities.json`.

## Run

From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_workflow_engine.py' -v
python3 tools/workflow_engine.py
```

The default example should normalize a string and count three words. Workflow
steps use `symbol` and explicit `namespace`; prior-step references use
`$step_id.field`. The engine checks that each alias maps to exactly one
matching vocabulary entry and one exact capability version.

## Safety and failure behavior

- No implicit alias fallback; namespace is mandatory.
- Unknown emoji, missing aliases, vocabulary mismatches, and ambiguous aliases
  produce explicit error codes.
- If both emoji and canonical capability are supplied, they must resolve to
  the same ID and version.
- Only `tested` capabilities with registered handlers and granted permissions
  execute; inputs and outputs are type-checked.
- The workflow file is data, not Python or shell code.

## Scope and honest limitations

`examples/demo_capabilities.json` contains two pure, in-memory demonstration
capabilities. Their `tested` status refers only to the unit-test contract in
this small example; run the test suite to verify the current checkout.
The main `registry/capabilities.json` still declares the production-facing
capability contracts as `planned`. This prototype does not yet dispatch to
the C VM, execute general SHUSH source, provide a security sandbox, or prove
token savings. Do not register untrusted Python handlers.
