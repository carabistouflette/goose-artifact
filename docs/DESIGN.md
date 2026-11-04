# Artifact library extraction contract

Source: goose-crypto b0deb95f6e7fe82aa1e38fad8ca24d69c6a31c7d,
examples/download. Preserve authentication ordering and resource/publication
semantics while extracting a reusable synchronous module.

## Interface

`artifact::execute(request) -> Result` performs no implicit cancellation polling.
An overload accepts a compile-time cancellation function returning i64: zero
continues, nonzero requests cancellation with an opaque caller reason. Polls are
synchronous and bounded by the existing workflow checkpoints. No callbacks cross
native FFI. No process-global signal policy, printing or exit in the library.
The CLI example owns SIGINT/SIGTERM handlers, diagnostics and exit-code mapping.

Use an artifact-owned Publication enum (NotAttempted, Applied, Unknown). Preserve
separate primary stage, backend status, cleanup errors, sync state, byte counts
and possible residue. HTTP/FS status types are deliberately exposed losslessly;
their supported contracts are part of this experimental interface.

A void implementation helper owns Resources and writes the caller's Result.
Register defer cleanup before any callback or resource acquisition. Its normal
return completes cleanup before the outer execute snapshots/returns Result;
Goose defer also runs on nonlocal block returns. Exit/abort/crash cannot guarantee
cleanup. Callback normal return is required to receive a Result; callbacks must
not block, mutate request inputs, alter destination names or interfere with owned
resources. Prefer a named pure poll function. Test nonlocal escape after staging
and body writes with surviving-process descriptor and namespace assertions.

## Invariants

Authenticate exact bounded metadata bytes before parse, networking or filesystem
mutation; strict signature/key/digest lengths; exact independently authorized URL.
Caller owns expected digest/key trust, encoding, freshness, rollback and install
authorization. No signing, trust discovery, installer, extraction or execution.

Private parent with no other writers including same UID; canonical lower-case
ASCII distinct filesystem-nonaliasing leaves. Establish staging/final absence
before exclusive open; failed open may create an owned entry with a zero token.
Never delete a preexisting collision. Incremental SHA and bounded complete writes,
separate cumulative body limit, clean terminal HTTP200 and final digest required.

Checked data sync, consumed close exactly once, final cancellation check, then
NoReplace plus parent synchronization. Unknown is never retried, rolled back or
speculatively cleaned; Applied survives late errors. Cleanup errors are separate.
No hard wall deadline for DNS cleanup or filesystem I/O; no universal durability
or RSS promise. Preserve prior limits: metadata16KiB, chunk64KiB, headers16KiB,
body0..1GiB, HTTP transfer300s/connect10s, pump20ms.

## Dependencies and validation

Goose honors sourced imports only in the application root. Caller root aliases:
crypto, http, fs, json_codec and artifact. Supported/tested public identities:
crypto a4643f62bd5e76b371054c6537a95169a7930101;
HTTP aa915a0b21db1129f85e6e339a6f0171bcac0e77;
FS cd0bd29c78c435caaebf75bfecd8e3e2083636eb;
JSON 3fa7b5275399641f8069698b6c097ea66cef7929.
The library cannot enforce root-selected versions; callers choosing others own
compatibility. No sibling sources or parent index/pin edits. Reuse the existing
61-case realTLS regressions through the new public interface, then extend only
for new module contracts. Native signal guard remains CLI-only. Validate default,
named and block cancellation, cleanup diagnostics, independent calls and public
imported consumption. Run GCC/Clang sanitizers including C++ vptr; retain exact
per-invocation transcripts and immutable source fingerprints. Use repeated
independent interface/security/correctness/test-quality reviews. No universal
performance superiority claim or new benchmark campaign.
