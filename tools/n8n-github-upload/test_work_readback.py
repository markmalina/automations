import base64
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import select
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import work_readback as r
import work_upload as w

COMMIT, ROOT, SUBTREE = "a" * 40, "b" * 40, "c" * 40
CANARY = "private-canary-never-print-0123456789"
TARGET = {"repositoryId": 1448151721, "repository": "markmalina/automations",
          "branch": "main", "prefix": "данные с пробелом"}


def blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class ReadbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raws = {"тест %.bin": bytes(range(256)) + b"\0\xff" + CANARY.encode(), "пустой.txt": b""}
        mappings = []
        for index, (path, raw) in enumerate(self.raws.items()):
            local = self.root / str(index)
            local.write_bytes(raw)
            mappings.append({"source": str(local), "path": path})
        self.bundle = w.prepare(TARGET, mappings, "11111111-1111-4111-8111-111111111111")
        manifest = self.bundle["manifest"]
        self.receipt = {"success": True, "uploadId": manifest["uploadId"],
                        "repository": TARGET["repository"], "branch": "main", "commitSha": COMMIT,
                        "url": "https://github.com/markmalina/automations/commit/" + COMMIT,
                        "fileCount": 2, "totalBytes": sum(map(len, self.raws.values())),
                        "files": [{"path": TARGET["prefix"] + "/" + f["path"],
                                   "sha256": f["sha256"], "bytes": f["bytes"]} for f in manifest["files"]]}
        self.calls = []

    def fetch(self, request):
        self.calls.append(copy.deepcopy(request))
        self.assertEqual(request["repository"], TARGET["repository"])
        kind = request["kind"]
        if kind == "repository":
            return {"id": TARGET["repositoryId"], "full_name": TARGET["repository"],
                    "owner": {"id": 23397294, "login": "markmalina"}}
        if kind == "commit":
            self.assertEqual(request["sha"], COMMIT)
            return {"sha": COMMIT, "tree": {"sha": ROOT}}
        if kind == "tree":
            if request["sha"] == ROOT:
                entries = [{"path": TARGET["prefix"], "type": "tree", "mode": "040000", "sha": SUBTREE}]
            else:
                self.assertEqual(request["sha"], SUBTREE)
                entries = [{"path": p, "type": "blob", "mode": "100644", "sha": blob_sha(v), "size": len(v)}
                           for p, v in self.raws.items()]
            return {"sha": request["sha"], "truncated": False, "tree": entries}
        self.assertEqual(kind, "file")
        self.assertEqual(request["ref"], COMMIT)
        prefix = TARGET["prefix"] + "/"
        self.assertTrue(request["path"].startswith(prefix))
        raw = self.raws[request["path"][len(prefix):]]
        return {"sha": blob_sha(raw), "content": base64.encodebytes(raw).decode(), "encoding": "base64",
                "display_url": "https://untrusted.invalid/" + CANARY}

    def altered(self, kind, mutate):
        def fetch(request):
            data = self.fetch(request)
            return mutate(data) if request["kind"] == kind else data
        return fetch

    def assert_failure(self, status, code, fetch=None, receipt=None):
        result = r.verify(self.bundle, receipt or self.receipt, fetch or self.fetch)
        self.assertEqual(result["status"], status, result)
        self.assertEqual(result["errorCode"], code, result)
        self.assertNotIn(CANARY, json.dumps(result))
        return result

    def test_actual_binary_unicode_prefix_percent_and_zero_file(self):
        result = r.verify(self.bundle, self.receipt, self.fetch)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["verifiedFiles"], 2)
        self.assertNotIn(CANARY, json.dumps(result))
        self.assertEqual(sum(c["kind"] == "tree" for c in self.calls), 2)

    def test_branch_movement_ignored_exact_commit_used_for_all_reads(self):
        receipt = {**self.receipt, "branchTip": "d" * 40}
        result = r.verify(self.bundle, receipt, self.fetch)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertFalse(any("branch" in c or "url" in c for c in self.calls))

    def test_invalid_receipt_and_bundle_never_call_connector(self):
        for key, value in [("repository", "markmalina/other"), ("url", "https://evil.invalid/" + CANARY),
                           ("commitSha", "main"), ("files", [])]:
            with self.subTest(key=key):
                self.assert_failure("UNAVAILABLE", "E_INPUT_BINDING", receipt={**self.receipt, key: value})
        bundle = copy.deepcopy(self.bundle)
        bundle["digest"] = "0" * 64
        self.assertEqual(r.verify(bundle, self.receipt, self.fetch)["status"], "UNAVAILABLE")
        self.assertEqual(self.calls, [])

    def test_wrong_remote_repo_and_commit(self):
        self.assert_failure("MISMATCH", "E_REMOTE_REPOSITORY", self.altered("repository", lambda d: {**d, "id": 1}))
        self.assert_failure("MISMATCH", "E_REMOTE_COMMIT", self.altered("commit", lambda d: {**d, "sha": "d" * 40}))

    def test_wrong_remote_owner(self):
        self.assert_failure("MISMATCH", "E_REMOTE_REPOSITORY", self.altered("repository", lambda d: {**d, "owner": {"id": 1}}))

    def test_missing_path(self):
        self.assert_failure("MISMATCH", "E_REMOTE_PATH", self.altered("tree", lambda d: {**d, "tree": []}))

    def test_symlink_submodule_and_wrong_blob_mode_rejected(self):
        for mode in ("120000", "160000", "100755"):
            def mutate(d):
                if d["sha"] == SUBTREE:
                    d["tree"][0]["mode"] = mode
                return d
            self.assert_failure("MISMATCH", "E_REMOTE_PATH_TYPE", self.altered("tree", mutate))

    def test_corrupted_bytes_same_size_and_different_size(self):
        for raw, code in [(b"x" * len(self.raws["тест %.bin"]), "E_REMOTE_DIGEST"), (b"", "E_REMOTE_SIZE")]:
            self.assert_failure("MISMATCH", code, self.altered("file", lambda d: {**d, "content": base64.b64encode(raw).decode()}))

    def test_blob_identity_recomputed_from_actual_bytes(self):
        def mutate(d):
            if d["sha"] == SUBTREE:
                d["tree"][0]["sha"] = "e" * 40
            return d
        tree_fetch = self.altered("tree", mutate)
        def fetch(q):
            d = tree_fetch(q)
            if q["kind"] == "file":
                d["sha"] = "e" * 40
            return d
        self.assert_failure("MISMATCH", "E_REMOTE_BLOB", fetch)

    def test_wrong_file_sha_rejected(self):
        self.assert_failure("MISMATCH", "E_REMOTE_BLOB", self.altered("file", lambda d: {**d, "sha": "f" * 40}))

    def test_invalid_base64_utf8_fallback_and_oversize_denied(self):
        self.assert_failure("UNAVAILABLE", "E_REMOTE_ENCODING", self.altered("file", lambda d: {**d, "content": "%%%"}))
        self.assert_failure("UNAVAILABLE", "E_REMOTE_ENCODING", self.altered("file", lambda d: {**d, "encoding": "utf-8"}))
        self.assert_failure("MISMATCH", "E_REMOTE_SIZE", self.altered("file", lambda d: {**d, "content": "A" * 10000}))

    def test_truncated_duplicate_and_wrong_tree_fail(self):
        self.assert_failure("UNAVAILABLE", "E_TREE_TRUNCATED", self.altered("tree", lambda d: {**d, "truncated": True}))
        self.assert_failure("MISMATCH", "E_REMOTE_TREE", self.altered("tree", lambda d: {**d, "sha": "f" * 40}))
        self.assert_failure("UNAVAILABLE", "E_REMOTE_SHAPE", self.altered("tree", lambda d: {**d, "tree": d["tree"] * 2}))

    def test_provider_exception_never_echoed(self):
        def fetch(q):
            raise OSError(CANARY)
        self.assert_failure("UNAVAILABLE", "E_READBACK_UNAVAILABLE", fetch)

    def test_total_budget_is_checked_after_fetch(self):
        clock = iter([0, 0, 121])
        result = r.verify(self.bundle, self.receipt, self.fetch, lambda: next(clock))
        self.assertEqual(result["errorCode"], "E_READBACK_TIMEOUT")

    def test_bridge_errors_timeout_redirect_access_incomplete_and_sequence(self):
        for response, expected in [({"sequence": 1, "ok": False, "error": "redirect", "body": CANARY}, "E_REDIRECT_DENIED"),
                                   ({"sequence": 1, "ok": False, "error": "timeout"}, "E_READBACK_TIMEOUT"),
                                   ({"sequence": 1, "ok": False, "error": "access"}, "E_READBACK_ACCESS"),
                                   ({"sequence": 2, "ok": True, "data": {}}, "E_READBACK_SEQUENCE")]:
            read, write = os.pipe()
            try:
                os.write(write, json.dumps(response).encode() + b"\n")
                with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(r.ReadbackError) as error:
                    r.StdinConnector(read)({"kind": "repository", "repository": TARGET["repository"]})
                self.assertEqual(error.exception.code, expected)
                self.assertNotIn(CANARY, output.getvalue())
            finally:
                os.close(read); os.close(write)
        read, write = os.pipe()
        os.close(write)
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(r.ReadbackError) as error:
                r.StdinConnector(read)({"kind": "repository"})
            self.assertEqual(error.exception.code, "E_READBACK_INCOMPLETE")
        finally:
            os.close(read)

    def test_bridge_actual_wait_timeout_is_bounded(self):
        read, write = os.pipe()
        try:
            with patch.object(r, "RESPONSE_SECONDS", 0.01), contextlib.redirect_stdout(io.StringIO()), self.assertRaises(r.ReadbackError) as error:
                r.StdinConnector(read)({"kind": "repository"})
            self.assertEqual(error.exception.code, "E_READBACK_TIMEOUT")
        finally:
            os.close(read); os.close(write)

    def test_cli_pipe_actual_protocol_and_private_report_no_payload(self):
        self.run_cli(False)

    def test_cli_fifo_input_is_rejected_without_writer_or_connector(self):
        fifo = self.root / "fifo"
        os.mkfifo(fifo)
        result = subprocess.run([sys.executable, str(Path(r.__file__)), "--bundle", str(fifo),
                                 "--receipt", str(self.root / "missing"), "--output", str(self.root / "result")],
                                capture_output=True, timeout=2)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b"READBACK_REQUEST", result.stdout)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_input_files_are_bounded_and_symlink_denied(self):
        file = self.root / "large"
        file.write_bytes(b"x" * 1_048_577)
        with self.assertRaises(r.ReadbackError):
            r.read_input(file)
        link = self.root / "link"
        link.symlink_to(file)
        with self.assertRaises(w.UploadError):
            r.read_input(link)

    @unittest.skipUnless(os.name == "posix", "PTY required")
    def test_cli_pty_actual_protocol_restores_modes_and_no_echo(self):
        self.run_cli(True)

    def run_cli(self, tty):
        bundle, receipt, output = [self.root / n for n in ("bundle.json", "receipt.json", "readback.json")]
        w.write_json(bundle, self.bundle); w.write_json(receipt, self.receipt)
        command = [sys.executable, str(Path(r.__file__)), "--bundle", str(bundle), "--receipt", str(receipt), "--output", str(output)]
        master = slave = None
        if tty:
            import pty, termios
            master, slave = pty.openpty()
            original = termios.tcgetattr(slave)
            process = subprocess.Popen(command, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        captured = bytearray()
        try:
            for _ in range(12):
                self.assertTrue(select.select([process.stdout], [], [], 3)[0], "protocol deadline")
                line = process.stdout.readline()
                captured.extend(line)
                if line.startswith(b"READBACK_REQUEST "):
                    request = json.loads(line[len(b"READBACK_REQUEST "):])
                    sequence = request.pop("sequence")
                    payload = json.dumps({"sequence": sequence, "ok": True, "data": self.fetch(request)}).encode() + b"\n"
                    if tty:
                        self.assertFalse(termios.tcgetattr(slave)[3] & termios.ECHO)
                        os.write(master, payload)
                    else:
                        process.stdin.write(payload); process.stdin.flush()
                if line.startswith(b"READBACK_RESULT "):
                    break
            process.wait(timeout=3)
            self.assertEqual(process.returncode, 0, process.stderr.read())
            self.assertNotIn(CANARY.encode(), captured)
            self.assertEqual(w.read_json(output)["status"], "VERIFIED")
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
            if tty:
                self.assertEqual(termios.tcgetattr(slave), original)
                while select.select([master], [], [], 0.01)[0]:
                    captured.extend(os.read(master, 65536))
                self.assertNotIn(CANARY.encode(), captured)
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            for handle in (process.stdin, process.stdout, process.stderr):
                if handle:
                    handle.close()
            for descriptor in (master, slave):
                if descriptor is not None:
                    os.close(descriptor)


if __name__ == "__main__":
    unittest.main()
