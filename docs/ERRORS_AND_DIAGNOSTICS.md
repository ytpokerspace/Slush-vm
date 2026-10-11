# Errors, Recovery, and Diagnostics

**Status:** design draft.

## Structured diagnostic schema

~~~json
{
  "schema_version": "1.0.0",
  "event": "runtime.error",
  "severity": "error",
  "code": "E_TYPE_MISMATCH",
  "message": "Expected NUM, received STR",
  "span": {
    "source": "main.shush",
    "start_line": 12,
    "start_column": 8,
    "end_line": 12,
    "end_column": 17
  },
  "stage": "vm",
  "recoverable": true,
  "status": "failed"
}
~~~

Fields: schema_version, event, severity, stable code, message, optional source span, stage, recoverability, and operation status. Define a single line/column or byte-offset convention.

## Vocabulary

| Alias | Canonical ID | Rule |
|---|---|---|
| ⚠ | diagnostics.warning | Nonfatal report; no automatic termination |
| 🆘 | diagnostics.fatal | Enter configured fatal path |
| 🧾 | diagnostics.record | Structured event, not just free text |
| 📍 | diagnostics.span | Consistent source/execution location |
| 🆔 | diagnostics.error_code | Stable machine-readable identifier |
| 🧯 | runtime.error.recover | Catch only documented recoverable failures |
| 🩹 | runtime.error.handler | Receive typed error object |
| 🅷🆁 | windows.error.hresult | HRESULT domain |
| 🅽🆃 | windows.error.ntstatus | NTSTATUS domain |
| 🆆32 | windows.error.win32 | Win32 error domain |
| 🅴🆃 | windows.diagnostics.etw | Windows event tracing |
| 📄 | diagnostics.crash_dump | Crash dump artifact |

## Recovery semantics

Separate describing a failure from deciding what happens next. Handlers must not swallow fatal VM invariants, authorization failures, or sandbox violations by default. Mutations may require rollback or termination if they fail partway through.

Suggested codes: E_SYNTAX, E_TYPE_MISMATCH, E_DIV_ZERO, E_CAPABILITY_NOT_FOUND, E_CAPABILITY_INCOMPATIBLE, E_ALIAS_AMBIGUOUS, E_PERMISSION_DENIED, E_SANDBOX_DENIED, E_RESOURCE_LIMIT, E_TIMEOUT, E_PLATFORM_UNAVAILABLE, E_NATIVE_FAILURE, E_INTERNAL_INVARIANT.

## Windows error domains

HRESULT, NTSTATUS, and Win32 errors are not interchangeable. Preserve platform, domain, and native_code when wrapping an OS failure. Add a generic SHUSH classification without discarding the original code. Win32 error 5 is ERROR_ACCESS_DENIED.

## ETW and crash dumps

ETW is optional and permission-controlled. Crash dumps may contain sensitive memory; apply explicit size limits, access controls, storage location, retention, and cleanup. Core structured errors must remain useful when tracing or dump generation is unavailable.
