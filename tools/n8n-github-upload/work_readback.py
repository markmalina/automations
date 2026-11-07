#!/usr/bin/env python3
"""Read-only exact-commit verification over the existing Work GitHub connector.

The caller services READBACK_REQUEST lines using connected GitHub tools, then
sends one bounded JSON response over protected stdin. No URLs or auth are input.
"""
import argparse
import base64
import binascii
import hashlib
import json
import os
import select
import sys
import time

import work_upload as upload

MAX_LINE = 44_000_000
MAX_CALLS = 1000
TOTAL_SECONDS = 120
RESPONSE_SECONDS = 20


class ReadbackError(Exception):
    def __init__(self, status, code):
        self.status, self.code = status, code


def reject(code, status="UNAVAILABLE"):
    raise ReadbackError(status, code)


def sha(value):
    return isinstance(value, str) and upload.SHA40.fullmatch(value) is not None


def verify(bundle, receipt, fetch, clock=time.monotonic):
    """fetch(request) returns provider data, never receipt-supplied destinations.

    Requests are repository, commit, tree (immutable SHA), and file (exact ref).
    Transport failures must raise ReadbackError; arbitrary exceptions are never
    included in reports. A fake fetch proves verifier logic only.
    """
    report = {"schemaVersion": "work-readback/v1", "status": "UNAVAILABLE",
              "fileCount": 0, "verifiedFiles": 0}
    try:
        manifest, total = upload.bundle_valid(bundle)
        bound = upload.receipt_valid(receipt, manifest, total)
        target = manifest["target"]
        repo, commit = target["repository"], bound["commitSha"]
        report.update(repository=repo, commitSha=commit, url=bound["url"],
                      fileCount=len(manifest["files"]))
        deadline, calls = clock() + TOTAL_SECONDS, 0

        def get(kind, **fields):
            nonlocal calls
            calls += 1
            if calls > MAX_CALLS or clock() >= deadline:
                reject("E_READBACK_LIMIT")
            value = fetch({"kind": kind, "repository": repo, **fields})
            if clock() >= deadline:
                reject("E_READBACK_TIMEOUT")
            if not isinstance(value, dict):
                reject("E_REMOTE_SHAPE")
            return value

        identity = get("repository")
        if (type(identity.get("id")) is not int or identity["id"] != target["repositoryId"]
                or identity.get("full_name") != repo
                or identity.get("owner", {}).get("id") != 23397294
                or identity.get("owner", {}).get("login") != "markmalina"):
            reject("E_REMOTE_REPOSITORY", "MISMATCH")
        remote = get("commit", sha=commit)
        if remote.get("sha") != commit:
            reject("E_REMOTE_COMMIT", "MISMATCH")
        root = remote.get("tree", {}).get("sha")
        if not sha(root):
            reject("E_REMOTE_SHAPE")
        trees = {}

        def tree(tree_sha):
            if tree_sha not in trees:
                data = get("tree", sha=tree_sha)
                if data.get("sha") != tree_sha:
                    reject("E_REMOTE_TREE", "MISMATCH")
                if data.get("truncated") is not False:
                    reject("E_TREE_TRUNCATED")
                entries = data.get("tree")
                if not isinstance(entries, list) or len(entries) > 100_000:
                    reject("E_REMOTE_SHAPE")
                index = {}
                for entry in entries:
                    if (not isinstance(entry, dict) or not isinstance(entry.get("path"), str)
                            or "/" in entry["path"] or entry["path"] in index):
                        reject("E_REMOTE_SHAPE")
                    index[entry["path"]] = entry
                trees[tree_sha] = index
            return trees[tree_sha]

        for item in manifest["files"]:
            path = "/".join(p for p in (target["prefix"], item["path"]) if p)
            parts, current = path.split("/"), root
            entry = None
            for position, component in enumerate(parts):
                entry = tree(current).get(component)
                if entry is None:
                    reject("E_REMOTE_PATH", "MISMATCH")
                final = position == len(parts) - 1
                if (entry.get("type") != ("blob" if final else "tree")
                        or entry.get("mode") != ("100644" if final else "040000")
                        or not sha(entry.get("sha"))):
                    reject("E_REMOTE_PATH_TYPE", "MISMATCH")
                current = entry["sha"]
            data = get("file", ref=commit, path=path)
            if data.get("sha") != entry["sha"]:
                reject("E_REMOTE_BLOB", "MISMATCH")
            encoded = data.get("content")
            if data.get("encoding") != "base64" or not isinstance(encoded, str):
                reject("E_REMOTE_ENCODING")
            # Only GitHub's line wrapping is accepted; no arbitrary whitespace.
            if len(encoded) > ((item["bytes"] + 2) // 3) * 4 + item["bytes"] // 30 + 16:
                reject("E_REMOTE_SIZE", "MISMATCH")
            try:
                raw = base64.b64decode(encoded.replace("\n", "").replace("\r", ""), validate=True)
            except (ValueError, binascii.Error):
                reject("E_REMOTE_ENCODING")
            if len(raw) != item["bytes"]:
                reject("E_REMOTE_SIZE", "MISMATCH")
            if "size" in entry and (type(entry["size"]) is not int or entry["size"] != len(raw)):
                reject("E_REMOTE_SIZE", "MISMATCH")
            if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                reject("E_REMOTE_DIGEST", "MISMATCH")
            git_blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()
            if git_blob != entry["sha"]:
                reject("E_REMOTE_BLOB", "MISMATCH")
            report["verifiedFiles"] += 1
        report["status"] = "VERIFIED"
    except ReadbackError as error:
        report.update(status=error.status, errorCode=error.code)
    except upload.UploadError:
        report["errorCode"] = "E_INPUT_BINDING"
    except (OSError, TimeoutError):
        report["errorCode"] = "E_READBACK_UNAVAILABLE"
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
        report["errorCode"] = "E_REMOTE_SHAPE"
    return report


class StdinConnector:
    """One response for each request, no shell commands or remote URLs accepted."""
    def __init__(self, descriptor):
        self.descriptor = descriptor
        self.pending = bytearray()
        self.sequence = 0

    def __call__(self, request):
        self.sequence += 1
        print("READBACK_REQUEST " + json.dumps({"sequence": self.sequence, **request}, ensure_ascii=False), flush=True)
        deadline = time.monotonic() + RESPONSE_SECONDS
        while b"\n" not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.descriptor], [], [], remaining)[0]:
                reject("E_READBACK_TIMEOUT")
            chunk = os.read(self.descriptor, min(65536, MAX_LINE + 1 - len(self.pending)))
            if not chunk:
                reject("E_READBACK_INCOMPLETE")
            self.pending.extend(chunk)
            if len(self.pending) > MAX_LINE:
                reject("E_READBACK_RESPONSE_SIZE")
        line, _, rest = self.pending.partition(b"\n")
        self.pending = bytearray(rest)
        try:
            response = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            reject("E_READBACK_RESPONSE_SHAPE")
        if not isinstance(response, dict) or response.get("sequence") != self.sequence:
            reject("E_READBACK_SEQUENCE")
        if response.get("ok") is not True:
            codes = {"timeout": "E_READBACK_TIMEOUT", "redirect": "E_REDIRECT_DENIED",
                     "access": "E_READBACK_ACCESS", "unavailable": "E_READBACK_UNAVAILABLE"}
            reject(codes.get(response.get("error"), "E_READBACK_UNAVAILABLE"))
        if set(response) != {"sequence", "ok", "data"}:
            reject("E_READBACK_RESPONSE_SHAPE")
        return response["data"]


def read_input(path):
    # Reuse the client's nonblocking ordinary-file opener: FIFO/symlink input
    # must not stall the verifier before the connector deadline starts.
    with upload.open_source(os.path.abspath(path)) as handle:
        raw = handle.read(1_048_577)
    if len(raw) > 1_048_576:
        reject("E_INPUT_SIZE")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        bundle, receipt = read_input(args.bundle), read_input(args.receipt)
        # Validate before starting the bridge or printing metadata requests.
        manifest, total = upload.bundle_valid(bundle)
        upload.receipt_valid(receipt, manifest, total)
        with upload.secure_grant_input() as stream:
            result = verify(bundle, receipt, StdinConnector(stream.fileno()))
        upload.write_json(args.output, result)
    except (upload.UploadError, ReadbackError, OSError, ValueError, TypeError, RecursionError):
        result = {"schemaVersion": "work-readback/v1", "status": "UNAVAILABLE",
                  "fileCount": 0, "verifiedFiles": 0, "errorCode": "E_INPUT_OR_OUTPUT"}
    print("READBACK_RESULT " + json.dumps(result, ensure_ascii=False), flush=True)
    return {"VERIFIED": 0, "MISMATCH": 1, "UNAVAILABLE": 2}[result["status"]]


if __name__ == "__main__":
    sys.exit(main())
