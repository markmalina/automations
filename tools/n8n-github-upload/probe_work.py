"""Diagnostic binary roundtrip to n8n; NOT a GitHub uploader."""
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the authorization header to another URL.


def main():
    url = os.environ.get("N8N_UPLOAD_PROBE_URL", "")
    token = os.environ.get("N8N_UPLOAD_TOKEN", "")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or not token):
        raise SystemExit("Set HTTPS N8N_UPLOAD_PROBE_URL and secret N8N_UPLOAD_TOKEN bindings; no credentials in URL.")
    data = secrets.token_bytes(4096)
    start = time.perf_counter()
    request = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/octet-stream", "X-Work-Upload-Token": token,
    })
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=60) as response:
            status = response.status
            returned = response.read(len(data) + 1)
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"n8n probe failed: HTTP {exc.code}; response body suppressed") from None
    except (urllib.error.URLError, TimeoutError):
        raise SystemExit("n8n probe transport failed; inspect network/TLS configuration without printing secrets") from None
    receipt = {
        "test": "work-n8n-binary-roundtrip", "http_status": status,
        "bytes": len(data), "returned_bytes": len(returned),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "returned_sha256": hashlib.sha256(returned).hexdigest(),
        "match": returned == data, "total_seconds": round(time.perf_counter() - start, 6),
        "github_tested": False,
    }
    print(json.dumps(receipt, ensure_ascii=False))
    if status != 200 or returned != data:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
