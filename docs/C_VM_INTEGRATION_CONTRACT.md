# C VM integration contract

## Repository inspection result

The current `main` tree contains the SHUSHOS specification and JSON registries,
but no C source file or checked-in VM implementation. Therefore a safe C dispatch
patch cannot be made against the current repository state without inventing the
missing runtime API. This document specifies the integration boundary for when
the VM source is added.

## Required dispatch sequence

1. Parser produces a semantic reference: symbol, namespace, canonical ID, exact
   version, and typed arguments.
2. Resolver consults the vocabulary and explicit alias manifest. Zero matches
   returns `E_ALIAS_NOT_FOUND`; multiple matches returns `E_ALIAS_AMBIGUOUS`.
3. Registry lookup requires exact ID and version; no best-effort version fallback.
4. Capability status must be `tested`; all required permissions must be granted.
5. Validate argument count and types before entering native code.
6. Dispatch to a handler through a stable enum/table, not by executing a string
   or evaluating generated source.
7. Validate result shape and types, then emit an audit trace with capability ID,
   version, and status.

## Suggested C interface (design only)

```c
typedef enum {
    SHUSH_OK = 0,
    SHUSH_E_ALIAS_NOT_FOUND,
    SHUSH_E_ALIAS_AMBIGUOUS,
    SHUSH_E_CAPABILITY_NOT_FOUND,
    SHUSH_E_CAPABILITY_UNVERIFIED,
    SHUSH_E_PERMISSION_DENIED,
    SHUSH_E_INPUT_TYPE,
    SHUSH_E_OUTPUT_TYPE
} ShushStatus;

/* Resolve exact identity first; dispatch only after policy and type checks. */
ShushStatus shush_resolve_and_dispatch(
    const ShushRegistry *registry,
    const ShushPolicy *policy,
    const ShushReference *reference,
    const ShushValue *args,
    size_t arg_count,
    ShushValue *out
);
```

This is an interface sketch, not compile-ready code: the referenced types must be
defined against the actual VM's value model, memory management, error model, and
native-call convention. The first C integration change should be made only after
the actual C source is committed and its build/test command is known.
