/* SPDX-License-Identifier: Apache-2.0 */
/* Benchmark fixture only: trust one ephemeral loopback CA.
 *
 * This shim does not weaken TLS verification. It supplies CURLOPT_CAINFO for
 * the single expected loopback URL and refuses every other URL. Peer and host
 * verification stay enabled in the library's own stream setup.
 *
 * It is linked into the measured process, so its cost (one getenv, two string
 * comparisons and one curl_easy_setopt per request) is part of every reported
 * end-to-end sample. It is not part of the artifact library code path.
 *
 * Unlike tests/transport.c this shim wraps only curl_multi_add_handle: the
 * benchmark must not link the fault-injection wrappers around write, fdatasync,
 * fstat, close, unlinkat or the root rename, because those are exactly the
 * filesystem operations the benchmark measures.
 */
#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

CURLMcode __real_curl_multi_add_handle(CURLM *, CURL *);

CURLMcode __wrap_curl_multi_add_handle(CURLM *multi, CURL *easy) {
    const char *expected = getenv("GOOSE_BENCH_URL");
    const char *ca = getenv("GOOSE_BENCH_CA");
    char *actual = NULL;
    if (!expected || !ca || strncmp(expected, "https://localhost:", 18) != 0 ||
        curl_easy_getinfo(easy, CURLINFO_EFFECTIVE_URL, &actual) != CURLE_OK ||
        !actual || strcmp(actual, expected) != 0) {
        fputs("benchmark fixture rejected unexpected URL\n", stderr);
        exit(90);
    }
    if (curl_easy_setopt(easy, CURLOPT_CAINFO, ca) != CURLE_OK) {
        fputs("benchmark fixture CA setup failed\n", stderr);
        exit(90);
    }
    return __real_curl_multi_add_handle(multi, easy);
}
