# Security policy

Experimental Linux x86-64 library, with no security certification. Use patched
system dependencies and reviewed source pins. Report vulnerabilities privately
through the repository's private vulnerability reporting facility when available,
or contact the maintainer privately. Do not publish sensitive exploit details.

Callers select trusted keys/digests and authorize exact URLs and metadata
protocols. The library does not establish key trust, freshness, anti-rollback or
installation authorization. A valid signature under a newly downloaded key does
not establish trust in that key.

Private parent/no other writers (including same UID) and distinct nonaliasing
names are contractual preconditions. This does not defend against a malicious
same-UID process violating those conditions. Preserve Unknown and Applied
publication outcomes even when errors or cancellation arrive late.
