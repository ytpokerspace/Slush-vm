# SHUSH implementation status

Updated: 2026-10-13

This page separates verified implementation from design intent.

## Implemented and verified in GitHub Actions

- Offline Python workflow engine resolves explicit workflow aliases to exact capability IDs and versions.
- Demo capabilities: whitespace normalization and whitespace-delimited word counting.
- JSON vocabulary/alias/demo contracts generate c/generated_registry.h; CI checks the committed header is current.
- Standalone C11 capability-dispatch reference accepts an explicit namespace, emoji symbol, canonical capability ID, exact version, permission, and string argument.
- C dispatcher rejects unknown aliases, wrong namespace, canonical-ID mismatch, version mismatch, untested capability status, and permission mismatch.
- C strict-warning build and 9 C self-tests.
- 20 deterministic task definitions; CI executes all 20 against the compiled C dispatcher and compares outputs with expected answers.
- 60 prompt variants exported for later model runs.
- Live benchmark runner, raw-record assembler, report tool, and manually triggered GitHub Actions workflow. Live model calls are opt-in and require a repository secret.

## Not yet verified or implemented

- The full SHUSH source parser and original VM integration.
- Loading the registry dynamically at runtime; the C table is generated at build/commit time from JSON.
- The full set of production capabilities and permissions; current C handlers cover only two offline demo operations.
- Live LLM measurements. No API calls, provider token counts, or savings claims have been made by CI.
- End-to-end cost/latency of generating SHUSH, resolving references, executing capabilities, and validating outputs.
- Repeated randomized benchmark runs and statistical confidence estimates.

## Current blocker for full VM integration

The current main tree does not contain shushc.c or the full VM implementation. The open feat/minimal-semantic-registry branch contains a standalone registry scaffold, but not the parser/VM source either. Therefore this work deliberately remains a standalone reference dispatcher rather than pretending to be integrated with the actual compiler.

To complete integration, the real compiler/VM source needs to be committed to this repository (or its exact repository and branch identified). Then the registry resolver should be called from the VM's existing native dispatch path, with typed arguments and permission checks enforced at the actual invocation boundary. Preserve existing VM semantics and add end-to-end tests rather than replacing the compiler with this demo.

## Next acceptance gates

1. Integrate against the actual SHUSH parser/VM and run its full existing test suite.
2. Prove registry ID/version/type/permission checks at the real dispatch boundary, including negative tests.
3. Run the live benchmark with a fixed model and provider, first as a 3-call smoke test and then all 60 requests.
4. Repeat the benchmark across multiple runs; publish raw results and compare accuracy, provider-reported tokens, latency, and total cost per successful task.
5. Expand beyond string utilities to nontrivial tasks and include registry/tool/runtime overhead before making any efficiency claim.
