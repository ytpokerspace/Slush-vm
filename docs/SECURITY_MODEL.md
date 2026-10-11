# Security and Execution Model

**Status:** proposed policy baseline, not proof of an existing OS sandbox.

## Dispatch pipeline

resolve → validate → authorize → sandbox/limits → execute → audit.

Every invocation must pass through this pipeline. Registry metadata and grammar constraints do not create a security boundary.

## Permissions

Use granular permissions such as fs.read/write/delete; process.spawn/signal/trace; net.dns/connect/listen/configure; registry.read/write; storage.read/admin; package.install; build.execute; graphics.render; audio.output/capture; kubernetes.read/write; cloud.modify; diagnostics.trace/dump; audit.write.

Read must never imply write. Check authorization at invocation time and scope it to the target.

## Execution barriers

Recommended controls: executable allowlist with stable identity; allowed working directories and filesystem roots; no shell by default; controlled environment; CPU, memory, process-count, output-file, and wall-clock limits; explicit network allowlist/listener policy; per-capability permissions; audit for allow/deny and outcome.

Illustrative limits could be CPU 2 seconds, address space 256 MiB, 16 processes, file size 1 MiB, wall timeout 5 seconds. Tune for the workload. OS-specific resource limits alone are not a complete sandbox; use OS isolation and handle-relative path operations where available.

## High-impact operations

Require explicit scope, authorization, confirmation, and audit for partition changes, filesystem creation/repair, boot configuration, power operations, sensitive Registry writes, package installation, cloud mutation, and privileged container execution. Prefer inspection before mutation.

## Secrets and telemetry

Do not log credentials, tokens, raw secrets, or full environment dumps by default. Registry exports, ETW events, crash dumps, and process traces may expose sensitive data; control access, retention, size, and redaction.

## Failure policy

Default deny unknown, ambiguous, unsupported, unauthorized, or incompatible references. Never silently fall back. Report a stable error code and preserve platform-specific details.
