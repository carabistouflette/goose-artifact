# Download workflow measurements

The benchmark calls the real `artifact::execute` through the example CLI against
an owned Python HTTPS fixture on loopback. It covers authenticated metadata,
staging, transport, SHA-256, writes, synchronization and atomic publication.
The measured binary links a CA-trust fixture shim and is not the production
binary. This is a bounded process-workflow baseline, not isolated library
throughput, a comparison with Rust, a speedup or a SOTA claim.

## Sampling and controls

One sample is one independent process. The interval starts before `Popen` and
ends after the parent observes and reaps termination. It includes parent
polling/RSS observation overhead, process startup, the Python producer, TLS,
filesystem work and exit. Output verification and file hashing happen afterward.
This differs from the historical schema-1 interval, which also included pipe
collection before taking the end timestamp. Neither interval isolates phases.

Default payloads are 64 KiB, 1 MiB and 4 MiB (4/8/4 samples), followed by two
full-transfer digest-mismatch controls and two pre-network signature-refusal
controls. There are no discarded warmups. Round-robin ordering interleaves only
the first common repetitions; the extra 1 MiB repetitions and controls form a
tail. Cold/cache, producer and host scheduling effects are retained. No causal
TLS or memory attribution follows from comparing these different workflows.

Every successful sample verifies publication, file size/digest, received and
written counts, staging absence, no residue and exactly one fixture request.
Digest controls verify full transfer/write before rejection; signature controls
verify zero transfer and no publication. These checks establish work, not timing
accuracy or comparative performance. CI runs a correctness smoke, never a timing
threshold.

## Bounds, retention and replay

Sizes must be distinct and in 1..4 MiB, counts positive, and each control kind
must have at least one sample. At most 20 processes run. Each measured child
has a 40-second wall deadline; failure or interruption kills its owned process
group and reaps the leader. Diagnostics have a checked 64 KiB budget (polling
can overshoot it); this is not a hard disk/memory quota. Builds have a 300-second
timeout. Callers serialize heavy work with the shared campaign lock.

Every invocation reserves a fresh `<output>.evidence` directory, retaining
build commands, per-sample command/stdout/stderr/status and an fsynced JSONL
journal. Each verified sample is journaled before proceeding. Failures retain
earlier samples and failure details, rather than producing a successful report.
Existing output or evidence paths are refused; there is no overwrite switch.
Final successful reports are created exclusively. A crash during final write can
leave a partial report; the journal remains separate.

Compiler, source and measured binary identities, resolved shared-library paths
and hashes, selected loader/locale environment, inherited CPU affinity and raw
ordered observations are retained. Shared-library drift rejects success. This
is attribution evidence, not a reproducible-build or full-environment guarantee.
The shim changes only the CA used for the expected localhost URL; the pinned
HTTP dependency keeps peer/hostname verification enabled. No system trust-store
change or production transport substitution is made.

```sh
make bench GOOSE=/path/to/pinned/goose
make bench-smoke GOOSE=/path/to/pinned/goose
```

`bench` refuses a second `.build/bench.json`; select a fresh output with
`python3 bench/measure.py --goose /path/to/pinned/goose --output /fresh/path.json`.
`bench-smoke` reserves a fresh ignored directory each time. Measurements and
failure evidence remain local until explicitly archived; never commit fixture
private keys, executables, caches or generated compiler output.

## Historical baseline

[The original record](results/2026-11-19/raw.json) remains byte-identical to the
clean `0f5eb9a` invocation. Its schema predates the deadline/journal fixes and
resolved-library capture; its source snapshot and observed values are retained,
not retroactively upgraded. [The corrected interpretation](results/2026-11-19/README.md)
records these limits. No replacement performance campaign is claimed.
