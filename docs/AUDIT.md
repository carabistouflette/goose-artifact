# Documentation and source check

## Versions and examples

The released alpha.1 and published main used for this audit are both
`c2d190b613c541a5dba839ce380de8b111c9ab0c`. This documentation change moves no
tag and changes no implementation, example, test, compiler or dependency pin.
All five root imports in the README are the supported tested combination.

README, API/design, download guide, setup/contributing, security, notices,
changelog and validation pages were checked. Detailed historical evidence is
linked separately from the quickstart. The quickstart explicitly tests argument
rejection without network/file I/O; the CLI guide's existing integration command
is the complete signed loopback download demonstration. Production commands
require caller-provided trusted signatures/keys/URLs, not the public fixture key.

The exact README public-import smoke ran successfully with the pinned Goose
compiler and returned InvalidInput/NotAttempted as asserted. `make check test`
passed API JIT/debug/native execution, signal tests and all 68 GCC loopback
integration scenarios. This was one bounded ordinary validation job, not a
measurement or fuzz campaign.

## Existing validation matches the implementation

The historical 68-case record measured clean
`60047bda596d457eb87f73e51e68dea96bc5f0ec`. All 18 non-Markdown files in
that record match the published c2d190b Git objects and current checkout byte
for byte, including artifact.goose, CLI/signals, integration fixtures, build/test
scripts and compiler pin. Root imports still select the recorded crypto/HTTP/FS/
JSON source objects. The raw records retain their original source identities.

Check executable sources from a full clone:

```sh
git diff --exit-code 60047bda596d457eb87f73e51e68dea96bc5f0ec HEAD --   artifact.goose GOOSE_REVISION Makefile scripts tests/api.goose   tests/integration.py tests/transport.c tests/faults.c examples/download/main.goose   examples/download/signals
```

See [VALIDATION.md](VALIDATION.md) for GCC/Clang release/sanitizer results,
68 public/TLS scenarios, fault/cleanup checks and their limits. Backend versions
were recorded; matching version strings do not prove identical binaries.

## Benchmark: N/A

This library composes authentication, HTTP, file writes, sync and rename; it is
not a new cryptographic, network or filesystem algorithm. There is no useful
claimed throughput advantage or comparative timing table to refresh. Application
throughput/latency depends on its origin, transport and filesystem. Manufacturing
a local speed ranking would not answer that question.

Existing child RSS samples for increasing transfer totals are historical
correctness/resource observations. They are not a hard process-memory ceiling,
allocator proof or current-host performance advertisement. The implementation
streams 64 KiB chunks rather than buffering the whole artifact; backend/kernel
buffers and cleanup latency still depend on the deployed environment. No new
measurement or raw-artifact replacement was needed for these documentation claims.
