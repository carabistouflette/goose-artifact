# Third-party notices

The initial workflow and CLI/harness are extracted from Apache-2.0 source
[goose-crypto b0deb95](https://github.com/carabistouflette/goose-crypto/tree/b0deb95f6e7fe82aa1e38fad8ca24d69c6a31c7d/examples/download).
No cryptographic or TLS implementation is vendored.

Supported/tested root-source dependencies (each Apache-2.0):

- goose-crypto a4643f62bd5e76b371054c6537a95169a7930101
- goose-http aa915a0b21db1129f85e6e339a6f0171bcac0e77
- goose-fs cd0bd29c78c435caaebf75bfecd8e3e2083636eb
- goose-json 3fa7b5275399641f8069698b6c097ea66cef7929

System libsodium, libcurl/TLS and goose-json's simdjson acceleration retain their
package licenses/notices. These are linked dependencies. Tests use Python
cryptography for signatures and local TLS certificates. The deterministic fixture
signing key is public test data and must never be used for real artifacts.

The fetched Goose compiler retains its own source-tree license. See
[LICENSE](LICENSE) for this repository's Apache-2.0 terms.
