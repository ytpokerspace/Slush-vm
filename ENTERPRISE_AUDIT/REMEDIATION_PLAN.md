# Enterprise Audit Remediation — Slush-vm / SHUSHOS

**Owner:** William Gunnell Cox  
**Repository:** ytpokerspace/Slush-vm  
**Status:** Baseline plan committed; remediation evidence not yet established.

## Audit objective

Establish a reproducible, portable C11 implementation with explicit memory ownership, sanitizer coverage, deterministic capability resolution, and a separately validated WebGL2 compute path.

## Existing evidence inspected

- The repository includes a standalone C11 capability-dispatch prototype and generated registry.
- The README states that the design documents are drafts and that the current C slice is not a complete parser/full VM.
- Existing workflows include registry/workflow validation and benchmark-related automation.
- No evidence was established in this inspection that the complete requested cross-platform sanitizer matrix has passed.

## Remediation sequence

### SLUSH-A1 — C11 compiler gate
- Compile the maintained C sources with `-std=c11 -Wall -Wextra -Werror -pedantic`.
- Keep compiler-specific flags isolated by toolchain; do not claim identical warning behavior across GCC, Clang, and MSVC.
- Add a documented MSVC build path and a MinGW path; record compiler versions and exact commands.
- Make ownership and error-return contracts explicit for every allocation and output parameter.

### SLUSH-A2 — Memory-safety gate
- Add sanitizer-enabled test jobs where supported: AddressSanitizer and UndefinedBehaviorSanitizer; use LeakSanitizer where supported by the runtime.
- Run Valgrind on a supported Linux runner as an independent check.
- Exercise normal, invalid-input, allocation-failure, repeated-call, and teardown paths.
- Do not mark a platform passed when its tool is unavailable; report NOT SUPPORTED separately from PASS.

### SLUSH-A3 — VM correctness
- Define parser/runtime boundaries and capability state: planned, implemented, tested.
- Add tests for alias ambiguity, namespace isolation, exact version resolution, permission denial, malformed inputs, and resource exhaustion.
- Add bounded execution fuel and explicit cancellation/error propagation before advertising general-purpose execution.

### SLUSH-A4 — WebGL2 portability
- Keep WebGL2 implementation and evidence separate from the C11 VM gate.
- Test context loss/restoration, shader compile/link failure, precision limits, and CPU fallback.
- Validate numerical output against a reference implementation using declared tolerances.
- Use compensated summation only where the numeric error model warrants it; test adversarial input distributions.

## Acceptance matrix

| Gate | Status | Evidence required |
|---|---|---|
| Strict C11 warning-free build | NOT VERIFIED | Compiler logs and version matrix |
| ASan/UBSan | NOT VERIFIED | CI artifacts on supported runners |
| LSan/Valgrind | NOT VERIFIED | Leak-check logs; platform support stated |
| Windows MSVC/MinGW | NOT VERIFIED | Separate successful build/test logs |
| Mobile WebGL2 | NOT VERIFIED | Device/browser matrix and context-loss tests |
| Full parser/VM integration | INCOMPLETE per current README | Implementation plus end-to-end tests |

## Evidence artifacts

- `evidence/compiler-matrix.md`
- `evidence/sanitizer-results/`
- `evidence/valgrind-summary.txt`
- `evidence/webgl2-device-matrix.md`
- `evidence/runtime-regressions.json`

## Execution constraints

Start with offline builds and tests. Do not run live benchmarks, external submissions, or paid services without separate authorization. This plan does not modify the current license or claim complete VM status.
