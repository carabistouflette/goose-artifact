# Artifact API contract

## Request and result

`artifact::execute(request) -> Result` is synchronous. Request fields are
`metadata_path`, `signature_hex`, `trusted_key_hex`, independently authorized
`expected_url`, `private_parent`, `staging_leaf`, `final_leaf` and `byte_limit`.
Borrowed byte views must remain valid and unchanged through the call; none are
retained afterward. Use only the public Request/Result/Stage/Publication and
execute/describe interface; implementation helpers/storage are internal.

Goose requires root-source imports for artifact, crypto, http, fs and json_codec.
[README.md](../README.md) pins the tested combination. Other versions require
caller compatibility testing; the library cannot enforce root-selected versions.

Result keeps primary stage/errno/HTTP status, cancellation reason, publication,
parent-sync state, rename-cleanup error, separate HTTP/File/staging/Root/Context
cleanup statuses, received/written counts and possible staging residue. HTTP/FS
status types are exposed without discarding their fields. Only Stage.None means
complete success. `describe` returns fixed labels/numbers, not untrusted names,
URLs, keys or signatures. A failed call can still have Publication.Applied.

## Authentication and private staging

Metadata is a regular file capped at 16 KiB, with exactly `url` and `sha256`.
Authenticate original bytes before parse, network or mutation. Signature hex is
128 characters; keys and digests use 64. Malformed sizes/characters are rejected.
Invalid signatures and verification backend failure have different stages.
The signed URL must equal an independently authorized HTTPS URL byte for byte.
Caller policy supplies key/expected-digest trust, serialization/encoding, protocol
context, expiry, freshness, rollback and installation authorization.

Use strict absolute metadata/parent paths with no symlink components, repeated
separators or dot components. The parent has no group/other permission bits or
other writers for the full call, including same UID. Staging/final leaves must be
filesystem-distinct nonaliasing lower-case ASCII names matching
`[a-z0-9][a-z0-9._-]*`, at most 255 bytes and no trailing dot. Exotic aliasing or
hostile same-UID namespace changes violate the contract.

Check staging/final absence before exclusive 0600 creation. A failed open can
create an entry without a File token; possible ownership is tracked from the
absence check/creation attempt. Never remove a preexisting collision. Stream
64 KiB chunks, enforce a separate cumulative 0..1 GiB limit, require complete
writes no larger than FS's 1 MiB maximum. Require clean terminal HTTP 200 and the
signed digest before publication; a matching truncated-prefix digest is not enough.

## Publication and cleanup

Check data sync and close before NoReplace rename with parent synchronization.
Close consumes a File even when it fails and is never retried. Preserve independent
NotAttempted/Applied/Unknown outcomes: Unknown is never retried, rolled back or
speculatively cleaned; Applied survives late errors. NotAttempted allows cleanup
of owned staging only. Cleanup errors and possible residue are reported separately.

Cleanup runs before a normal Result is returned. A nonlocal block callback return
also runs Goose defer cleanup, but no Result is returned and its cleanup errors
cannot be inspected. Exit/abort/crash/SIGKILL cannot guarantee cleanup.

## Cancellation and budgets

The default execute has no polling. `artifact::execute(request, poll_cancel)`
takes a named compile-time function returning i64. Zero continues; nonzero requests cancellation with an opaque caller
reason. Polls are synchronous at workflow checkpoints. They must return quickly,
not block, mutate inputs/destination names or interfere with owned resources.
Prefer a named function; no callback is stored or crosses native FFI. The library
has no signal handlers, printing or exit policy. The CLI owns those decisions.

The final poll before rename is the publication commitment point. A later signal
cannot guarantee final absence or undo an attempted publication. Metadata/headers
are 16 KiB, chunks 64 KiB, body 0..1 GiB; HTTP transfer 300 s / connect 10 s / pump 20 ms
budgets do not bound DNS cleanup or filesystem latency. No universal durability,
crash cleanup or allocator/RSS guarantee is made.

See [validation](VALIDATION.md) for public API, real TLS, failure and cleanup
checks, and [AUDIT.md](AUDIT.md) for source identity and runnable examples.
