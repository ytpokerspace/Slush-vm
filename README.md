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

## Status

These are working design drafts. Manifest entries are marked planned; that does not mean the parser, native capability, or platform integration already exists. Check implementation and test status before relying on a capability.

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
