# goose-artifact

Bounded authenticated HTTPS staging and checked file publication for
[Goose](https://github.com/aardappel/goose). Apache-2.0, experimental interface.
Initially Linux x86-64/glibc only; no compatibility promise before 1.0.

`execute` authenticates exact metadata bytes, incrementally hashes bounded HTTP
chunks while writing a private staging file, and publishes only after clean
transport completion, digest equality, checked data sync and consumed close.
Callers receive independent publication, cleanup and possible-residue results.
The implementation is extracted from the reviewed goose-crypto streaming example.

## Use

Goose requires dependencies in the application's root source. Declare all five
aliases; the library cannot enforce transitive versions. These are the supported
and tested identities (other selections require caller compatibility validation):

```goose
import artifact from "../goose-artifact"; // local checkout; public pin supplied at publication
import crypto from "carabistouflette/goose-crypto@a4643f62bd5e76b371054c6537a95169a7930101";
import http from "carabistouflette/goose-http@aa915a0b21db1129f85e6e339a6f0171bcac0e77";
import fs from "carabistouflette/goose-fs@cd0bd29c78c435caaebf75bfecd8e3e2083636eb";
import json_codec from "carabistouflette/goose-json@3fa7b5275399641f8069698b6c097ea66cef7929";
```

Construct an `artifact::Request` with `metadata_path`, `signature_hex`,
`trusted_key_hex`, independently authorized `expected_url`, `private_parent`,
`staging_leaf`, `final_leaf` and `byte_limit`. All byte views remain valid and
unchanged for the entire call. No input references survive the call.

```goose
let result = artifact::execute(request);
if result.stage == artifact::Stage.None {
    assert(result.publication == artifact::Publication.Applied);
}
```

An overload accepts a compile-time function returning i64, polled synchronously:

```goose
fn poll_cancel() -> i64 { return 0; } // application-owned cancellation state
let result = artifact::execute(request, poll_cancel);
```

Zero means continue; any nonzero value is an opaque cancellation reason retained
in `Result.cancellation_reason` when cancellation is observed. The default has no
polling behavior. Polls must be quick, nonblocking, and must not mutate borrowed
inputs, destination names or owned resources. Prefer a named function. Normal
return is required to receive a Result. A nonlocal block return runs resource
cleanup through Goose defer but returns no Result; cleanup errors then cannot be
inspected. Exit/abort/crash/SIGKILL cleanup is not guaranteed. No user callback
crosses native FFI, no callback is stored, and the library installs no signals.

## Inputs and trust

Metadata is at most 16 KiB and has exactly `url` and `sha256` fields. Sign its exact
bytes, including encoding, whitespace and field order. The signature is 128 hex
characters, key 64 hex and digest 64 hex. Strict hex rejects malformed lengths or
characters. Invalid signatures and backend verification errors have distinct
stages. Signature verification precedes JSON parsing, mutation and networking.
The signed URL must equal the independently authorized HTTPS URL exactly.

The caller establishes key/expected-digest trust and owns key rotation, protocol
context, expiry, freshness, rollback prevention, origin/address policy and
installation authorization. A digest or key downloaded alongside the artifact
does not establish its trust. This module neither extracts nor executes payloads.

Metadata and parent use strict absolute paths without symlink components, `.` or
`..`, or repeated separators. The parent has no group/other permissions and no
other writers throughout the call, including same-UID writers. Leaves are
filesystem-distinct and nonaliasing, lower-case ASCII matching
`[a-z0-9][a-z0-9._-]*`, at most 255 bytes and no trailing dot. Exotic aliasing
filesystems and hostile same-UID namespace changes violate the contract.

## Publication and errors

Only `Stage.None` means a completed successful call. `Result` preserves the primary
stage/errno/HTTP status, cancellation reason, publication, parent-sync state,
rename cleanup error, separate HTTP/File/staging/Root/Context cleanup statuses,
possible staging residue, received and written byte counts. HTTP and FS status
types are exposed losslessly; their supported contracts are part of this
experimental interface. `describe(result)` formats fixed labels/numbers without
printing, URLs, names, keys or signatures. Helper functions/storage are internal.

| Publication | Caller interpretation |
| --- | --- |
| NotAttempted | Publication syscall did not run; owned staging cleanup is attempted |
| Applied | Bytes were published; a later error does not roll them back |
| Unknown | Publication may have happened; never retry, roll back or speculatively unlink |

Initial absence is checked before CreateNew; a failed exclusive open can still
create an owned entry without a File token. Preexisting collisions are preserved.
Close consumes the File even on error and is not retried. The last cancellation
poll before rename is the commitment point; cancellation afterward cannot revoke
an attempted publication. NoReplace and checked parent synchronization preserve
outcomes independently from errors. A nonzero error can coexist with Applied.
Sync reports filesystem/kernel promises, not universal crash durability.

Memory scales with fixed metadata/header/chunk buffers and backend behavior,
not the artifact total. Body cap is 0..1 GiB, chunks 64 KiB, metadata/headers 16 KiB.
HTTP uses verified TLS, HTTP/1.1, identity encoding, no redirects/proxies/credentials.
Clean terminal HTTP200 and digest equality are both required; matching a truncated
prefix's digest is insufficient. Transfer budget 300 s, connect 10 s and pump 20 ms
are not hard wall deadlines: DNS cleanup and filesystem writes/sync/close can block.

## Development

Pinned Goose compiler (`GOOSE_REVISION`), CMake >=3.27, C/C++20 toolchain, Make,
Python >=3.11 with cryptography, pkg-config, libsodium >=1.0.18, libcurl >=7.85
with TLS/asynchronous DNS and simdjson development packages are needed. Ubuntu:
`build-essential cmake ninja-build python3 python3-cryptography pkg-config
libsodium-dev libcurl4-openssl-dev libsimdjson-dev clang git`.

```sh
make setup
make format check test
make sanitize SANITIZER_CC=gcc
make sanitize SANITIZER_CC=clang
```

Select an existing matching compiler with `GOOSE=/absolute/path/to/goose`.
The [CLI example](examples/download/README.md) owns signal handlers and exit
policy. See [design](docs/DESIGN.md), [contributing](CONTRIBUTING.md),
[security](SECURITY.md) and [notices](THIRD_PARTY_NOTICES.md).
