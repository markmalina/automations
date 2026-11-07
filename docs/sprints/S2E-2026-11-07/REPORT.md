# #24 — installation jsonBody fixed; native binary/stub/replay PASS

07.11.2026. Worker `worker-20261107T195418Z-d3cab9545dca`.
Task: https://github.com/markmalina/automations/issues/24
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
Baseline main: `c51c4090fcace63a6c1060b0384eb63f528d9c0f`.

**Native two-file upload and same-UUID replay PASS in actual n8n2.46.6 with a
local GitHub stub. Source integration is not ready: one local bootstrap
consistency test fails, and this task forbids modifying bootstrap.**

No real GitHub data-path upload, live n8n change or Railway deployment occurred.
The local stub result is not the user-facing commit URL/remote bytes acceptance.

## Narrow source candidate

The generator and owner-repository-upload export add one space between nested
object closing braces in Issue installation token /nodes/11/parameters/jsonBody.
Parsed workflow comparison proves this is the only changed export parameter.
repository_ids remains exactly [target.repositoryId], permissions exactly
{contents:'write'}. Endpoint/JWT/graph/timeouts/redirect/retry/binding/privacy and
ledger logic remain unchanged. upload-grant export is byte-identical.

The new semantic test evaluates the actual generated expression for two
synthetic repository IDs and deep-compares the complete request object.
It is not advertised as a native syntax check.
The optional native_expression_probe.cjs uses the actual installed native
extendSyntax: baseline1of28 parameters fails (the installation jsonBody);
candidate28of28 pass. No workflow or HTTP execution occurs in that probe.

native_binary_probe.py only adds safe fixture counters and captures existing
execution/version evidence BEFORE stopping n8n. Strict success criteria remain:
two successful executions on the expected version, same receipt commit on
replay, one commit/ref write, zero fixture protocol errors, independent bytes.
Last-node details are not needed for that acceptance and were not claimed.
No post-stop DB read/restart was used to produce the PASS.

All35 baseline tool files were materialized with exact Git blob SHA before
edits (no added LF). Before native, the source directory copied the candidate
workflow and unchanged client/ledger exactly. Unrelated test-generated
pilot-bootstrap changes were restored to exact baseline; they are not included
in the published candidate.

## Native acceptance facts

- One approved online exact n8n2.46.6 ignore-scripts installation, explicit
  existing workspace cache, inherited proxy/CA/TLS; exit0. No offline-first or
  second full install.
- Actual n8n/n8n-nodes-base/CLI2.46.6. Official n8n integrity matched prior record:
  sha512-fzO5VUcyyq1J282QLUNMIUQBUvsjl8XedNOHrHT9X2IQTc6gAFdfc0fFzaeNecWyHP7VYZQIAQa2RfGg5GnzhQ==.
- Node24.22.1; matching official headers checksum
  322e0a27db9088093ab8347bdc8c7e0aaa21dc9ed548390bf06b394494c09267.
  SQLite initially missing binding; one local Debug node-gyp build,
  2jobs/180s timeout, exit0; actual require SQLite3.44.2 PASS.
- Lockv3/2368entries, all resolved URLs public registry.npmjs.org, SHA256
  770ee5c43e4664f235bfaa6e643214b543b3b3ee3c0e3a2e6056f80d626d15e6.
  Package/build logs and temporary lock are private cleanup items, not published.
- Fresh own0700 runtime/DB, synthetic owner/JWT/grant/target/files, loopback stub,
  existing whitelisted runtime env, no real credentials. Only the prior six
  allowed test substitutions: GitHub origins, absolute ledger paths and fake
  JWT credential name. Production export was not rewritten for the stub.
- Actual import/publish; published nodes equal expected candidate test copy.
  Published version: 3d37f383-5a7c-44c6-991c-151bab7fb79e.
- First real local multipart binary request succeeded. Exactly one replay of
  the SAME UUID succeeded with replayed=true and the same receipt commit.
  No further upload UUID or request was created.
- Two files<=16KiB independently compared with source bytes, manifest sizes,
  SHA256 and Git blob SHA against stub storage. filesVerified=2.
- Stub counters: commitWrites=1, refWrites=1, protocolErrors=0.
- Before-stop native execution metadata: id1 success and id2 success, both
  workflowVersionId=3d37f383-5a7c-44c6-991c-151bab7fb79e.
  publishedNodesExact=true; executionMetadataPhase=before-stop.
- Probe outcome=PASS, phase=native-binary, processesStopped=true.
  This is not merely a metadata collector exit0 or readiness check.

The manifest parser regression accepted in #21 was not repeated as a separate
audit. This execution tested the changed expression and complete local native
workflow path. Stub Git tree/commit IDs are synthetic; only blob SHA is an
actual Git object checksum. No real remote GitHub acceptance is claimed.

## Local source check and precise remaining integration boundary

78 Python tests PASS. Node67 total:66 PASS,1 FAIL.
The new semantic request-body test passes, as do all workflow tests.
The only failure is existing test_universal_bootstrap.cjs:
`embedding is reproducible, bounded and matches reviewed JSON files`.
Its generator embeds the workflow export into pilot-bootstrap.cjs. After the
jsonBody source changes, that embedded copy must change too; the test correctly
detects the old embedded export. This is a source integration failure, not a
native failure or a missing user credential.

Issue#24 explicitly forbids bootstrap changes and its allowed paths exclude
pilot-bootstrap.cjs. The worker did not expand the scope. The test-generated
local bootstrap was restored to its exact baseline. Therefore no green full
source suite is claimed.

No PR was opened: its source paths would automatically trigger hosted CI for a
known failing version. No manual hosted CI was requested or rerun. The prepared
code and this report are saved on the separate reviewable branch/commit.
This is an explicit deviation from the requested PR handoff, necessary to honor
both the bootstrap prohibition and the prepare-before-hosted-CI rule. The issue
and queue contain the exact scope gap. The controller can authorize regenerating
only the embedded workflow section, then repeat the failing consistency check,
complete one source CI and open/accept the PR. No new external permission is
needed for that routine source decision; it is not a Railway deployment.

Candidate generator/export/native probes/semantic regression are reviewable;
source/CI/merge/deploy/live remain separate states.
#24 remains open. #17 native evidence awaits controller acceptance; overall
live product/S1 remain incomplete.

## Reproduce

From the repository:
`python tools/n8n-github-upload/build_universal_workflow.py`.
Run existing Node/Python suites and note the bootstrap consistency boundary.
With a separately prepared pinned native install:
`node tools/n8n-github-upload/native_expression_probe.cjs <install-root> <baseline-export> <candidate-export>`.
Then use the existing native_binary_probe.py --root <isolated-root> with
source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json}.
Use candidate export, fresh DB and synthetic-only env; never real credentials.
No workflow/import/binary repeat is needed merely to examine this report.

## Cleanup and cache pointer

Setup finished within15minutes; total worker within30minutes.
All own native/runner/stub/install/build processes stop+wait; own prefix with
DB/keys/grants/fixtures/rawlogs/headers/node_modules removed after evidence
extraction. Terminal receipt records process/absence verification.

Public cache retained:
`/workspace/scratch/d3cab9545dca/task17-public-npm-cache`.
1,302,756,336bytes;4010index records; only registry.npmjs.org origins;
zero nonempty auth/cookie fields; only _cacache, logs/notifier/tmp removed.
Completeness/cross-Work availability are not guaranteed.
**Outstanding deletion deadline08.11.2026 00:20MSK**; carry this pointer in #14
until confirmed deletion. No other cache pointer was introduced.

New hosted runs requested0; provider usage/invoice unavailable. The previous
0.2833 measured runner-minute ledger entry is carried, not a complete total.
Railway/live/S1/permissions/resources/realcredentials/old failedID/journal and
neighboring projects/automations unchanged. No original Deploy retry or bypass.

ДАЛЬШЕ: контроллер — принять native PASS, уточнить разрешение на необходимое
generated bootstrap embedding в той же #24 и завершить source PR/CI приёмку.
