# goose-artifact

Verify signed metadata, download an HTTPS file into private staging, then publish
it without overwriting an existing file. The library reports publication and
cleanup separately, including uncertain rename outcomes. Apache-2.0.

Experimental synchronous API, tested on Linux x86-64/glibc. The released
[v0.1.0-alpha.1](https://github.com/carabistouflette/goose-artifact/releases/tag/v0.1.0-alpha.1)
is `c2d190b613c541a5dba839ce380de8b111c9ab0c`. Main adds documentation;
[the source check](docs/AUDIT.md) identifies unchanged implementation/dependencies.

## Quickstart

Use the pinned Goose compiler and native dependencies listed in
[CONTRIBUTING.md](CONTRIBUTING.md). Save this as `main.goose`, then run
`goose run main.goose`. At runtime this smoke checks argument rejection without
reading artifact files or making a network request. Building may fetch the pinned
packages. A successful signed download is shown
in the [local CLI demonstration](examples/download/README.md).

All five package aliases belong in the application's root source. Goose does not
enforce transitive versions: these exact versions are the tested combination.

```goose
import artifact from "carabistouflette/goose-artifact@c2d190b613c541a5dba839ce380de8b111c9ab0c";
import crypto from "carabistouflette/goose-crypto@a4643f62bd5e76b371054c6537a95169a7930101";
import http from "carabistouflette/goose-http@aa915a0b21db1129f85e6e339a6f0171bcac0e77";
import fs from "carabistouflette/goose-fs@cd0bd29c78c435caaebf75bfecd8e3e2083636eb";
import json_codec from "carabistouflette/goose-json@3fa7b5275399641f8069698b6c097ea66cef7929";
import std;
fn main() {
    let request = artifact::Request {
        metadata_path: "", signature_hex: "", trusted_key_hex: "",
        expected_url: "", private_parent: "", staging_leaf: "",
        final_leaf: "", byte_limit: 0,
    };
    let result = artifact::execute(request);
    assert(result.stage == artifact::Stage.InvalidInput);
    assert(result.publication == artifact::Publication.NotAttempted);
    print(artifact::describe(result));
}
```

For real requests, keep every borrowed input valid and unchanged for the entire
call. Supply an independently trusted key, signed metadata, authorized URL,
private parent and distinct staging/final leaves. See [DESIGN.md](docs/DESIGN.md)
for fields, cancellation and the complete input contract.

## What the call does

1. Read at most 16 KiB of metadata; verify its exact bytes before JSON parsing,
   network setup or filesystem mutation. Metadata has exactly `url` and `sha256`.
2. Require its signed URL to equal the independently authorized HTTPS URL.
   Strict hex sizes are 128 characters for signatures and 64 for keys/digests.
3. Stream bounded chunks into a new private staging file while hashing them.
   Require clean terminal HTTP 200 and the signed digest, not an early status
   or a matching digest for a truncated prefix.
4. Check file-data sync and close, then attempt a no-replace rename with parent
   synchronization. Return primary status, publication, cleanup and possible residue.

The caller supplies key/digest trust, protocol context, encoding, freshness,
rollback prevention, origin/address policy and installation authorization.
A key downloaded alongside the file does not establish trust. This module does
not extract, install or execute the payload.

## Filesystem and outcome requirements

Metadata/parent paths are strict absolute paths without symlink components,
`.`/`..` or repeated separators. The parent has no group/other permissions and
no other writers during the call, including the same UID. Names must be distinct
nonaliasing filesystem lookups: lower-case ASCII `[a-z0-9][a-z0-9._-]*`, at most
255 bytes, no trailing dot. These conditions do not defend against a same-UID
process that violates them or exotic name-aliasing filesystems.

Only `Stage.None` means complete success. Inspect publication even on error:

| Publication | Meaning |
| --- | --- |
| `NotAttempted` | Rename did not run; owned staging cleanup is attempted |
| `Applied` | File was published; later errors do not undo it |
| `Unknown` | Publication may have happened; do not retry, roll back or speculatively unlink |

Preexisting entries are preserved. A failed exclusive open can still create an
owned staging entry without returning a File. Close consumes its File even on
error and is not retried. Cleanup errors, parent-sync state and possible residue
remain separate from the primary error. Sync is not a universal crash-durability
promise. `describe(result)` formats labels/numbers without echoing URLs, keys,
signatures or filenames.

## Limits and cancellation

Body limit: 0..1 GiB; chunks: 64 KiB; metadata/headers: 16 KiB. HTTP uses verified
TLS, identity encoding, HTTP/1.1, no redirects/proxies/credentials. Transfer 300 s,
connect 10 s and pump 20 ms are budgets, not hard wall deadlines: DNS cleanup and
filesystem calls may wait longer. No complete artifact buffer is allocated;
backend buffers and runtime behavior still prevent a hard allocator/RSS claim.

`execute(request)` does not poll cancellation. An overload accepts a named
compile-time function returning i64: zero continues; nonzero is an opaque reason
retained when cancellation is observed. Polls must be quick/nonblocking and must
not mutate inputs, names or resources. No callback is stored or crosses native FFI;
the library installs no signals. Normal return is required to receive a Result.
A nonlocal block return runs defer cleanup but returns no Result/cleanup errors.
Exit/abort/crash/SIGKILL cleanup is not guaranteed. The final poll before rename is
the commitment point; cancellation afterward cannot revoke an attempted rename.

[The CLI](examples/download/README.md) supplies SIGINT/SIGTERM and exit codes.
[Validation](docs/VALIDATION.md) records correctness/resource checks, not a speed
claim. [AUDIT.md](docs/AUDIT.md) explains why a throughput benchmark is N/A.
See also [security](SECURITY.md) and [notices](THIRD_PARTY_NOTICES.md).
