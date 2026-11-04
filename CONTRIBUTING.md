# Contributing

Use focused branches and Conventional Commits with imperative subjects. Keep the
module small, explicit and bounded. Caller policy owns digest/key trust,
freshness, rollback and installation authorization. Preserve authentication before
parsing/mutation, consumed-close semantics and independent publication/cleanup.

No bespoke cryptography, HTTP parser, installer or process-global signal policy
in the library. Supported source dependencies are declared in the program root;
never silently substitute versions. No stability promise before 1.0.

Behavior changes need public-interface regressions for success, malformed inputs,
cancellation, cleanup and surviving-process ownership. Run `make format check test`
and GCC/Clang `make sanitize`. Check generated Goose/runtime C and native C/C++
instrumentation, including C++ vptr runtime linkage. Request independent security,
correctness, performance and test-quality reviews; resolve findings and keep CI
passing. Keep per-run evidence attributable to frozen sources and compilers.

Do not commit binaries, toolchains, credentials or private notes. Raw validation
records may be committed with exact identities and limitations. Measure before
optimizing; bounded memory is not a hard RSS or wall-time promise. CI checks
correctness, not timing thresholds or universal rankings.
