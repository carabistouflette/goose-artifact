// SPDX-License-Identifier: Apache-2.0
import artifact from "../..";
import crypto from "carabistouflette/goose-crypto@a4643f62bd5e76b371054c6537a95169a7930101";
// Reviewed public streaming source, published by the HTTP owner.
import http from "carabistouflette/goose-http@aa915a0b21db1129f85e6e339a6f0171bcac0e77";
import fs from "carabistouflette/goose-fs@cd0bd29c78c435caaebf75bfecd8e3e2083636eb";
import json_codec from "carabistouflette/goose-json@3fa7b5275399641f8069698b6c097ea66cef7929";
import signals from "./signals";
import std;
import os;

fn decimal_limit(text: const u8[:]) -> i64, bool {
    if text.len < 1 || text.len > 10 { return 0, false; }
    var value: i64 = 0;
    for c in text {
        if c < '0' || c > '9' { return 0, false; }
        value = value * 10 + c - '0';
        if value > artifact::MAX_DOWNLOAD_BYTES { return 0, false; }
    }
    return value, true;
}
fn main() {
    let argv = args();
    if argv.len != 9 {
        write_stderr("usage: download METADATA_ABSOLUTE_PATH SIGNATURE_HEX TRUSTED_KEY_HEX EXPECTED_HTTPS_URL PRIVATE_PARENT STAGING_LEAF FINAL_LEAF BYTE_LIMIT\n");
        exit(2);
    }
    let limit, valid = decimal_limit(argv[8]);
    if !valid {
        let invalid = artifact::Result { stage: artifact::Stage.InvalidInput, .. };
        write_stderr(str(artifact::describe(invalid), " cleanup_guard_error=0\n"));
        exit(1);
    }
    let started = download_signals::start();
    if started != 0 {
        let stopped = download_signals::stop();
        write_stderr(str("artifact: stage=GuardStart os_error=", started,
            " cleanup_guard_error=", stopped, "\n"));
        exit(1);
    }
    let request = artifact::Request { metadata_path: argv[1], signature_hex: argv[2],
        trusted_key_hex: argv[3], expected_url: argv[4], private_parent: argv[5],
        staging_leaf: argv[6], final_leaf: argv[7], byte_limit: limit };
    let result = artifact::execute(request, download_signals::received);
    // The library has already completed its cleanup. Guard restoration is CLI policy.
    let stopped = download_signals::stop();
    var code: i64 = if result.stage == artifact::Stage.None && stopped == 0 { 0 } else { 1 };
    if result.stage == artifact::Stage.Cancelled {
        if result.cancellation_reason == 2 { code = 130; }
        if result.cancellation_reason == 15 { code = 143; }
    }
    let message = str(artifact::describe(result), " cleanup_guard_error=", stopped);
    if code == 0 { print(message); }
    else { write_stderr(str(message, "\n")); }
    exit(code);
}
