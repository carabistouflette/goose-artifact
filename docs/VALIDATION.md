# Local validation — 2026-11-05

Historical validation record. [AUDIT.md](AUDIT.md) checks current source
identity and examples; the records below keep their original identities.


Validated library, CLI and harness:
`60047bda596d457eb87f73e51e68dea96bc5f0ec`, clean working tree. This record,
raw evidence and a README wording correction were added afterward without
changing executable sources. Hosted CI independently repeats the checks.

All 68 real loopback TLS/public-interface scenarios passed in each configuration:

- [GCC release](../tests/results/2026-11-05/release.json)
- [GCC ASan/UBSan](../tests/results/2026-11-05/gcc-sanitize.json)
- [Clang ASan/UBSan](../tests/results/2026-11-05/clang-sanitize.json)

Each record contains complete repository source hashes, source commit/status,
declared full-SHA dependency identities, Goose/compiler binary hashes and versions,
backend version metadata, actual per-invocation compiler commands, binary hashes
and case outcomes. Inputs and binaries are checked again after execution.
Source hashes were independently compared with the recorded Git objects. Compiler
transcripts are fresh per invocation; cached objects can omit compilation commands.
Backend version strings do not detect same-version library replacement.

Environment: Linux x86-64/glibc, GCC 16.2.1, Clang 23.1.4, libsodium 1.0.22 and
libcurl 8.23.0. Goose revision `eadca409f68210893f366e60d0c2f0dc29a339be`.
Supported dependencies are declared by the root program: crypto a4643f62,
HTTP aa915a0b, FS cd0bd29c and JSON 3fa7b527; raw records contain full hashes.
Local affinity excluded CPU3 during another owner's profiles. No new benchmark
campaign or performance ranking; RSS samples are observations, not thresholds.

The original 61 cases exercise authenticated input rejection, large/empty/tiny
transfers, production TLS rejection, body/header limits, matching signed digest
of truncated/abortive-reset prefixes, real signals, short/zero/ENOSPC writes,
failed creation inspection, sync/consumed-close/cleanup errors, collisions and
NotAttempted/Applied/Unknown publication outcomes. EOF and abortive-reset barriers
wait for specific staged byte counts, preventing an early failure from standing
in for correct terminal-transfer gating. Exact exits/stages/requests and bytes
are required; crashes cannot count as expected rejection.

Seven new cases call the imported module without the CLI's signal package:
default success, named continuation, named cancellation with reason -911,
block cancellation after staging/body with reason -73, and nonlocal escapes
after staging/body writes. The escaping caller survives and verifies descriptor
and namespace cleanup. Normal calls inspect cleanup fields. Digest/write failure
loops also repeat 20 times after warmup in a surviving process. The void helper's
defer completes before the outer Result snapshot, preserving cleanup errors.

[Release/interface log](../tests/results/2026-11-05/release.log) covers check,
JIT, debug JIT and native execution for default/opaque cancellation. Full TLS and
nonlocal-escape scenarios are compiled native tests. CLI signal guard tests pass
in release and both sanitizers. Sanitizers instrument generated Goose/runtime C
and native C/C++ adapters; explicit C++ vptr and mixed C-driver final linkage have
a preflight. The production TLS binary is separately release-built with no CA
shim. System libraries are not sanitizer-instrumented.

Independent interface/security design reviews preceded extraction. A later
implementation review and independent test-quality/performance review found no
remaining blocker after fixes. Reviews corrected stale compiler-documentation
assumptions about defer, caller-declared dependency wording and mutating CI
formatting. CI now checks formatting/fingerprints without repairing the source.

Finite Linux regression coverage does not certify a complete updater or establish
crash cleanup, hard deadlines or universal filesystem durability. Caller trust,
freshness, rollback and installation policy and private/no-other-writers/nonaliasing
namespace preconditions remain explicit. Existing crypto release and parent pins
are unchanged.

## Reproduce the current checks

Install [development prerequisites](../CONTRIBUTING.md), then:

```sh
make setup
make check
make test
make sanitize SANITIZER_CC=gcc
make sanitize SANITIZER_CC=clang
```

An existing matching compiler may be selected with `GOOSE=/path/to/goose`. New
records describe the checked-out source, not the historical commit above.
