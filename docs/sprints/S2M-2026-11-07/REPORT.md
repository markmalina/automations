# #21: multipart manifest client candidate

Worker: `worker-20261107T175437Z-d3cab9545dca`.
Source: `4a96e0eaf3929da934d55f66135e28ab2ce34235`.
Task: https://github.com/markmalina/automations/issues/21
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md

## Source and local evidence

Removed only the manifest part's `Content-Type: application/json` from
`work_upload.upload`. Content-Disposition and canonical JSON remain unchanged;
Content-Length already derives from actual framing. Binary part framing,
TLS/proxy/endpoint behavior, grant/digest/UUID/target/receipt validation, server
workflow and ledger are unchanged.

`test_work_multipart.py` captures the actual upload request through the existing
connection_factory seam. Two tests parse that packet with Python's MIME parser:
manifest is filename-free and MIME-free, exact canonical Unicode JSON; two
binary parts retain their exact contents, lengths and SHA256; total emitted
Content-Length matches. Fake grant/header/body are never logged.

Compared actual packets emitted by baseline and candidate with the same
synthetic inputs. Baseline fails the no-per-part-MIME contract; candidate passes.
Both preserve exact canonical manifest and Content-Length. This comparison uses
Python MIME parsing, **not actual n8n**, and is not native acceptance.

Local checks: 78 Python tests PASS (baseline76 +2), including existing binding,
transport, receipt, secure stdin, ledger and cleanup regressions. Modified
`multipart_parser_probe.cjs` passes `node --check`. Existing literal failure
reproducer remains its default mode. Hosted CI result belongs to the exact PR
head and will be linked in the task receipt; it does not run native n8n.

## Native evidence: UNAVAILABLE, no binary request

The approved existing public cache was present. Exactly one bounded offline
`npm install --save-exact n8n@2.46.6 --offline --ignore-scripts --no-audit --no-fund`
with explicit workspace `--cache` failed with exit1 / `ENOTCACHED`: the public
dependency archive `https://registry.npmjs.org/undici/-/undici-6.29.1.tgz` was not
cached. No second full install was attempted, as required by #21. No usable
native n8n installation resulted. A read-only index check also found no cached
n8n2.46.6 archive entry for a standalone parser check.

Actual n8n2.46.6 parser: **UNAVAILABLE_SETUP_ENOTCACHED**. Native binary/stub/replay:
**NOT_RUN**. No SQLite build, native owner, DB, JWT key, grant, upload UUID,
workflow execution or GitHub stub commit was created in this native attempt.
This is a source candidate, not a verified native fix, not #17 completion and
not real Work→n8n→GitHub acceptance. Prior #17/R2 failure evidence is unchanged.

The opt-in `multipart_parser_probe.cjs <isolated-install-root> --packet` mode is
prepared for a later permitted runtime. It accepts a private stdin frame:
4-byte big-endian metadata length, UTF-8 JSON metadata, actual upload body.
Metadata fields: `contentType`, numeric `contentLength`, canonical manifest
string `manifest`, manifest's `files` array. Do not forward the grant header.
It requires one exact string manifest, precisely the expected file count and
each binary's size/SHA256; temp parser files are cleaned. Only safe result
metadata is printed. This new mode was syntax-checked, not native-executed.

Reproduce the candidate packet check after installing the pinned native runtime
under a separately authorized setup (run from tools/n8n-github-upload):

```python
import json, subprocess
import work_upload as w
from test_work_multipart import capture_packet
body, headers, bundle, _ = capture_packet()
config = dict(contentType=headers['Content-Type'],
              contentLength=int(headers['Content-Length']),
              manifest=w.canonical(bundle['manifest']).decode('utf-8'),
              files=bundle['manifest']['files'])
metadata = json.dumps(config, ensure_ascii=False).encode('utf-8')
frame = len(metadata).to_bytes(4, 'big') + metadata + body
subprocess.run(['node', 'multipart_parser_probe.cjs',
                '/absolute/isolated-install-root', '--packet'],
               input=frame, timeout=20, check=True)
```

For baseline comparison pass a baseline work_upload module to capture_packet;
expect parser exit1 and absent string manifest. Then run the existing
native_binary_probe.py with the candidate client, fresh DB and synthetic-only
environment. Neither a Python test nor a parser PASS substitutes for native
workflow execution or real GitHub bytes readback.

## Cleanup and remaining work

Install process is terminal. Temporary install prefix, downloaded headers,
raw install logs and baseline client copy are removed before terminal handoff.
Public cache retained at
`/workspace/scratch/d3cab9545dca/task17-public-npm-cache`: only `_cacache`,
1,262,203,990 bytes; 3,993 index records, only registry.npmjs.org origins,
zero nonempty auth/cookie fields. Logs/notifier/tmp removed. **Incomplete cache;
do not assume it can install offline.** This path remains an outstanding cleanup
pointer: delete no later than 08.11.2026 00:20 MSK. Availability across Work
environments is not guaranteed.

Controller: review the narrow source candidate; decide a permitted way to
complete native setup and verify parser/binary/replay in #21/#17. Source PR is
not merged by the worker. S1/Railway/live n8n, old failedID/journal, permissions,
resources, production credentials and neighboring projects were not changed.
