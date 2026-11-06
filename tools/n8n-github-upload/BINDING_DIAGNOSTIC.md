# Protected binding metadata diagnostic

Exact owner command on Automations issue1: `/n8n-ops binding-check`.
This separate project-owned workflow observes only the metadata of the fixed
`markmalina/automations` Environment `n8n-upload-readonly`, using the job's
ephemeral GITHUB_TOKEN with contents/read, issues/read and actions/read.

No job declares an Environment, so it cannot create one as a side effect. No
repository/Environment secret or Railway credential is accessed. Only one fixed
GitHub GET is permitted; no generic selectors, writes, provisioning, deployment,
secrets listing, approval, Railway request or LLM call exists. Exact owner/repo/
main/workflow/first-attempt/original-comment checks precede the token lookup.

The receipt contains booleans and stable metadata/error codes; it never contains
raw API bodies, reviewer identities, error text or token values. A 404 does not
establish secret absence. A 200 is OBSERVED_NOT_ACCEPTED: credentialPresent is
unknown and railwayScopeAccepted=false. Existing Ops releases stay disabled.

GitHub documents the Environment GET as an Actions/read operation:
https://docs.github.com/en/rest/deployments/environments#get-an-environment
https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens#repository-permissions-for-actions

Local verification: `node --test tools/n8n-github-upload/test-binding-diagnostic.mjs`.
This source is a narrow diagnostic, separate from unmerged Ops/client/runtime
candidates. Installing/running it does not apply or remove the prior rejected
Railway STAGED patch, extend the expired timer, change upload destinations or
reset failed upload9d94bcf3-9a28-4014-93d5-ce8e5d259c7d or its journal.

Task: https://github.com/markmalina/ops/issues/434
Client: https://github.com/markmalina/automations/issues/1
Rules: https://github.com/markmalina/ai/blob/main/WORK-RULES.md
