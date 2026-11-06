# Universal repository upload: source candidate

The existing OAuth grant workflow ID `workUploadGrantPilot`, header credential
and GitHub App JWT credential `workPilotGithubJwt` are retained. The grant
accepts optional `target` for v2 and remains `availableInMCP:true`. Legacy grant
and binary endpoints/rows remain usable as before; the new binary endpoint is
`/webhook/work-owner-repository-upload-v1`, workflow ID
`workOwnerRepositoryUploadV1`, not exposed in MCP.

V2 manifest: `{schemaVersion:"work-upload/v2",uploadId,target,files}`.
Target: `{repositoryId,repository:"markmalina/name",branch,prefix}`. Branch must
already exist. File shape: `{field,path,bytes,sha256}`. At most100 files and
32,000,000 total binary bytes; manifest JSON text at most30,000 UTF16 codeunits
to bound the shell-quoted metadata argument. Prefix is a relative directory
without trailing slash, or empty; paths are NFC relative POSIX paths. Current
App permissions are contents-only, so `.github/workflows` is rejected early as
`E_WORKFLOWS_PERMISSION`; no new permissions are silently requested.

The35 stock n8n nodes validate metadata, binary SHA256 and actual lengths
before any GitHub request, authenticate the grant/target in the existing
SQLite journal, mint a repository-restricted installation token, verify
immutable owner23397294 and repository ID/name, then use the Git Data API.
Each file becomes a blob, one bundle tree and one commit are created, the
commit SHA is journaled before publishing the branch with `force:false`, and
ancestry of that exact SHA is checked before confirming the receipt. No full
clone/history or payload file writes occur. This removes clone disk growth
with repository history; it does not establish memory/throughput acceptance.

Binary bytes reach n8n as multipart parts. Base64 is an internal n8n-to-GitHub
Git Data API transformation only; it never enters MCP or model messages. The
binary workflow disables saving success/error/manual execution payloads.
Modes of existing files are explicitly written as100644; executable-mode
preservation is not implemented in this candidate.

Replay of a recorded commit skips blobs/tree/commit and branch mutation. It
only confirms if the same commit is already reachable from the requested
branch. A recorded-but-unpublished commit or remote conflict returns
`REMOTE_NOT_CONFIRMED` and retains the journal; there is no automatic new ID,
second commit, forced push or protection bypass. A pre-commit claimed row from
another execution remains uncertain and requires explicit recovery.

`build_universal_workflow.py` deterministically generates the two JSON exports.
`test_universal_workflow.mjs` runs47 offline tests against actual Code-node
snippets and graph structure, including100file metadata, binary hashes/sizes,
foreign targets/token scopes, path collisions, journal-before-ref ordering,
non-force branch update and exact-commit replay receipt. No provider/network
calls or credentials were used for these tests.

Native n8n import/execution and live GitHub API compatibility remain UNTESTED.
Parent attempted n8n best-practices/SDK reference; both failed with MCP-32603
Internal error while the live service is stopped. The JSON uses existing
exported stock-node patterns; local snippet/graph tests do not substitute for
native validation. Actual100files/30MB memory, disk lifecycle, speed, OAuth and
restart/lost-response acceptance remain pending. Existing failed upload ID
`9d94bcf3-9a28-4014-93d5-ce8e5d259c7d` is not touched by this source preparation.


Privacy hardening: a stock CryptoV2 text SHA256 node hashes the incoming grant
before the metadata bridge. Universal ExecuteCommand uses only
`claim-granted-hash` with `grantHash`; the raw grant is absent from command
arguments. Legacy workflow/protocol remains unchanged. The new internal ledger
action must be V2-only and validate that hash against the stored token hash.

Binary reading/encoding occurs in a Code node whose INPUT still has binary
references, then stock Crypto hashes those same references. This is deliberate:
CryptoV2 removes processed binary output; the subsequent Code node only checks
actualBytes/hash and does not rely on restoring a remote worker's binary input.

Blob POSTs use the stock HTTP Request batching collection with batchSize1 and
batchInterval1000ms, retryOnFail:false. This paces one workflow's mutative
requests; concurrent/global GitHub secondary rate limits remain unproven and
need operational acceptance. A100file batch may take more than100seconds plus
network time; the Work HTTP timeout must account for that.

Verified primary source parameter definitions/implementation at the installed
`n8n@2.46.6` tag:
- CryptoV2 text hashing parameters `binaryData:false`, `value`, `type:SHA256`,
  `encoding:hex`, `dataPropertyName`: blob
  `2803b34e73d569cee4818cbc31839c8c7b76ebe8` in
  https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/nodes-base/nodes/Crypto/v2/CryptoV2.node.ts
- HTTP Request batching shape `options.batching.batch.{batchSize,batchInterval}`:
  Description blob `b34174e663969ca3336fedeb368e12b2c9ba548a` in
  https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/nodes-base/nodes/HttpRequest/V3/Description.ts
- HTTP Request implementation sleeps between batch boundaries and preserves
  result order through Promise.allSettled; redirects disabled by explicit
  options.redirect.redirect.followRedirects:false. Implementation blob
  `3ecf7913b74b72742dd28d007599a332147b9ee6` in
  https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/nodes-base/nodes/HttpRequest/V3/HttpRequestV3.node.ts

The generator embeds its grant template and has no sibling scratch dependency.
A test copies only the generator to an empty directory and verifies both JSON
exports are byte-identical. This source inspection and47localtests do not claim
native workflow import/execution or live GitHub acceptance.

Binary workflow settings.executionTimeout is300seconds, aligned with the client timeout. Native installed-tag workflow-runner reads workflowSettings.executionTimeout and multiplies it by1000; primary source blob0b44f718ffbbf418e436ba55283837867077ed3d at https://github.com/n8n-io/n8n/blob/n8n%402.46.6/packages/cli/src/workflow-runner.ts . This is source verification, not live deadline acceptance.
