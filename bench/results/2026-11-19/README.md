# Download workflow measurement, 2026-11-19

Historical results for the commit named below. See the
[current measurement guide](../../README.md) for source currentness, dispersion
and comparison limits.

[Raw samples and provenance](raw.json) were measured on clean commit
`0f5eb9a18fd3fccca07324734b927587b69e402a` (branch
`quality/download-benchmark-20261119`, empty `git status`) with the exact pinned
Goose compiler `eadca409f68210893f366e60d0c2f0dc29a339be`
(SHA-256 `3cad45a18356bf97f4732f1da2012252afd77a652932ddb9c91c5551c04904be`).
This evidence-only commit does not change the measured implementation.

Reproduce with:

```sh
make bench GOOSE=/path/to/pinned/goose
```

## What was measured

One sample is one independent OS process invocation of
`examples/download/main.goose`, which calls `artifact::execute` exactly once
against an owned loopback HTTPS fixture. The reported interval runs from
immediately before `Popen` to immediately after `wait()`, so it includes
fork/exec, dynamic linking, the TLS handshake, the complete workflow and process
exit. Fixture startup, certificate generation, metadata signing, temporary
directory creation and all verification are outside the interval.

The workflow covers authenticated metadata read, Ed25519 verification, JSON
parse, staging creation, the HTTPS stream, per-chunk SHA-256 and staging writes,
stream close, digest comparison, `fsync`, file close and the atomic `NoReplace`
rename with parent synchronisation.

## Environment

Intel Core Ultra 7 258V, 8 logical CPUs, no CPU pinning (the measured process
inherits the parent affinity mask `0-7`). Linux `7.2.15-arch1-1` x86-64, glibc
2.44. GCC 16.2.1 20260810 (`/usr/bin/gcc`, SHA-256 `8aac907d6fbf4039…`), flags
`-O2 -UNDEBUG`. libcurl 8.23.0, OpenSSL 4.1.0, libsodium 1.0.22. Measured binary
SHA-256 `84fd7f956c4381a2…`; fixture shim SHA-256 `1028b7d17596e763…`. Full
hashes, the exact build command, every effective compiler invocation and the
compiler wrapper text are in the raw record.

## Observations

Twenty independent processes: 16 successes, 2 digest controls and 2 startup
floors. Sizes were round-robined so drift is spread across workloads. All values
are end-to-end process wall time in milliseconds; outliers are retained.

| Workload | n | Median ms | Range ms |
| --- | ---: | ---: | ---: |
| 64 KiB | 4 | 20.96 | 20.23–23.09 |
| 1 MiB | 8 | 30.59 | 26.64–32.21 |
| 4 MiB | 4 | 58.07 | 51.74–59.63 |
| startup floor (1 MiB, rejected at `Signature`) | 2 | — | 9.67–12.63 |
| digest control (1 MiB, rejected at `DigestMismatch`) | 2 | — | 30.69–33.50 |

Every success published with `stage=None`, `publication=Applied`,
`received_bytes == written_bytes == size`, no staging residue and a published
file whose size and SHA-256 match the fixture.

## What these numbers do and do not show

The startup floor is roughly half of the 64 KiB sample, so at these sizes the
sample is dominated by process startup and the TLS handshake. **No library
throughput is isolated and no bytes-per-second figure is claimed.** Separating
phases would require instrumenting the production API, which is out of scope.

The digest control is the work proof. It transfers, hashes and writes the whole
1 MiB body and only then fails at `DigestMismatch`; its timings (30.69, 33.50 ms)
sit inside the 1 MiB success range, as they must if the timed path performs the
same real work. The startup floor transfers zero bytes and is correspondingly
cheaper. A folded idle path could not satisfy both assertions.

The difference between the 4 MiB and 64 KiB medians is 37.1 ms for 4,128,768
additional bytes. That is a difference of two end-to-end process medians, not an
isolated library throughput, and it is not a performance claim.

Sampled `VmHWM` was about 15.0–15.2 MiB for successful runs and 6.5–7.7 MiB for
startup floors, so the HTTP/TLS stack accounts for roughly 8 MiB of the resident
high-water mark. This is a polled observation and a lower bound on the true
peak, not a hard memory promise.

## Limits

One host, one toolchain, one bounded fixture set. No Rust or other
implementation is compared, so no improvement ratio exists. Loopback TLS and a
local filesystem do not represent a wide-area network or a real disk. No CPU
pinning, so scheduler migration and frequency scaling are inside every sample.
The measured binary links a fixture shim that only sets `CURLOPT_CAINFO` for the
expected loopback URL, so it is not byte-identical to the production binary and
the shim's cost is inside every sample. CI runs a correctness smoke only; no
timing threshold is asserted anywhere.
