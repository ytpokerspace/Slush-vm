# Slush-vm / SHUSHOS

SHUSH is an emoji-native surface language; SHUSHOS is the proposed runtime/control plane for resolving aliases to canonical, typed, versioned capabilities.

## Documents

- [Language and VM specification](docs/SHUSHOS_SPEC.md)
- [Capability contracts](registry/capabilities.json)
- [Emoji vocabulary and platform aliases](registry/vocabulary.json)
- [Diagnostics and error handling](docs/ERRORS_AND_DIAGNOSTICS.md)
- [Platform registries](docs/PLATFORM_REGISTRIES.md)
- [Security and execution model](docs/SECURITY_MODEL.md)
- [Registry validator](tools/validate_registry.py)
- [Standalone C capability dispatcher](c/shush_capability_vm.c)
- [Implementation status and remaining gates](docs/IMPLEMENTATION_STATUS.md)
- [Live benchmark run guide](docs/RUN_LIVE_BENCHMARK.md)
- [Benchmark runner](tools/run_llm_benchmark.py)
- [Benchmark result assembler](tools/assemble_benchmark_results.py)
- [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md)

## Status

The language and platform documents remain design drafts. A standalone C11 capability-dispatch prototype, offline Python workflow demo, and benchmark harness are implemented and tested in CI. They are not yet integrated into a complete SHUSH parser/full VM. Manifest entries marked planned are not implemented capabilities; check implementation and test status before relying on one.

The minimal registry scaffold is tracked separately in [PR #1](https://github.com/ytpokerspace/Slush-vm/pull/1). This documentation branch does not replace or merge that work.

## Validate

~~~sh
python3 tools/validate_registry.py
~~~

The validator uses only the Python standard library. It checks required fields and duplicate canonical IDs, then reports emoji aliases reused across namespaces. Reused symbols are allowed only when namespace/context resolves them unambiguously.

## Principles

1. Emoji are aliases; canonical IDs carry semantic identity.
2. Resolve exact versions deterministically; never silently select incompatible implementations.
3. Validate types, permissions, platforms, and resource constraints before execution.
4. Separate planned, implemented, and tested states.
5. Measure token savings and correctness instead of assuming compression improves quality.


## ARC-AGI-3 object value planning (experimental)

The ARC solver branch includes `arc3/object_value_planner.py`, a small heuristic scaffold for separating per-object decision estimates from global objective arbitration. It scores goal value, estimated success probability, information value, risk, and action cost; it can recommend pursuing, preparing for, or deferring an objective. Deferred objectives remain in the result so they can be reconsidered after new observations.

This module is a decision primitive, not yet an integrated semantic object detector or a proven improvement to game performance. Its numeric inputs and utility weights are heuristics unless supplied from measured evidence. It does not generate or store private chain-of-thought; it stores compact decision factors and outcomes. Unit tests cover deferral, preparation, arbitration, and input validation.


## ARC object-centric perception (experimental)

The ARC solver branch includes `arc3/object_perception.py`. It extracts connected components and reports geometry: area, bounding-box width/height, aspect ratio, fill density, color counts, center, relative size/dimension ranks, and tentative geometric role hypotheses. The runner stores the resulting object summary in the partitioned planning memory and includes it in its JSON output.

These descriptors support "what it looks like" and "how it compares" but do not prove what an object means in game terms. The default background estimate uses the most frequent pixel value and can fail on multi-color backgrounds; explicit background colors are supported. Diagonal adjacency, occlusion, animation, and role identification remain open problems. Object identity confidence remains zero until evidence beyond geometry is added.
