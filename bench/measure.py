#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Measure the real artifact::execute download/integrity/filesystem path.

One sample is one independent OS process invocation of the example CLI, which
calls artifact::execute exactly once against an owned loopback HTTPS fixture.
Nothing is mocked: the measured process performs metadata authentication, the
TLS stream, per-chunk SHA-256 and staging writes, fsync, close and the atomic
NoReplace rename with parent synchronisation.

Time boundary. t0 is taken immediately before Popen of the benchmark binary and
t1 immediately after wait() returns. The interval therefore includes fork/exec,
dynamic linking, the TLS handshake, the complete execute workflow and process
exit. It excludes fixture server startup, certificate generation, metadata
signing, temporary directory creation and every post-run verification step.

This harness makes no universal performance claim. It records ordered raw
observations for one host, one toolchain and one bounded set of fixtures.
"""
from __future__ import annotations
import argparse
import datetime
import hashlib
import http.server
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import ssl
import statistics
import subprocess
import tempfile
import threading
import time

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
CLI = ROOT / "examples/download/main.goose"
PATTERN = bytes(range(256))
MAX_SAMPLES = 20
PROXY_VARIABLES = ("http_proxy", "https_proxy", "all_proxy",
                   "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")


def run(command, **kwargs):
    return subprocess.run(command, check=True, timeout=600, **kwargs)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while piece := stream.read(1 << 20):
            digest.update(piece)
    return digest.hexdigest()


def payload_hash(size: int) -> str:
    digest = hashlib.sha256()
    remaining = size
    while remaining:
        piece = PATTERN[:min(remaining, len(PATTERN))]
        digest.update(piece)
        remaining -= len(piece)
    return digest.hexdigest()


def source_snapshot(repo: Path):
    paths = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo).split(b"\0")
    files = {}
    for raw in sorted(set(paths) - {b""}):
        path = repo / os.fsdecode(raw)
        data = (os.fsencode(os.readlink(path)) if path.is_symlink()
                else path.read_bytes() if path.exists() else b"<deleted>")
        files[os.fsdecode(raw)] = hashlib.sha256(data).hexdigest()
    return {"head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
            "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo, text=True).strip(),
            "status": subprocess.check_output(["git", "status", "--short", "--untracked-files=all"], cwd=repo, text=True),
            "files": files}


def build(goose: Path, cc: str):
    """Build the measured binary with only the CA-trust fixture shim."""
    found = shutil.which(cc)
    if found is None:
        raise RuntimeError(f"compiler not found: {cc}")
    compiler = str(Path(found).resolve())
    version = subprocess.check_output([compiler, "--version"], text=True)
    flags = ["-O2", "-UNDEBUG"]
    identity = hashlib.sha256(
        (HERE / "transport.c").read_bytes() + version.encode()
        + repr((compiler, flags)).encode()).hexdigest()[:16]
    folder = ROOT / ".build" / f"bench-{Path(compiler).name}-{identity}"
    folder.mkdir(parents=True, exist_ok=True)
    commands = folder / "compiler-commands.jsonl"
    commands.write_text("")
    shim = folder / "transport.o"
    curl_flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "libcurl"], text=True))
    run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror", "-fPIC", *flags,
         *curl_flags, "-c", str(HERE / "transport.c"), "-o", str(shim)])
    wrapper = folder / "cc"
    wrapper.write_text(
        "#!/usr/bin/env python3\nimport json, os, sys\n"
        f"compiler={compiler!r}\nflags={flags!r}\nlog={str(commands)!r}\n"
        "args=sys.argv[1:]\n"
        "probe=any(a in args for a in ('-v','--version','-dumpversion','-dumpmachine'))\n"
        "link=not probe and not any(a in args for a in ('-c','-E','-S'))\n"
        "program=link and any(a.startswith('@') and a.endswith(('/link-cc.rsp','/link-cxx.rsp')) for a in args)\n"
        f"extra=[{str(shim)!r}, '-Wl,--wrap=curl_multi_add_handle', '-lcurl'] if program else []\n"
        "effective=[compiler,*args,*([] if probe else flags),*extra]\n"
        "with open(log,'a') as f: f.write(json.dumps(effective)+'\\n')\n"
        "os.execv(compiler,effective)\n")
    wrapper.chmod(0o755)
    binary = folder / "download-bench"
    command = [str(goose), "build", "examples/download/main.goose", "--standalone",
               "--cc", str(wrapper), "-o", str(binary)]
    run(command, cwd=ROOT)
    return {"binary": binary, "shim": shim, "wrapper": wrapper, "commands": commands,
            "compiler": compiler, "compiler_version": version.strip(), "flags": flags,
            "build_command": command, "folder": folder}


def certificate(folder: Path):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = folder / "ca.pem", folder / "server-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                           serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    return cert_path, key_path


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass

    def do_GET(self):
        self.server.requests.append(self.path)
        size = self.server.size
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(size))
            self.send_header("Connection", "close")
            self.end_headers()
            sent = 0
            while sent < size:
                count = min(size - sent, 65536)
                start = sent % len(PATTERN)
                # Repeat the pattern before slicing: PATTERN is only 256 bytes,
                # so slicing it directly would truncate the declared body.
                piece = (PATTERN * (count // len(PATTERN) + 2))[start:start + count]
                self.wfile.write(piece)
                self.wfile.flush()
                sent += count
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
            pass


def peak_rss_kib(pid: int) -> int:
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
    except (FileNotFoundError, ProcessLookupError):
        return 0
    return 0


def parse_fields(stream: bytes):
    text = stream.decode()
    if not text.startswith("artifact: ") or not text.endswith("\n") or text.count("\n") != 1:
        raise RuntimeError(f"unexpected diagnostic shape: {text!r}")
    return dict(part.split("=", 1) for part in text.strip()[10:].split())


def sample(server, binary: Path, ca: Path, signing, public_key: str, url: str,
           folder: Path, size: int, byte_limit: int, signed_digest: str,
           expect: str):
    """Run one independent process and verify its effects outside the timing.

    expect is "success" (full workflow publishes), "digest" (the whole body is
    still transferred, hashed and written, then rejected at DigestMismatch) or
    "signature" (rejected before any network or file mutation, which measures
    the process startup floor).
    """
    parent = folder / "out"
    parent.mkdir(mode=0o700, parents=True)
    os.chmod(parent, 0o700)
    staging_leaf, final_leaf = "staging.part", "verified.bin"
    staging_path, final_path = parent / staging_leaf, parent / final_leaf
    metadata = folder / "metadata.json"
    raw = json.dumps({"url": url, "sha256": signed_digest}, separators=(",", ":")).encode()
    metadata.write_bytes(raw)
    signature = (signing.sign(b"not the metadata").hex() if expect == "signature"
                 else signing.sign(raw).hex())
    server.size = size
    before = len(server.requests)
    env = dict(os.environ, GOOSE_BENCH_URL=url, GOOSE_BENCH_CA=str(ca))
    for name in PROXY_VARIABLES:
        env[name] = "http://127.0.0.1:1"
    command = [str(binary), str(metadata), signature, public_key, url, str(parent),
               staging_leaf, final_leaf, str(byte_limit)]
    started = time.monotonic_ns()
    child = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    peak = 0
    while child.poll() is None:
        peak = max(peak, peak_rss_kib(child.pid))
        time.sleep(0.0005)
    stdout, stderr = child.communicate()
    finished = time.monotonic_ns()
    # Everything below is verification and is outside the reported interval.
    succeeded = expect == "success"
    try:
        fields = parse_fields(stdout if succeeded else stderr)
    except RuntimeError as error:
        raise RuntimeError(f"{error} (exit {child.returncode}, "
                           f"stdout={stdout!r}, stderr={stderr!r})") from error
    other = stderr if succeeded else stdout
    if other:
        raise RuntimeError(f"unexpected extra output: {other!r}")
    if succeeded:
        if child.returncode != 0:
            raise RuntimeError(f"expected success, exit {child.returncode}: {fields}")
        if fields["stage"] != "None" or fields["publication"] != "Applied":
            raise RuntimeError(f"unexpected outcome: {fields}")
        if not final_path.exists():
            raise RuntimeError("published file missing")
        if final_path.stat().st_size != size:
            raise RuntimeError("published size mismatch")
        if sha256_file(final_path) != payload_hash(size):
            raise RuntimeError("published digest mismatch")
        if staging_path.exists():
            raise RuntimeError("staging residue after publication")
    else:
        if child.returncode == 0:
            raise RuntimeError("control sample unexpectedly succeeded")
        if final_path.exists():
            raise RuntimeError("control published an unverified file")
        if expect == "digest":
            if fields["stage"] != "DigestMismatch" or fields["publication"] != "NotAttempted":
                raise RuntimeError(f"control did not fail at the digest: {fields}")
            # The digest control must still have moved and hashed the whole
            # body: this is the proof that the timed path performs real work
            # rather than folding to an idle path.
            if int(fields["received_bytes"]) != size or int(fields["written_bytes"]) != size:
                raise RuntimeError(f"body was not fully transferred and written: {fields}")
        else:
            if fields["stage"] != "Signature" or fields["publication"] != "NotAttempted":
                raise RuntimeError(f"startup floor did not fail at the signature: {fields}")
            if int(fields["received_bytes"]) != 0 or int(fields["written_bytes"]) != 0:
                raise RuntimeError(f"startup floor performed transfer work: {fields}")
    if fields["residue_may_remain"] != "false":
        raise RuntimeError(f"unexpected residue: {fields}")
    expected_requests = 0 if expect == "signature" else 1
    if len(server.requests) - before != expected_requests:
        raise RuntimeError(f"expected {expected_requests} fixture request(s), "
                           f"saw {server.requests[before:]}")
    record = {"size_bytes": size, "byte_limit": byte_limit, "expect": expect,
              "elapsed_ns": finished - started, "exit_code": child.returncode,
              "stage": fields["stage"], "publication": fields["publication"],
              "received_bytes": int(fields["received_bytes"]),
              "written_bytes": int(fields["written_bytes"]),
              "peak_rss_kib_sampled": peak,
              "final_sha256": sha256_file(final_path) if final_path.exists() else None,
              "final_size": final_path.stat().st_size if final_path.exists() else None,
              "staging_absent": not staging_path.exists(),
              "stdout": stdout.decode(), "stderr": stderr.decode()}
    shutil.rmtree(folder)
    return record


def plan(sizes, counts):
    """Round-robin the sizes so drift is spread across every workload."""
    order, remaining = [], dict(zip(sizes, counts))
    while any(remaining.values()):
        for size in sizes:
            if remaining.get(size, 0) > 0:
                order.append(size)
                remaining[size] -= 1
    return order


def backend_version(name):
    try:
        return subprocess.check_output(["pkg-config", "--modversion", name], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--goose", type=Path, required=True)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--sizes", default="65536,1048576,4194304")
    parser.add_argument("--samples", default="4,8,4",
                        help="independent process samples per size, same order as --sizes")
    parser.add_argument("--controls", type=int, default=2,
                        help="digest-mismatch control samples at the middle size")
    parser.add_argument("--startup-controls", type=int, default=2,
                        help="signature-rejection startup-floor samples at the middle size")
    parser.add_argument("--output", type=Path, default=ROOT / ".build/bench.json")
    parser.add_argument("--force", action="store_true", help="replace an existing record")
    args = parser.parse_args()

    sizes = [int(value) for value in args.sizes.split(",")]
    counts = [int(value) for value in args.samples.split(",")]
    if len(sizes) != len(counts) or not sizes:
        raise SystemExit("--sizes and --samples must have the same non-zero length")
    if any(size <= 0 for size in sizes) or any(count <= 0 for count in counts):
        raise SystemExit("sizes and sample counts must be positive")
    total = sum(counts) + args.controls + args.startup_controls
    if total > MAX_SAMPLES:
        raise SystemExit(f"{total} samples exceeds the bounded budget of {MAX_SAMPLES}")
    if args.output.exists() and not args.force:
        raise SystemExit(f"refusing to replace existing record: {args.output}")

    goose = args.goose.resolve()
    before = source_snapshot(ROOT)
    built = build(goose, args.cc)
    measured_sha256 = sha256_file(built["binary"])
    goose_version = subprocess.check_output([str(goose), "--version"], text=True).strip()
    pin = (ROOT / "GOOSE_REVISION").read_text().strip()
    advertised = re.search(r"\bgoose ([0-9a-f]{7,40})\b", goose_version)
    if advertised is None or not pin.startswith(advertised.group(1)):
        raise SystemExit("Goose binary does not advertise the pinned revision")

    signing = ed25519.Ed25519PrivateKey.from_private_bytes(hashlib.sha256(b"goose artifact benchmark").digest())
    public_key = signing.public_key().public_bytes(serialization.Encoding.Raw,
                                                   serialization.PublicFormat.Raw).hex()
    samples = []
    with tempfile.TemporaryDirectory(prefix="goose-artifact-bench-") as tmp:
        folder = Path(tmp)
        ca, key = certificate(folder)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(ca, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        server.requests = []
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"https://localhost:{server.server_port}/payload"
        try:
            order = plan(sizes, counts)
            for index, size in enumerate(order):
                samples.append({"index": index, "kind": "success", **sample(
                    server, built["binary"], ca, signing, public_key, url,
                    folder / f"sample-{index}", size, size, payload_hash(size), "success")})
            middle = sizes[len(sizes) // 2]
            for offset in range(args.controls):
                index = len(order) + offset
                samples.append({"index": index, "kind": "digest-control", **sample(
                    server, built["binary"], ca, signing, public_key, url,
                    folder / f"sample-{index}", middle, middle, "0" * 64, "digest")})
            for offset in range(args.startup_controls):
                index = len(order) + args.controls + offset
                samples.append({"index": index, "kind": "startup-floor", **sample(
                    server, built["binary"], ca, signing, public_key, url,
                    folder / f"sample-{index}", middle, middle, payload_hash(middle), "signature")})
        finally:
            server.shutdown()
            server.server_close()

    after = source_snapshot(ROOT)
    if after != before:
        raise SystemExit("source changed during measurement; no record saved")
    if sha256_file(built["binary"]) != measured_sha256:
        raise SystemExit("measured binary changed during measurement; no record saved")

    successes = [item for item in samples if item["kind"] == "success"]
    result = {
        "schema": 1,
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": before,
        "sample_unit": "one independent OS process invocation of the example CLI calling artifact::execute once",
        "time_boundary": {
            "start": "immediately before Popen of the benchmark binary",
            "end": "immediately after wait() returns",
            "includes": ["fork/exec", "dynamic linking", "TLS handshake", "metadata read",
                         "Ed25519 verification", "JSON parse", "staging create",
                         "HTTPS stream", "per-chunk SHA-256 and staging write",
                         "stream close", "digest compare", "fsync", "file close",
                         "atomic NoReplace rename with parent sync", "process exit"],
            "excludes": ["fixture server startup", "certificate generation", "metadata signing",
                         "temporary directory creation", "all post-run verification"],
            "clock": "CLOCK_MONOTONIC via time.monotonic_ns in the parent process",
        },
        "toolchain": {
            "goose_revision": pin, "goose_version": goose_version,
            "goose_path": str(goose), "goose_binary_sha256": sha256_file(goose),
            "cc": args.cc, "cc_path": built["compiler"],
            "cc_binary_sha256": sha256_file(Path(built["compiler"])),
            "cc_version": built["compiler_version"], "flags": built["flags"],
            "build_command": built["build_command"],
            "effective_compiler_commands": [json.loads(line) for line in
                                            built["commands"].read_text().splitlines()],
            "compiler_wrapper": built["wrapper"].read_text(),
            "backends": {name: backend_version(name) for name in ("libcurl", "openssl", "libsodium")},
        },
        "machine": {
            "platform": platform.platform(), "machine": platform.machine(),
            "kernel": platform.release(), "logical_cpus": os.cpu_count(),
            "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "cpu_models": sorted({line.split(":", 1)[1].strip()
                                  for line in Path("/proc/cpuinfo").read_text().splitlines()
                                  if line.startswith("model name")}),
            "pinning": "none; the measured process inherits the parent affinity mask",
        },
        "binaries": {
            "measured": {"path": str(built["binary"]), "sha256": measured_sha256},
            "fixture_shim": {"path": str(built["shim"]), "sha256": sha256_file(built["shim"]),
                             "scope": "wraps curl_multi_add_handle only to set CURLOPT_CAINFO for the "
                                      "expected loopback URL; no fault-injection wrappers are linked"},
        },
        "fixture": {
            "pattern": "payload[i] = i % 256, repeating",
            "sizes_bytes": sizes, "samples_per_size": counts,
            "digest_controls": args.controls, "startup_controls": args.startup_controls,
            "control_kinds": {
                "digest-control": "metadata signs an all-zero digest; the body is still fully "
                                  "transferred, hashed and written before DigestMismatch",
                "startup-floor": "the signature is over different bytes, so the run is rejected at "
                                 "Signature before any network or file mutation; this measures the "
                                 "process startup floor",
            },
            "order": [item["size_bytes"] for item in samples],
            "order_policy": "round-robin across sizes to spread drift; no A/B comparison is made, "
                            "so no alternating implementation order applies",
            "server": "owned ThreadingHTTPServer on 127.0.0.1 with an ephemeral self-signed CA",
        },
        "samples": samples,
        "observations": {
            "successful_samples": len(successes),
            "control_samples": len(samples) - len(successes),
            "elapsed_ns_by_size": {
                str(size): [item["elapsed_ns"] for item in successes if item["size_bytes"] == size]
                for size in sizes},
            "median_elapsed_ns_by_size": {
                str(size): statistics.median([item["elapsed_ns"] for item in successes
                                              if item["size_bytes"] == size])
                for size in sizes},
            "peak_rss_kib_sampled_by_size": {
                str(size): [item["peak_rss_kib_sampled"] for item in successes
                            if item["size_bytes"] == size] for size in sizes},
            "startup_floor_elapsed_ns": [item["elapsed_ns"] for item in samples
                                         if item["kind"] == "startup-floor"],
            "digest_control_elapsed_ns": [item["elapsed_ns"] for item in samples
                                          if item["kind"] == "digest-control"],
            "work_proof": "every digest-control sample reports received_bytes == written_bytes == "
                          "size before failing at DigestMismatch, and every startup-floor sample "
                          "reports zero transferred bytes; the timed path therefore performs the "
                          "real transfer, hash and write rather than folding to an idle path",
        },
        "limitations": [
            "One host, one toolchain, one bounded fixture set; no universal performance claim",
            "No Rust or other implementation is compared; no improvement ratio is claimed",
            "The measured binary links a fixture shim that sets CURLOPT_CAINFO for the loopback CA; "
            "it is not byte-identical to the production binary and its cost is inside every sample",
            "Loopback TLS and a local filesystem do not represent a wide-area network or a real disk",
            "No CPU pinning: scheduler migration and frequency scaling are inside every sample",
            "peak_rss_kib_sampled is a polled VmHWM observation, a lower bound on true peak, "
            "not a hard memory promise",
            "elapsed_ns is end-to-end process wall time; per-phase costs are not separated",
            "At these small sizes the sample is dominated by process startup and the TLS handshake, "
            "so no library throughput is isolated and no bytes-per-second figure is claimed",
            "CI runs a correctness smoke only; no timing threshold is asserted anywhere",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Saved {len(samples)} ordered samples to {args.output}")


if __name__ == "__main__":
    main()
