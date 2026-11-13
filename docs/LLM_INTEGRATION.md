# SHUSHOS unified capability runtime

## What this adds

This branch adds a dependency-light Python host runtime at runtime/shushos_runtime.py and an MCP-compatible stdio tool server. The LLM-facing interface uses typed JSON tool inputs and structured JSON results. Each tool maps to a fixed capability function; model-provided strings are never evaluated as code.

The implementation is deliberately a **host capability runtime**, not a claim that the repository now contains the full SHUSH parser or bytecode VM. The current C dispatcher remains a separate C11 reference slice. A future VM integration must call this same capability registry at its native dispatch boundary rather than reimplementing each algorithm.

## Capability map

| Capability | Executable behavior | Boundary |
|---|---|---|
| arc2.fit_program | Calls arc_r2.primitives.fit_program from the separately maintained ARC-2 repository | Requires that repository on PYTHONPATH; only fits supplied training pairs; MCTS and beam search are off |
| arc3.validate_action | Checks an LLM-proposed action against an environment-supplied legal-action list | No game policy, transition model, or environment execution is claimed |
| qbs.rank_hypotheses | Validates separate criteria and computes non-dominated Pareto fronts | No invented aggregate score; probabilities remain uncalibrated estimates |
| glyphic.create_path | Versioned event/glyph records, duplicate-ID rejection, tags and SHA-256 evidence | Evidence is retained; glyph encoding is not lossless compression |
| glyphic.retrieve_paths | Tag Jaccard retrieval | Not embedding-based semantic search |
| glyphic.hybridize_paths | Maximal suffix/prefix event stitching | Output remains a hypothesis; stitching is not proof of logical compatibility |
| csc_lch.ingest | Preserves exact source bytes and SHA-256; validates node graph references | Caller supplies graph nodes and byte ranges |
| csc_lch.compress | Creates active node views and lazy stubs; reports source, graph, total and active bytes | Original source remains stored; active-context reduction is not total-storage reduction |
| csc_lch.hydrate | Tag-ranked graph traversal, byte budget, hop limit, overlap merge and source hash verification | Hydration is byte-range based; relevance is tag overlap |
| csc_lch.reconstruct | Returns original base64 bytes after SHA-256 verification | Exact byte reconstruction only |

## Install and run

Python 3.11+; runtime and tests use the Python standard library.

For ARC-2 integration, check out the ARC-2 repository at the same pinned commit used by CI:

eeaeaea682461596fc80ea62d09e6cc666b59a7d

Then expose both folders by setting PYTHONPATH=runtime:arc2-source and launching python runtime/shushos_runtime.py.

The process speaks newline-delimited JSON-RPC over stdin/stdout using the MCP stdio transport. Configure an MCP client to launch Python with this script as its command/argument. Keep stdout reserved for protocol messages; diagnostics belong on stderr.

Without the ARC-2 checkout, the other capabilities still work. An ARC-2 call fails closed with E_DEPENDENCY_MISSING; it does not silently substitute another solver.

## Example MCP tool calls

The server exposes these tools through tools/list:

- arc2_fit_program
- arc3_validate_action
- qbs_rank_hypotheses
- glyphic_create_path
- glyphic_retrieve_paths
- glyphic_hybridize_paths
- csc_lch_ingest
- csc_lch_compress
- csc_lch_hydrate
- csc_lch_reconstruct

Example ARC-2 arguments:

    {
      "training_pairs": [
        {
          "input": [[0, 1], [0, 0]],
          "output": [[1, 0], [0, 0]]
        }
      ],
      "candidate_cap": 5000,
      "max_depth": 1
    }

A returned exact-fit program means only that it reproduces every pair supplied to that call. It does not establish held-out generalization or an official ARC score.

## Safety and execution model

- No arbitrary Python evaluation, shell execution, filesystem browsing, or network request tool is exposed.
- Capability names map to fixed functions.
- Inputs are type/range checked and failures use stable error codes.
- ARC-3 action validation does not execute the action.
- The MCP host should display tool calls and require user authorization for consequential operations.
- Persistent data is passed explicitly in tool arguments/results; this server does not silently maintain a hidden database.
- The optional ARC-2 import is code from a separately pinned repository revision.

## Verification

Run compileall on runtime, then run unittest discovery on runtime/tests with PYTHONPATH set to runtime:arc2-source.

CI checks the pinned ARC-2 adapter and all local conformance tests. The tests are not an official ARC benchmark. No LLM quality, token reduction, speed, energy, or cost improvement is claimed by this change.

## Next integration gates

1. Verify CI on this branch.
2. Add an actual SHUSH parser/VM source and connect its native dispatch to this same host capability contract.
3. Recover the ARC-AGI-3 observation/action/state protocol from the live solver source before implementing a game policy.
4. Compare runtime tool schemas with a real MCP host and document a tested client configuration.
5. Add dataset-backed ARC-2 held-out evaluation only as a separate, explicitly authorized benchmark run.
