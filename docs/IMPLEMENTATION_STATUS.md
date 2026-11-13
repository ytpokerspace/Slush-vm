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


## Unified host capability runtime (feature branch)

Branch: feat/unified-capability-runtime

Added in this branch:
- Python host capability runtime and MCP stdio server at runtime/shushos_runtime.py.
- ARC-2 adapter calls the separate arc_r2.primitives.fit_program implementation at a pinned revision; no copied solver implementation and no MCTS/beam substitution.
- ARC-AGI-3 legal-action validation envelope only; no unverified game policy or environment execution.
- QBS Pareto-front ranking with separate criteria and no fabricated aggregate probability.
- Glyphic Path Memory create/retrieve/hybridize operations with SHA-256 evidence checks and hypothesis-labelled hybrids.
- CSC-LCH source-byte preservation, duplicate-ID rejection, SHA-256, active/stub representation, byte accounting, budgeted graph hydration and exact reconstruction.
- Runtime conformance tests and a CI workflow.

Important boundary:
- These are host-side capabilities exposed to an LLM through MCP tools. They are not yet native SHUSH bytecode opcodes or calls from a complete SHUSH parser/VM.
- The C11 dispatcher remains a separate reference implementation. Native VM integration is a remaining gate.
- ARC-AGI-3 is not a solver yet; its game policy and transition model remain unspecified in source notes.
- ARC-2 adapter exact-fit output is not held-out validation or an official ARC score.
- No live LLM benchmark, token savings, latency, cost, energy or accuracy improvement is claimed.

Verification state: CI must pass on the feature branch before this implementation is described as tested. See docs/LLM_INTEGRATION.md.
