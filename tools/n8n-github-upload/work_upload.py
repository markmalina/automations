#!/usr/bin/env python3
"""Work-side binary transport. No persistent credentials, HTTP server, Git or archive."""
import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import sys
import time
import unicodedata
import uuid
from urllib.parse import unquote, urlsplit
from urllib.request import getproxies_environment, proxy_bypass_environment

URL = "https://n8n-upload-pilot.up.railway.app/webhook/work-owner-repository-upload-v1"
HOST = "n8n-upload-pilot.up.railway.app"
ENDPOINT = "/webhook/work-owner-repository-upload-v1"
MAX_BYTES = 32_000_000
MAX_RESPONSE = 65_536
MAX_MANIFEST_UTF16 = 30_000
MAX_GRANT_LINE_BYTES = 16_384
SOCKET_TIMEOUT_SECONDS = 300
MAX_SAFE = 9_007_199_254_740_991
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
SHA40 = re.compile(r"[a-f0-9]{40}\Z")
UUID = re.compile(r"[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}\Z")


class UploadError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def fail(code):
    raise UploadError(code)


def upload_connection(host, *, timeout, context):
    """Fixed origin over inherited HTTP CONNECT; never fall back after failure."""
    if host != HOST or not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        fail("E_TLS_CONFIG")
    proxies = getproxies_environment()
    if proxy_bypass_environment(HOST + ":443", proxies):
        return http.client.HTTPSConnection(HOST, timeout=timeout, context=context)
    proxy = proxies.get("https", proxies.get("all"))
    if not proxy:
        return http.client.HTTPSConnection(HOST, timeout=timeout, context=context)
    try:
        # urlsplit strips some controls: reject them before parsing.
        if len(proxy) > 8192 or any(ord(c) <= 32 or ord(c) == 127 for c in proxy):
            fail("E_PROXY_CONFIG")
        parsed = urlsplit(proxy)
        if parsed.scheme.lower() != "http":
            fail("E_PROXY_SCHEME")
        if not parsed.hostname or parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            fail("E_PROXY_CONFIG")
        port = parsed.port if parsed.port is not None else 80
        if not 1 <= port <= 65535 or parsed.netloc.endswith(":"):
            fail("E_PROXY_CONFIG")
        headers = {}
        if parsed.username is not None:
            user = unquote(parsed.username, errors="strict")
            password = unquote(parsed.password or "", errors="strict")
            if ":" in user or any(ord(c) < 32 or ord(c) == 127 for c in user + password):
                fail("E_PROXY_CONFIG")
            auth = base64.b64encode((user + ":" + password).encode("utf-8")).decode("ascii")
            headers["Proxy-Authorization"] = "Basic " + auth
        connection = http.client.HTTPSConnection(parsed.hostname, port, timeout=timeout, context=context)
        # HTTPSConnection wraps the tunnel with origin SNI and validates its cert.
        # CONNECT-only headers are never copied into the encrypted origin request.
        connection.set_tunnel(HOST, 443, headers=headers)
        return connection
    except UploadError:
        raise
    except (ValueError, UnicodeError, http.client.HTTPException):
        fail("E_PROXY_CONFIG")


def exact(obj, keys, code="E_INPUT"):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        fail(code)


def integer(value):
    return type(value) is int and 0 <= value <= MAX_SAFE


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError):
        fail("E_INPUT")


def relative(value, allow_empty=False):
    if allow_empty and value == "":
        return value
    if not isinstance(value, str) or not value:
        fail("E_PATH")
    try:
        if len(value.encode("utf-8")) > 2048:
            fail("E_PATH")
    except UnicodeError:
        fail("E_PATH")
    if unicodedata.normalize("NFC", value) != value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        fail("E_PATH")
    if "\\" in value or "," in value or value.startswith("/"):
        fail("E_PATH")
    if any(p in ("", ".", "..") or p.lower() == ".git" or len(p.encode("utf-8")) > 255 for p in value.split("/")):
        fail("E_PATH")
    return value


def target_valid(target):
    exact(target, ("repositoryId", "repository", "branch", "prefix"), "E_TARGET")
    if not integer(target["repositoryId"]) or target["repositoryId"] < 1:
        fail("E_TARGET")
    repo = target["repository"]
    if not isinstance(repo, str) or not re.fullmatch(r"markmalina/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", repo):
        fail("E_TARGET")
    if repo.split("/")[1] in (".", ".."):
        fail("E_TARGET")
    branch = target["branch"]
    if not isinstance(branch, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,199}", branch):
        fail("E_BRANCH")
    if ".." in branch or "//" in branch or branch.endswith(("/", ".")) or branch.upper() == "HEAD":
        fail("E_BRANCH")
    if any(p.startswith(".") or p.lower().endswith(".lock") for p in branch.split("/")):
        fail("E_BRANCH")
    relative(target["prefix"], allow_empty=True)
    if target["prefix"].lower() == ".github/workflows" or target["prefix"].lower().startswith(".github/workflows/"):
        fail("E_WORKFLOWS_PERMISSION")
    return target


def manifest_valid(manifest):
    exact(manifest, ("schemaVersion", "uploadId", "target", "files"), "E_MANIFEST")
    if manifest["schemaVersion"] != "work-upload/v2" or not isinstance(manifest["uploadId"], str) or not UUID.fullmatch(manifest["uploadId"]):
        fail("E_MANIFEST")
    target_valid(manifest["target"])
    files = manifest["files"]
    if not isinstance(files, list) or not 1 <= len(files) <= 100:
        fail("E_LIMIT")
    seen, fields, total = set(), set(), 0
    for item in files:
        exact(item, ("field", "path", "bytes", "sha256"), "E_MANIFEST")
        if not isinstance(item["field"], str) or not re.fullmatch(r"file(?:0|[1-9][0-9]?)", item["field"]) or item["field"] in fields:
            fail("E_MANIFEST")
        fields.add(item["field"])
        relative(item["path"])
        path = "/".join(v for v in (manifest["target"]["prefix"], item["path"]) if v)
        relative(path)
        if path.lower().startswith(".github/workflows/") or path.lower() == ".github/workflows":
            fail("E_WORKFLOWS_PERMISSION")
        folded = path.lower()
        if folded in seen or any(folded.startswith(p + "/") or p.startswith(folded + "/") for p in seen):
            fail("E_PATH_COLLISION")
        seen.add(folded)
        if not integer(item["bytes"]) or not isinstance(item["sha256"], str) or not HEX64.fullmatch(item["sha256"]):
            fail("E_MANIFEST")
        total += item["bytes"]
        if total > MAX_BYTES:
            fail("E_LIMIT")
    if len(canonical(manifest).decode("utf-8").encode("utf-16-le")) // 2 > MAX_MANIFEST_UTF16:
        fail("E_MANIFEST_TOO_LARGE")
    return total


def read_json(path, maximum=1_048_576):
    try:
        with open(path, "rb") as handle:
            raw = handle.read(maximum + 1)
        if len(raw) > maximum:
            fail("E_INPUT_SIZE")
        return json.loads(raw.decode("utf-8"))
    except UploadError:
        raise
    except (OSError, ValueError, UnicodeError):
        fail("E_INPUT")


def write_json(path, value):
    # Exclusive temporary file, restrictive mode, then atomic replacement. Never
    # follow a pre-existing destination symlink while writing a grant/receipt.
    destination = Path(path)
    temporary = destination.with_name(destination.name + ".tmp-" + secrets.token_hex(8))
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8") + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except (OSError, ValueError, UnicodeError):
        fail("E_OUTPUT")
    finally:
        with contextlib.suppress(OSError):
            temporary.unlink()


def open_source(source):
    if not isinstance(source, str) or not Path(source).is_absolute() or "\x00" in source:
        fail("E_SOURCE")
    try:
        initial = os.lstat(source)
        if stat.S_ISLNK(initial.st_mode):
            fail("E_SOURCE_SYMLINK")
        if not stat.S_ISREG(initial.st_mode):
            fail("E_SOURCE")
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        handle = os.fdopen(descriptor, "rb")
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            handle.close()
            fail("E_SOURCE")
        if (initial.st_dev, initial.st_ino) != (info.st_dev, info.st_ino):
            handle.close()
            fail("E_SOURCE_CHANGED")
        return handle
    except UploadError:
        raise
    except OSError:
        fail("E_SOURCE")


def describe(handle):
    before = os.fstat(handle.fileno())
    if before.st_size > MAX_BYTES:
        fail("E_LIMIT")
    digest, length = hashlib.sha256(), 0
    for chunk in iter(lambda: handle.read(65_536), b""):
        length += len(chunk)
        if length > MAX_BYTES:
            fail("E_LIMIT")
        digest.update(chunk)
    after = os.fstat(handle.fileno())
    if before.st_size != length or before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
        fail("E_SOURCE_CHANGED")
    handle.seek(0)
    return length, digest.hexdigest()


def prepare(target, mappings, upload_id=None):
    target_valid(target)
    if not isinstance(mappings, list) or not 1 <= len(mappings) <= 100:
        fail("E_LIMIT")
    manifest = {"schemaVersion": "work-upload/v2", "uploadId": upload_id if upload_id is not None else str(uuid.uuid4()),
                "target": dict(target), "files": []}
    sources = {}
    for index, mapping in enumerate(mappings):
        exact(mapping, ("source", "path"))
        relative(mapping["path"])
        with open_source(mapping["source"]) as handle:
            size, digest = describe(handle)
        field = "file" + str(index)
        sources[field] = mapping["source"]
        manifest["files"].append({"field": field, "path": mapping["path"], "bytes": size, "sha256": digest})
    total = manifest_valid(manifest)
    digest = hashlib.sha256(canonical(manifest)).hexdigest()
    return {"manifest": manifest, "sources": sources, "digest": digest,
            "grantRequest": {"id": manifest["uploadId"], "digest": digest,
                             "fileCount": len(manifest["files"]), "totalBytes": total, "target": dict(target)}}


def bundle_valid(bundle):
    exact(bundle, ("manifest", "sources", "digest", "grantRequest"), "E_BUNDLE")
    manifest = bundle["manifest"]
    total = manifest_valid(manifest)
    digest = hashlib.sha256(canonical(manifest)).hexdigest()
    if bundle["digest"] != digest or bundle["grantRequest"] != {
        "id": manifest["uploadId"], "digest": digest, "fileCount": len(manifest["files"]),
        "totalBytes": total, "target": manifest["target"],
    }:
        fail("E_BUNDLE_BINDING")
    if not isinstance(bundle["sources"], dict) or set(bundle["sources"]) != {f["field"] for f in manifest["files"]}:
        fail("E_BUNDLE")
    return manifest, total


def grant_valid(grant, bundle, now=None):
    if not isinstance(grant, dict):
        fail("E_GRANT")
    target_valid(grant.get("target"))
    if grant.get("uploadId") != bundle["manifest"]["uploadId"] or grant.get("manifestDigest") != bundle["digest"] or grant.get("target") != bundle["manifest"]["target"]:
        fail("E_GRANT_BINDING")
    if grant.get("uploadUrl") != URL or grant.get("headerName") != "X-Work-Upload-Grant":
        fail("E_GRANT_URL")
    token = grant.get("token")
    if not isinstance(token, str) or not HEX64.fullmatch(token):
        fail("E_GRANT")
    try:
        expires = dt.datetime.fromisoformat(grant["expiresAt"].replace("Z", "+00:00"))
        if expires.utcoffset() is None:
            fail("E_GRANT_EXPIRY")
        seconds = expires.timestamp() - (time.time() if now is None else now)
        if not 0 < seconds <= 900:
            fail("E_GRANT_EXPIRY")
    except UploadError:
        raise
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
        fail("E_GRANT_EXPIRY")
    return token


def receipt_valid(value, manifest, total):
    if not isinstance(value, dict) or value.get("success") is not True:
        fail("E_UPLOAD_NOT_CONFIRMED")
    target = manifest["target"]
    manifest_digest = hashlib.sha256(canonical(manifest)).hexdigest()
    if "manifestDigest" in value and value["manifestDigest"] != manifest_digest:
        fail("E_RECEIPT_BINDING")
    if type(value.get("fileCount")) is not int or type(value.get("totalBytes")) is not int:
        fail("E_RECEIPT_BINDING")
    if any(value.get(key) != expected for key, expected in {
        "uploadId": manifest["uploadId"], "repository": target["repository"], "branch": target["branch"],
        "fileCount": len(manifest["files"]), "totalBytes": total,
    }.items()):
        fail("E_RECEIPT_BINDING")
    if "repositoryId" in value and (type(value["repositoryId"]) is not int or value["repositoryId"] != target["repositoryId"]):
        fail("E_RECEIPT_BINDING")
    sha = value.get("commitSha")
    if not isinstance(sha, str) or not SHA40.fullmatch(sha) or value.get("url") != "https://github.com/" + target["repository"] + "/commit/" + sha:
        fail("E_RECEIPT_BINDING")
    expected_files = [{"path": "/".join(p for p in (target["prefix"], f["path"]) if p),
                       "sha256": f["sha256"], "bytes": f["bytes"]} for f in manifest["files"]]
    files = value.get("files")
    if not isinstance(files, list) or len(files) != len(expected_files):
        fail("E_RECEIPT_BINDING")
    actual = []
    for item in files:
        if not isinstance(item, dict) or type(item.get("bytes")) is not int:
            fail("E_RECEIPT_BINDING")
        actual.append({key: item.get(key) for key in ("path", "sha256", "bytes")})
    if sorted(actual, key=lambda f: str(f["path"])) != sorted(expected_files, key=lambda f: f["path"]):
        fail("E_RECEIPT_BINDING")
    safe = {key: value[key] for key in ("success", "uploadId", "repository", "branch", "fileCount", "totalBytes", "commitSha", "url")}
    safe["files"] = expected_files
    safe["repositoryId"] = target["repositoryId"]
    safe["manifestDigest"] = manifest_digest
    if type(value.get("replayed")) is bool:
        safe["replayed"] = value["replayed"]
    return safe


def upload(bundle, grant, connection_factory=None, now=None):
    manifest, total = bundle_valid(bundle)
    token = grant_valid(grant, bundle, now)
    with contextlib.ExitStack() as stack:
        handles = {}
        # Open and verify every file before constructing any network connection.
        for item in manifest["files"]:
            handle = stack.enter_context(open_source(bundle["sources"][item["field"]]))
            size, digest = describe(handle)
            if size != item["bytes"] or digest != item["sha256"]:
                fail("E_SOURCE_CHANGED")
            handles[item["field"]] = handle
        boundary = "workn8n-" + secrets.token_hex(24)
        lead = ("--" + boundary + '\r\nContent-Disposition: form-data; name="manifest"\r\n'
                'Content-Type: application/json\r\n\r\n').encode() + canonical(manifest) + b"\r\n"
        prefixes = [(f, ("--" + boundary + '\r\nContent-Disposition: form-data; name="' + f["field"] +
                        '"; filename="' + f["field"] + '.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode())
                    for f in manifest["files"]]
        end = ("--" + boundary + "--\r\n").encode()
        length = len(lead) + sum(len(header) + f["bytes"] + 2 for f, header in prefixes) + len(end)
        connection = None
        try:
            factory = connection_factory or upload_connection
            try:
                context = ssl.create_default_context()
            except (OSError, ValueError):
                fail("E_TLS_CONFIG")
            connection = factory(HOST, timeout=SOCKET_TIMEOUT_SECONDS, context=context)
            connection.putrequest("POST", ENDPOINT)
            connection.putheader("Content-Type", "multipart/form-data; boundary=" + boundary)
            connection.putheader("Content-Length", str(length))
            connection.putheader("X-Work-Upload-Grant", token)
            connection.endheaders()
            connection.send(lead)
            for item, header in prefixes:
                connection.send(header)
                handle = handles[item["field"]]
                sent = 0
                for chunk in iter(lambda: handle.read(65_536), b""):
                    sent += len(chunk)
                    if sent > item["bytes"]:
                        fail("E_UPLOAD_OUTCOME_UNKNOWN")
                    connection.send(chunk)
                if sent != item["bytes"]:
                    fail("E_UPLOAD_OUTCOME_UNKNOWN")
                connection.send(b"\r\n")
            connection.send(end)
            response = connection.getresponse()
            if 300 <= response.status < 400:
                fail("E_REDIRECT_DENIED")
            if response.status != 200:
                # Do not print provider response text, which may reflect secrets.
                fail("E_UPLOAD_HTTP_" + str(response.status))
            raw = response.read(MAX_RESPONSE + 1)
            if len(raw) > MAX_RESPONSE:
                fail("E_RESPONSE_SIZE")
            try:
                result = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError):
                fail("E_RESPONSE_SHAPE")
            return receipt_valid(result, manifest, total)
        except UploadError:
            raise
        except (OSError, http.client.HTTPException, TimeoutError):
            fail("E_UPLOAD_OUTCOME_UNKNOWN")
        finally:
            if connection is not None:
                with contextlib.suppress(Exception):
                    connection.close()


@contextlib.contextmanager
def secure_grant_input():
    """Pipe by default; an interactive tool must observe READY before sending."""
    if not sys.stdin.isatty():
        yield sys.stdin.buffer
        return
    try:
        import termios
        descriptor = sys.stdin.fileno()
        original = termios.tcgetattr(descriptor)
        secured = [part[:] if isinstance(part, list) else part for part in original]
        secured[3] &= ~(termios.ECHO | termios.ECHONL | termios.ICANON)
        secured[6][termios.VMIN] = 1
        secured[6][termios.VTIME] = 0
        termios.tcsetattr(descriptor, termios.TCSANOW, secured)
    except Exception:
        fail("E_SECURE_STDIN")
    try:
        print("READY_FOR_GRANT", flush=True)
        yield sys.stdin.buffer
    finally:
        try:
            termios.tcsetattr(descriptor, termios.TCSANOW, original)
        except Exception:
            fail("E_SECURE_STDIN")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--target", required=True)
    prep.add_argument("--files", required=True)
    prep.add_argument("--upload-id")
    prep.add_argument("--output", required=True)
    receive = commands.add_parser("receive-grant")
    receive.add_argument("--bundle", required=True)
    receive.add_argument("--output", required=True)
    send = commands.add_parser("upload")
    send.add_argument("--bundle", required=True)
    send.add_argument("--grant", required=True)
    send.add_argument("--receipt", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            bundle = prepare(read_json(args.target), read_json(args.files), args.upload_id)
            write_json(args.output, bundle)
            print(json.dumps({"uploadId": bundle["manifest"]["uploadId"], "manifestDigest": bundle["digest"],
                              "fileCount": len(bundle["manifest"]["files"]),
                              "totalBytes": bundle["grantRequest"]["totalBytes"]}))
        elif args.command == "receive-grant":
            bundle = read_json(args.bundle)
            manifest, _ = bundle_valid(bundle)
            with secure_grant_input() as stream:
                raw = stream.readline(MAX_GRANT_LINE_BYTES + 1)
                if len(raw) > MAX_GRANT_LINE_BYTES:
                    fail("E_GRANT_STDIN_SIZE")
                if not raw.endswith(b"\n"):
                    fail("E_GRANT_STDIN_LINE")
                grant = json.loads(raw.decode("utf-8"))
                grant_valid(grant, bundle)
                safe = {key: grant[key] for key in ("uploadId", "manifestDigest", "target", "uploadUrl",
                                                   "headerName", "token", "expiresAt")}
                write_json(args.output, safe)
            print(json.dumps({"saved": True, "uploadId": manifest["uploadId"], "expiresAt": safe["expiresAt"]}))
        else:
            info = os.stat(args.grant, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                fail("E_GRANT_FILE_MODE")
            bundle, grant = read_json(args.bundle), read_json(args.grant)
            result = upload(bundle, grant)
            write_json(args.receipt, result)
            print(json.dumps(result, ensure_ascii=False))
    except UploadError as error:
        print(json.dumps({"success": False, "errorCode": error.code,
                          "retry": "reuse the same uploadId; do not create a new upload"}))
        return 1
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        print(json.dumps({"success": False, "errorCode": "E_INPUT", "retry": "reuse the same uploadId"}))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
