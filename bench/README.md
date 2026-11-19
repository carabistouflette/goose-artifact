# Download workflow measurements

These measurements cover one complete `artifact::execute` call through the real
production path: authenticated metadata read, Ed25519 verification, JSON parse,
staging creation, the HTTPS stream, per-chunk SHA-256 and staging writes, stream
close, digest comparison, `fsync`, file close and the atomic `NoReplace` rename
with parent synchronisation. Nothing is mocked and no throughput loop is
substituted for the workflow.

They are ordered raw observations for one host, one toolchain and one bounded
fixture set. They are not a universal performance claim, not a library ranking
and not a bytes-per-second figure.

## Sample unit and time boundary

One sample is one independent OS process invocation of
`examples/download/main.goose`, which calls `artifact::execute` exactly once
against an owned loopback HTTPS fixture.

`t0` is taken immediately before `Popen` of the benchmark binary and `t1`
immediately after `wait()` returns. The interval therefore includes fork/exec,
dynamic linking, the TLS handshake, the complete workflow and process exit. It
excludes fixture server startup, certificate generation, metadata signing,
temporary directory creation and every post-run verification step. The clock is
`CLOCK_MONOTONIC` read in the parent process.

Because the interval is end-to-end process wall time, per-phase costs are not
separated. At the fixture sizes used here the sample is dominated by process
startup and the TLS handshake, so no library throughput is isolated. Separating
phases would require instrumenting the production API, which is out of scope.

## Workload and controls

The payload is `payload[i] = i % 256`, repeating. Default sizes are 64 KiB,
1 MiB and 4 MiB, sampled 4, 8 and 4 times respectively, round-robin across sizes
so drift is spread rather than concentrated in one workload. No A/B comparison
is made, so no alternating implementation order applies.

Two controls make the timed path falsifiable:

- **digest-control** — the metadata signs an all-zero digest. The body is still
  fully transferred, hashed and written, then rejected at `DigestMismatch`. The
  harness asserts `received_bytes == written_bytes == size`, which proves the
  timed path performs the real transfer, hash and write instead of folding to an
  idle path.
- **startup-floor** — the signature covers different bytes, so the run is
  rejected at `Signature` before any network or file mutation. The harness
  asserts zero transferred bytes. This measures the process startup floor and
  shows how much of each sample is fixed cost.

Every sample is verified outside the timing: exit code, `stage`, `publication`,
`received_bytes`, `written_bytes`, absence of staging residue, absence of
`residue_may_remain`, exactly one fixture request, and the published file's size
and SHA-256. A failed verification aborts the run and saves nothing.

The total sample budget is capped at 20 independent processes. The default plan
uses exactly 20: 16 successes, 2 digest controls and 2 startup floors.

## Fixture shim

The measured binary links `bench/transport.c`, which wraps
`curl_multi_add_handle` only to set `CURLOPT_CAINFO` for the single expected
loopback URL. It does not weaken TLS verification: peer and host verification
stay enabled in the library's own stream setup, and any other URL is refused.

This shim is necessary because the library sets no `CURLOPT_CAINFO` and this
libcurl build does not honour `CURL_CA_BUNDLE` or `SSL_CERT_FILE` for the
default trust store. The alternative would be mutating the system trust store.

The shim is linked into the measured process, so its cost (one `getenv`, two
string comparisons and one `curl_easy_setopt` per request) is inside every
sample, and the measured binary is not byte-identical to the production binary.
Both hashes are recorded. Unlike `tests/transport.c`, no fault-injection
wrappers around `write`, `fdatasync`, `fstat`, `close`, `unlinkat` or the root
rename are linked, because those are exactly the filesystem operations being
measured.

## Reproduce

From a clean checkout with the pinned compiler available:

```sh
make bench GOOSE=/path/to/pinned/goose
```

The default output `.build/bench.json` is ignored. For a reviewable record, copy
it to `bench/results/<date>/raw.json` after source edits have settled, and
retain the measured commit. The script refuses to replace an existing output
unless `--force` is passed, and it refuses to save at all if the source or the
measured binary changes during the run.

The record contains the source fingerprint (HEAD, branch, status and per-file
hashes), the pinned Goose revision and binary hash, compiler path/version/binary
hash, flags, the exact build command, every effective compiler invocation, the
compiler wrapper text, backend versions, the measured and shim binary hashes,
CPU model, logical CPUs, affinity mask, platform, kernel, the fixture definition,
the exact sample order and all raw samples.

A dirty measurement is labelled by the recorded `status`; it does not identify an
uncommitted tree as a clean commit.

## Limitations

- One host, one toolchain, one bounded fixture set. No universal claim.
- No Rust or other implementation is compared, so no improvement ratio exists.
- Loopback TLS and a local filesystem do not represent a wide-area network or a
  real disk.
- No CPU pinning: scheduler migration and frequency scaling are inside every
  sample. The measured process inherits the parent affinity mask.
- `peak_rss_kib_sampled` is a polled `VmHWM` observation, a lower bound on the
  true peak, not a hard memory promise.
- CI runs a correctness smoke only. No timing threshold is asserted anywhere.
