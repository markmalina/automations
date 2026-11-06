# Runtime observation proposal — Ops 434

This is a separate runtime-source proposal based on the retention fix
d1abb31147db3d0bd1f7ffbec0c1b6dbffbfeb67. It is not selected by the existing Ops
candidate, not deployed and not substituted into the rejected staged patch.
No Railway variable, deadline, resource, credential, workflow or journal is
changed by publishing this source. The existing source lock remains intact.

The bootstrap now takes two read-only SQLite snapshots around its existing
cleanup/startup sequence. It hashes all upload/grant rows inside a read
transaction, includes the previously failed upload in preservation checks and
emits only before/after aggregate digests and safe booleans. Missing/malformed/
symlink journals yield UNAVAILABLE without initialization. Measurement failures
do not replace cleanup policy or make missing data appear preserved.

A single UPLOAD_OPS_OBSERVATION_V1 JSON line reports exact Railway resource and
deployment IDs, decoded bootstrap source hash, hash of the actual installed
ledger file, explicit persistent flag, actual statfs available bytes, journal
digest equality and checked cleanup outcomes. No environment dump, source body,
manifest, receipt, grant, private key or journal row appears in this evidence.
Runtime IDs use documented Railway-injected variables:
https://docs.railway.com/variables/reference

The phase is POST_CLEANUP, before the final n8n child starts. It does not claim
HTTP readiness. Its disk measurement has its own observedAt timestamp; a later
collector must not relabel it as a current measurement. No monitoring interval,
new HTTP endpoint, signal handler, signing key or extra background process is
added. Existing absolute pilot deadline and persistent child-exit behavior remain.

Local checks: 10 runtime-observation tests PASS; existing retention verification
PASS (including preservation of uncertain/local-commit rows and safety refusals);
existing bootstrap/watchdog checks PASS; Node syntax PASS. Tests execute real
read-only temporary SQLite databases and isolated bootstrap helper code, not
the n8n service or provider. They do not establish live capability/acceptance.

The Ops collector proposal reads exact-deployment logs plus scoped provider
state and public health, rejecting drift/stale/unknown evidence. It deliberately
returns OBSERVED_NOT_ACCEPTED. Logs alone do not authenticate which process
emitted a line; trusted source/configuration and log provenance must still be
independently accepted. This record is not the existing verifier's VERIFIED
observation schema. Source adoption, protocol review and live native acceptance
remain mandatory, and no accepted source hash is silently updated here.

The failed upload ID remains 9d94bcf3-9a28-4014-93d5-ce8e5d259c7d. No recovery,
retry, journal reset or deletion of a new clone is introduced.

Task: https://github.com/markmalina/ops/issues/434
Client task: https://github.com/markmalina/automations/issues/1
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
