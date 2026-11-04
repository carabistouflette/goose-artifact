// SPDX-License-Identifier: Apache-2.0
import artifact from "..";
import crypto from "carabistouflette/goose-crypto@a4643f62bd5e76b371054c6537a95169a7930101";
import http from "carabistouflette/goose-http@aa915a0b21db1129f85e6e339a6f0171bcac0e77";
import fs from "carabistouflette/goose-fs@cd0bd29c78c435caaebf75bfecd8e3e2083636eb";
import json_codec from "carabistouflette/goose-json@3fa7b5275399641f8069698b6c097ea66cef7929";
import std;
fn cancel_named() -> i64 { return -19; }
fn main() {
    let request = artifact::Request {
        metadata_path:   "/must-not-read", signature_hex: "00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
        trusted_key_hex: "0000000000000000000000000000000000000000000000000000000000000000", expected_url: "https://example.invalid/payload",
        private_parent:  "/must-not-open", staging_leaf: "staging.part",
        final_leaf:      "verified.bin", byte_limit: 65536,
    };
    let result = artifact::execute(request, cancel_named);
    assert(result.stage == artifact::Stage.Cancelled && result.cancellation_reason == -19);
    assert(result.publication == artifact::Publication.NotAttempted);
    assert(!result.residue_may_remain && result.received_bytes == 0 && result.written_bytes == 0);
    assert(result.cleanup_http.error == http::Error.None);
    assert(result.cleanup_file.error == fs::Error.None);
    assert(result.cleanup_staging.error == fs::Error.None);
    assert(result.cleanup_root.error == fs::Error.None);
    assert(result.cleanup_context.error == fs::Error.None);
    var calls: i64 = 0;
    let block_result = artifact::execute(request) { calls++; -37 };
    assert(calls == 1 && block_result.stage == artifact::Stage.Cancelled && block_result.cancellation_reason == -37);
    let invalid = artifact::Request { metadata_path: "", signature_hex: "", trusted_key_hex: "",
        expected_url: "", private_parent: "", staging_leaf: "", final_leaf: "", byte_limit: 0 };
    assert(artifact::execute(invalid).stage == artifact::Stage.InvalidInput);
    print("artifact public interface: default and opaque cancellation passed");
}
