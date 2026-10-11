# SHUSHOS Language and VM Specification

**Status:** working design draft. The documents describe intended semantics, not a claim that every feature is implemented.

## Goal

SHUSH is an emoji-native surface language. SHUSHOS is the proposed runtime/control plane for resolving compact semantic references to reusable, typed, versioned capabilities. The hypothesis is that verified references reduce generated tokens while maintaining or improving correctness; this must be measured rather than assumed.

## Execution architecture

1. Parse source under a versioned grammar.
2. Build and verify AST/bytecode.
3. Resolve canonical capability IDs and exact versions.
4. Validate typed inputs and outputs.
5. Authorize every invocation.
6. Execute in a sandbox with resource limits.
7. Audit the decision/outcome and emit diagnostics.

Unknown, ambiguous, incompatible, unauthorized, and unavailable references must fail explicitly. Never silently fall back to an incompatible implementation.

## Syntax and value model

The proposed vocabulary is in [registry/vocabulary.json](../registry/vocabulary.json). It is not proof that every symbol is implemented in the parser. Several emoji are overloaded; grammar context or explicit canonical IDs are required.

Proposed value types: NUM, STR, BOOL, NIL, LIST, MAP, FUNCTION, NATIVE. Specify integer/float representation, overflow, string encoding, truthiness, equality, map key/hash rules, mutation behavior, scope, and shadowing before declaring the language stable.

Proposed precedence, highest to lowest: call/index/grouping; unary NOT/negation; multiply/divide/modulo; add/subtract; ordered comparisons; equality; AND; OR; ternary. Specify short-circuiting, division by zero, type mismatch, and overflow.

## Bytecode and VM

Candidate opcodes: CONST TRUE FALSE NIL LLOC SLOC LGLB SGLB POP DUP ADD SUB MUL DIV MOD NEG NOT EQ NEQ LT LE GT GE PRINT JMP JIF CALL RET MKLIST INDEX HALT.

Define every opcode's operands, stack effects, operand types, error behavior, constant-pool encoding, jump boundaries, calling convention, and return behavior. A verifier should reject unknown opcodes, malformed operands, invalid jumps, stack underflow, inconsistent stack depths at control-flow merges, and invalid calls/returns.

Maps need an explicit construction/access strategy, such as MKMAP plus map operations or registered native functions. GC roots include operand stack, locals, globals, frames, closures, and temporary native roots. Mark objects visited before recursively tracing children to safely handle cyclic graphs.

## Capability registry

See [registry/capabilities.json](../registry/capabilities.json). Every capability has a canonical ID/version, typed inputs/outputs, implementation reference, permissions, supported platforms, sandbox requirements, lifecycle status, and test status. Lifecycle values are planned, implemented, tested, deprecated, unavailable. Do not mark something implemented or tested until code and tests prove it.

## Diagnostics and platform coverage

See [ERRORS_AND_DIAGNOSTICS.md](ERRORS_AND_DIAGNOSTICS.md) and [PLATFORM_REGISTRIES.md](PLATFORM_REGISTRIES.md). Platform-specific terms must not imply portability. Unsupported features must fail clearly instead of silently switching backends.

## Security

See [SECURITY_MODEL.md](SECURITY_MODEL.md). The registry alone is not a security boundary; enforce permissions at dispatch time and OS-level constraints for filesystem, process, network, storage, Registry, cloud, and device operations.

## Validate

Run:

~~~sh
python3 tools/validate_registry.py
~~~

The validator checks required fields and duplicate canonical IDs and reports reused emoji aliases. A clean manifest is necessary but not sufficient for runtime correctness.

## Evaluation plan

Compare A: ordinary code generation; B: emoji-native generation without reusable references; C: emoji-native generation with exact semantic references and verified components. Use the same tasks/environment and measure token usage, first-pass correctness, execution time, resolver accuracy, and failure classification. Publish tasks, sample size, raw outcomes, and uncertainty; do not claim improvements before measurement.
