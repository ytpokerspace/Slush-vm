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


## License

Copyright (C) 2026 William Gunnell Cox.

This project is licensed under the GNU General Public License v3.0 or later (GPL-3.0-or-later). See [LICENSE](LICENSE).


## Project at a glance

**What it is:** An emoji-native surface-language and capability-runtime research project. Emoji act as readable aliases; canonical identifiers, typed contracts, versions, and permissions define the underlying capability.

**Why it matters:** Symbolic interfaces are only useful when their meaning is unambiguous and their behavior can be checked. This project explores explicit capability metadata and validation rather than treating an emoji as executable behavior by itself.

**Try the validator:**
```sh
python3 tools/validate_registry.py
```
This uses Python's standard library. See the linked specification, registry files, security model, and implementation-status document for scope and limitations.

**Current status:** The repository documents a design draft and includes a standalone C11 capability-dispatch prototype, an offline Python workflow demo, and a benchmark harness. It is not yet a complete integrated VM/parser. Planned capabilities are not automatically implemented capabilities.

**How to evaluate it:** Run the validator and project tests available in the repository. Report the environment and exact commands used. Treat performance or LLM-efficiency claims as unverified unless a reproducible benchmark and results are provided.

**Attribution and license:** Copyright notice and GPL-3.0-or-later terms are in this repository's LICENSE and documentation.
