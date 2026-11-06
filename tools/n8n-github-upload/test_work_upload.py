import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import subprocess
import sys
import select
import unittest
import work_upload as w

NOW = 1_800_000_000
UPLOAD_ID = "9d94bcf3-9a28-4014-93d5-ce8e5d259c7d"
TARGET = {"repositoryId": 1448151721, "repository": "markmalina/automations", "branch": "test/upload", "prefix": "данные"}
TOKEN = "f" * 64


class Response:
    def __init__(self, body, status=200):
        self.status, self.body = status, body
    def read(self, maximum):
        return self.body[:maximum]


class Connection:
    def __init__(self, response):
        self.response, self.headers, self.body, self.closed = response, {}, bytearray(), False
    def putrequest(self, method, path):
        self.method, self.path = method, path
    def putheader(self, name, value):
        self.headers[name] = value
    def endheaders(self):
        pass
    def send(self, data):
        self.body.extend(data)
    def getresponse(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response
    def close(self):
        self.closed = True


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.binary = bytes(range(256)) * 4 + b"\x00\xff\r\n" + "Кириллица".encode()
        self.file = self.root / "sample.bin"
        self.file.write_bytes(self.binary)
        self.bundle = w.prepare(TARGET, [{"source": str(self.file), "path": "файл.bin"}], UPLOAD_ID)
        self.grant = {"uploadId": UPLOAD_ID, "manifestDigest": self.bundle["digest"], "target": dict(TARGET),
                      "uploadUrl": w.URL, "headerName": "X-Work-Upload-Grant", "token": TOKEN,
                      "expiresAt": dt.datetime.fromtimestamp(NOW + 600, dt.timezone.utc).isoformat()}
    def receipt(self):
        return {"success": True, "uploadId": UPLOAD_ID, "repository": TARGET["repository"], "repositoryId": TARGET["repositoryId"],
                "branch": TARGET["branch"], "fileCount": 1, "totalBytes": len(self.binary), "commitSha": "a" * 40,
                "url": "https://github.com/markmalina/automations/commit/" + "a" * 40,
                "files": [{"path": "данные/файл.bin", "sha256": hashlib.sha256(self.binary).hexdigest(), "bytes": len(self.binary)}]}
    def transport(self, body=None, status=200):
        conn = Connection(Response(json.dumps(body if body is not None else self.receipt()).encode(), status))
        calls = []
        def factory(host, **options):
            calls.append((host, options))
            return conn
        return conn, calls, factory
    def assert_error(self, expected, function):
        with self.assertRaises(w.UploadError) as ctx:
            function()
        self.assertEqual(expected, ctx.exception.code)
    def test_prepare_deterministic_digest_real_bytes_and_private_output(self):
        self.assertEqual(self.bundle, w.prepare(TARGET, [{"source": str(self.file), "path": "файл.bin"}], UPLOAD_ID))
        self.assertEqual(self.bundle["digest"], hashlib.sha256(w.canonical(self.bundle["manifest"])).hexdigest())
        out = self.root / "bundle.json"
        w.write_json(out, self.bundle)
        self.assertEqual(stat.S_IMODE(out.stat().st_mode), 0o600)
        self.assertEqual(w.read_json(out), self.bundle)
        self.assertNotIn(self.binary, out.read_bytes())
    def test_binary_multipart_has_correct_length_fields_and_verified_tls(self):
        conn, calls, factory = self.transport()
        receipt = w.upload(self.bundle, self.grant, factory, NOW)
        self.assertEqual(calls[0][0], w.HOST)
        self.assertEqual(calls[0][1]["timeout"], 300)
        self.assertTrue(calls[0][1]["context"].check_hostname)
        self.assertEqual(conn.method, "POST")
        self.assertEqual(conn.path, w.ENDPOINT)
        self.assertEqual(int(conn.headers["Content-Length"]), len(conn.body))
        self.assertEqual(conn.headers["X-Work-Upload-Grant"], TOKEN)
        self.assertIn(self.binary, conn.body)
        self.assertIn(w.canonical(self.bundle["manifest"]), conn.body)
        self.assertIn(b'name="file0"; filename="file0.bin"', conn.body)
        self.assertTrue(conn.closed)
        self.assertEqual(receipt["commitSha"], "a" * 40)
    def test_wrong_grant_bindings_fail_before_any_connection(self):
        for key, value in [("uploadId", "0" * 36), ("manifestDigest", "0" * 64), ("target", {**TARGET, "branch": "another"}),
                           ("uploadUrl", "https://evil.invalid/upload"), ("uploadUrl", w.URL + "?token=anything"),
                           ("headerName", "Authorization"), ("token", "not-a-token"), ("expiresAt", "invalid")]:
            with self.subTest(key=key, value=str(value)[:40]):
                grant = {**self.grant, key: value}
                calls = []
                with self.assertRaises(w.UploadError):
                    w.upload(self.bundle, grant, lambda *args, **kw: calls.append(1), NOW)
                self.assertEqual(calls, [])
    def test_expiry_future_limit_and_expired_grant_fail(self):
        for seconds in (-1, 0, 901):
            grant = {**self.grant, "expiresAt": dt.datetime.fromtimestamp(NOW + seconds, dt.timezone.utc).isoformat()}
            self.assert_error("E_GRANT_EXPIRY", lambda: w.upload(self.bundle, grant, lambda *a, **k: self.fail("network"), NOW))
    def test_changed_file_fails_before_connect(self):
        self.file.write_bytes(self.binary + b"changed")
        self.assert_error("E_SOURCE_CHANGED", lambda: w.upload(self.bundle, self.grant, lambda *a, **k: self.fail("network"), NOW))
    def test_symlink_file_fails_before_connect(self):
        self.file.unlink()
        real = self.root / "other.bin"
        real.write_bytes(self.binary)
        self.file.symlink_to(real)
        self.assert_error("E_SOURCE_SYMLINK", lambda: w.upload(self.bundle, self.grant, lambda *a, **k: self.fail("network"), NOW))
    def test_target_and_path_boundaries(self):
        for target in [{**TARGET, "repository": "foreign/repository"}, {**TARGET, "repositoryId": True},
                       {**TARGET, "repository": "markmalina/.hidden"}, {**TARGET, "repository": "markmalina/-repo"},
                       {**TARGET, "branch": "main..other"}, {**TARGET, "branch": "feature/.hidden"},
                       {**TARGET, "branch": "main.lock"}, {**TARGET, "branch": "main.LOCK"},
                       {**TARGET, "branch": "HEAD"}, {**TARGET, "branch": "head"}, {**TARGET, "prefix": ".git"}]:
            with self.subTest(target=target), self.assertRaises(w.UploadError):
                w.prepare(target, [{"source": str(self.file), "path": "ok.bin"}])
        for path in ["/absolute", "../escape", "a//b", "a/./b", "a\\b", "a,b", "a\x00b", "e\u0301.bin", "\ud800"]:
            with self.subTest(path=repr(path)), self.assertRaises(w.UploadError):
                w.prepare(TARGET, [{"source": str(self.file), "path": path}])
        self.assert_error("E_WORKFLOWS_PERMISSION", lambda: w.prepare({**TARGET, "prefix": ""}, [{"source": str(self.file), "path": ".github/workflows/file.yml"}]))
    def test_case_and_directory_collisions_fail(self):
        for a, b in [("a.bin", "A.bin"), ("a", "a/b.bin")]:
            self.assert_error("E_PATH_COLLISION", lambda: w.prepare(TARGET, [{"source": str(self.file), "path": a}, {"source": str(self.file), "path": b}]))
    def test_limits_and_manifest_source_tampering_fail(self):
        self.assert_error("E_LIMIT", lambda: w.prepare(TARGET, []))
        self.assert_error("E_LIMIT", lambda: w.prepare(TARGET, [{"source": str(self.file), "path": str(i)} for i in range(101)]))
        bundle = copy.deepcopy(self.bundle)
        bundle["manifest"]["target"]["branch"] = "changed"
        self.assert_error("E_BUNDLE_BINDING", lambda: w.upload(bundle, self.grant, lambda *a, **k: self.fail("network"), NOW))
    def test_exact_file_field_grammar(self):
        for field in ("file0", "file1", "file9", "file10", "file99"):
            manifest = copy.deepcopy(self.bundle["manifest"])
            manifest["files"][0]["field"] = field
            self.assertEqual(w.manifest_valid(manifest), len(self.binary))
        for field in ("f000", "file00", "file01", "file100", "file-1", "file", "File0"):
            manifest = copy.deepcopy(self.bundle["manifest"])
            manifest["files"][0]["field"] = field
            self.assert_error("E_MANIFEST", lambda: w.manifest_valid(manifest))
    def test_utf8_path_component_and_combined_limits(self):
        # Per-component byte limit includes Unicode, while total is2048bytes.
        for path in ("x" * 256, "я" * 128):
            self.assert_error("E_PATH", lambda: w.prepare(TARGET, [{"source": str(self.file), "path": path}]))
        path = "/".join(["x" * 250] * 5)
        bundle = w.prepare({**TARGET, "prefix": ""}, [{"source": str(self.file), "path": path}], UPLOAD_ID)
        self.assertEqual(bundle["manifest"]["files"][0]["path"], path)
        prefix = "/".join(["p" * 250] * 4)
        self.assert_error("E_PATH", lambda: w.prepare({**TARGET, "prefix": prefix}, [{"source": str(self.file), "path": path}]))
        self.assert_error("E_BRANCH", lambda: w.target_valid({**TARGET, "branch": "x" * 201}))
        self.assert_error("E_WORKFLOWS_PERMISSION", lambda: w.target_valid({**TARGET, "prefix": ".github/workflows"}))
    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_actual_fifo_prepare_terminates_without_network_or_writer(self):
        fifo = self.root / "blocked-fifo"
        os.mkfifo(fifo)
        target, files = self.root / "target.json", self.root / "files.json"
        target.write_text(json.dumps(TARGET))
        files.write_text(json.dumps([{"source": str(fifo), "path": "result.bin"}]))
        run = subprocess.run([sys.executable, str(Path(w.__file__)), "prepare", "--target", str(target),
                              "--files", str(files), "--output", str(self.root / "bundle.json")],
                             capture_output=True, text=True, timeout=2)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)["errorCode"], "E_SOURCE")
        self.assertFalse((self.root / "bundle.json").exists())
    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO required")
    def test_fifo_swap_after_lstat_is_nonblocking_and_rejected(self):
        fifo = self.root / "race-fifo"
        os.mkfifo(fifo)
        code = """import sys,os
sys.path.insert(0,sys.argv[1])
import work_upload as w
regular=os.stat(sys.argv[3])
w.os.lstat=lambda path:regular
try:
 w.open_source(sys.argv[2])
except w.UploadError as e:
 print(e.code)
 sys.exit(0 if e.code=='E_SOURCE' else 2)
sys.exit(3)
"""
        run = subprocess.run([sys.executable, "-c", code, str(Path(w.__file__).parent), str(fifo), str(self.file)],
                             capture_output=True, text=True, timeout=2)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "E_SOURCE")
    def test_response_is_bounded_and_errors_never_echo_body(self):
        for response, expected in [(Response(b"x" * (w.MAX_RESPONSE + 1)), "E_RESPONSE_SIZE"),
                                   (Response(b"not-json-" + TOKEN.encode()), "E_RESPONSE_SHAPE"),
                                   (Response(TOKEN.encode(), 500), "E_UPLOAD_HTTP_500"),
                                   (Response(TOKEN.encode(), 307), "E_REDIRECT_DENIED"),
                                   (OSError("network failure " + TOKEN), "E_UPLOAD_OUTCOME_UNKNOWN")]:
            conn = Connection(response)
            with self.subTest(expected=expected):
                self.assert_error(expected, lambda: w.upload(self.bundle, self.grant, lambda *a, **kw: conn, NOW))
                self.assertTrue(conn.closed)
    def test_receipt_binding_rejects_wrong_commit_target_files_and_bool_counts(self):
        for key, value in [("commitSha", "wrong"), ("branch", "another"), ("repository", "foreign/repo"),
                           ("fileCount", True), ("totalBytes", False), ("url", "https://evil.invalid"),
                           ("files", [{"path": "different", "sha256": "a" * 64, "bytes": 1}])]:
            conn, _, factory = self.transport({**self.receipt(), key: value})
            self.assert_error("E_RECEIPT_BINDING", lambda: w.upload(self.bundle, self.grant, factory, NOW))
    def test_unknown_receipt_fields_and_nested_secret_echo_are_stripped(self):
        receipt = self.receipt()
        receipt["token"] = TOKEN
        receipt["files"][0]["secret"] = TOKEN
        receipt["details"] = {"Authorization": TOKEN}
        conn, _, factory = self.transport(receipt)
        result = w.upload(self.bundle, self.grant, factory, NOW)
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertNotIn("details", result)
    def test_empty_binary_and_empty_prefix_work(self):
        self.file.write_bytes(b"")
        bundle = w.prepare({**TARGET, "prefix": ""}, [{"source": str(self.file), "path": "empty.bin"}], UPLOAD_ID)
        self.assertEqual(bundle["grantRequest"]["totalBytes"], 0)
        self.assertEqual(bundle["manifest"]["files"][0]["sha256"], hashlib.sha256(b"").hexdigest())
    def test_manifest_utf16_bound_and_explicit_empty_id(self):
        mappings = [{"source": str(self.file), "path": str(i) + "/" + "x" * 200 + "/" + "y" * 200} for i in range(100)]
        self.assert_error("E_MANIFEST_TOO_LARGE", lambda: w.prepare(TARGET, mappings))
        self.assert_error("E_MANIFEST", lambda: w.prepare(TARGET, [{"source": str(self.file), "path": "ok"}], ""))
    def test_actual_prepare_cli_and_missing_grant_are_safe(self):
        target, files, output = self.root / "target.json", self.root / "files.json", self.root / "bundle.json"
        target.write_text(json.dumps(TARGET))
        files.write_text(json.dumps([{"source": str(self.file), "path": "result.bin"}]))
        command = [sys.executable, str(Path(w.__file__)), "prepare", "--target", str(target), "--files", str(files),
                   "--upload-id", UPLOAD_ID, "--output", str(output)]
        run = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["uploadId"], UPLOAD_ID)
        self.assertEqual(w.read_json(output)["manifest"]["uploadId"], UPLOAD_ID)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        run = subprocess.run([sys.executable, str(Path(w.__file__)), "upload", "--bundle", str(output),
                              "--grant", str(self.root / "missing-secret.json"), "--receipt", str(self.root / "r.json")],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)["errorCode"], "E_INPUT")
        self.assertNotIn("Traceback", run.stderr)
    def test_full_100_file_30mb_binary_package_offline(self):
        self.file.write_bytes(bytes(range(250)) * 1200)
        mappings = [{"source": str(self.file), "path": "batch/file-%03d.bin" % i} for i in range(100)]
        bundle = w.prepare(TARGET, mappings, UPLOAD_ID)
        grant = {**self.grant, "manifestDigest": bundle["digest"]}
        receipt = {**self.receipt(), "fileCount": 100, "totalBytes": 30_000_000,
                   "files": [{"path": "данные/" + f["path"], "sha256": f["sha256"], "bytes": f["bytes"]}
                             for f in bundle["manifest"]["files"]]}
        conn, _, factory = self.transport(receipt)
        result = w.upload(bundle, grant, factory, NOW)
        self.assertEqual(result["fileCount"], 100)
        self.assertEqual(result["totalBytes"], 30_000_000)
        self.assertEqual(len(conn.body), int(conn.headers["Content-Length"]))
        self.assertEqual(conn.body.count(b"Content-Type: application/octet-stream\r\n"), 100)
    def grant_stdin_cli(self, raw, output=None):
        bundle_file = self.root / "bundle.json"
        w.write_json(bundle_file, self.bundle)
        output = output or self.root / "received-grant.json"
        run = subprocess.run([sys.executable, str(Path(w.__file__)), "receive-grant", "--bundle", str(bundle_file),
                              "--output", str(output)], input=raw, capture_output=True)
        self.assertNotIn(TOKEN.encode(), run.stdout + run.stderr)
        return run, output
    def fresh_grant(self):
        return {**self.grant, "expiresAt": (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat()}
    def test_actual_stdin_grant_cli_saves_only_bound_fields_privately(self):
        grant = {**self.fresh_grant(), "ignoredSecret": "another-canary-not-retained"}
        run, output = self.grant_stdin_cli(json.dumps(grant).encode() + b"\n")
        self.assertEqual(run.returncode, 0, run.stderr)
        safe_output = json.loads(run.stdout)
        self.assertEqual(safe_output["saved"], True)
        self.assertEqual(safe_output["uploadId"], UPLOAD_ID)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        saved = w.read_json(output)
        self.assertEqual(saved["token"], TOKEN)
        self.assertEqual(set(saved), {"uploadId", "manifestDigest", "target", "uploadUrl", "headerName", "token", "expiresAt"})
        self.assertNotIn(b"another-canary", output.read_bytes())
    def test_actual_stdin_grant_cli_rejects_wrong_binding_malformed_and_oversize(self):
        wrong = {**self.fresh_grant(), "target": {**TARGET, "branch": "different"}}
        for index, (raw, expected) in enumerate([
            (json.dumps(wrong).encode() + b"\n", "E_GRANT_BINDING"),
            (b'{invalid-json-' + TOKEN.encode() + b"\n", "E_INPUT"),
            ((b"x" * (w.MAX_GRANT_LINE_BYTES + 1)) + b"\n", "E_GRANT_STDIN_SIZE"),
            (json.dumps(self.fresh_grant()).encode(), "E_GRANT_STDIN_LINE"),
        ]):
            with self.subTest(expected=expected):
                output = self.root / ("denied-grant-%d.json" % index)
                run, _ = self.grant_stdin_cli(raw, output)
                self.assertEqual(run.returncode, 1)
                self.assertEqual(json.loads(run.stdout)["errorCode"], expected)
                self.assertFalse(output.exists())
    def secure_pty_cli(self, raw, output):
        import pty
        import termios
        master, slave = pty.openpty()
        original = termios.tcgetattr(slave)
        bundle = self.root / "pty-bundle.json"
        w.write_json(bundle, self.bundle)
        process = subprocess.Popen([sys.executable, str(Path(w.__file__)), "receive-grant", "--bundle", str(bundle),
                                    "--output", str(output)], stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        captured = bytearray()
        try:
            # No input is sent until the helper proves its echo-off setup finished.
            for _ in range(4):
                ready, _, _ = select.select([master], [], [], 1)
                self.assertTrue(ready, "READY handshake timed out")
                captured.extend(os.read(master, 65536))
                if b"READY_FOR_GRANT" in captured:
                    break
            self.assertIn(b"READY_FOR_GRANT", captured)
            current = termios.tcgetattr(slave)
            self.assertFalse(current[3] & (termios.ECHO | termios.ECHONL | termios.ICANON))
            pending = memoryview(raw)
            while pending:
                pending = pending[os.write(master, pending):]
            process.wait(timeout=3)
            while select.select([master], [], [], 0.05)[0]:
                captured.extend(os.read(master, 65536))
            self.assertEqual(termios.tcgetattr(slave), original)
            self.assertNotIn(TOKEN.encode(), captured)
            return process.returncode, bytes(captured)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
            os.close(slave)
    @unittest.skipUnless(os.name == "posix", "POSIX termios required")
    def test_secure_pty_grant_cli_no_echo_above_canonical_limit(self):
        grant = {**self.fresh_grant(), "ignoredPadding": "x" * 7000}
        output = self.root / "pty-grant.json"
        code, text = self.secure_pty_cli(json.dumps(grant).encode() + b"\n", output)
        self.assertEqual(code, 0, text)
        self.assertIn(b'"saved": true', text)
        self.assertEqual(w.read_json(output)["token"], TOKEN)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertNotIn("ignoredPadding", w.read_json(output))
    @unittest.skipUnless(os.name == "posix", "POSIX termios required")
    def test_secure_pty_grant_cli_restores_modes_on_invalid_input(self):
        output = self.root / "pty-denied.json"
        code, text = self.secure_pty_cli(b'{invalid-json-' + TOKEN.encode() + b"\n", output)
        self.assertEqual(code, 1)
        self.assertIn(b'"errorCode": "E_INPUT"', text)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
