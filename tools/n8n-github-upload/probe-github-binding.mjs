import { readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const REPOSITORY = 'markmalina/automations';
export const ENVIRONMENT = 'n8n-upload-readonly';
export const ENDPOINT = 'https://api.github.com/repos/' + REPOSITORY + '/environments/' + ENVIRONMENT;
const OWNER = '23397294', REPOSITORY_ID = '1448151721';
const sha = value => typeof value === 'string' && /^[0-9a-f]{40}$/u.test(value);
const number = value => typeof value === 'string' && /^[1-9][0-9]{0,19}$/u.test(value);
class DiagnosticError extends Error { constructor(code) { super(code); this.code = code; } }
const fail = code => { throw new DiagnosticError(code); };

export function admitCaller(env, event, now) {
  if (env.GITHUB_REPOSITORY !== REPOSITORY || env.GITHUB_REPOSITORY_ID !== REPOSITORY_ID ||
      env.GITHUB_ACTOR_ID !== OWNER || env.GITHUB_REF !== 'refs/heads/main' || env.GITHUB_RUN_ATTEMPT !== '1' ||
      !number(env.GITHUB_RUN_ID) || !sha(env.GITHUB_SHA) || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA ||
      env.GITHUB_EVENT_NAME !== 'issue_comment' ||
      env.GITHUB_WORKFLOW_REF !== REPOSITORY + '/.github/workflows/ops-n8n-binding-check.yml@refs/heads/main' ||
      event.action !== 'created' || String(event.sender?.id) !== OWNER ||
      event.repository?.full_name !== REPOSITORY || String(event.repository?.id) !== REPOSITORY_ID ||
      event.repository?.default_branch !== 'main' || event.issue?.number !== 1 || event.issue?.pull_request ||
      String(event.comment?.user?.id) !== OWNER || !number(String(event.comment?.id ?? '')) ||
      event.comment?.body !== '/n8n-ops binding-check' || event.comment.created_at !== event.comment.updated_at) fail('E_CALLER');
  const created = Date.parse(event.comment.created_at);
  if (!Number.isSafeInteger(now) || !Number.isSafeInteger(created) || created > now || now - created > 300000) fail('E_REQUEST_EXPIRED');
}

export async function probeBinding({ env, event }, { fetchFn = fetch, clock = () => Date.now() } = {}) {
  const receipt = { schemaVersion: 'agent-ops.n8n-binding-diagnostic/v1', repository: REPOSITORY,
    protectedEnvironment: ENVIRONMENT, result: 'ABORTED', errorCode: 'E_INPUT', observedAt: null,
    clientCommit: null, runId: null, commentId: null, githubMetadataHttpStatus: null,
    environmentObserved: false, requiredReviewersConfigured: null, preventSelfReview: null,
    adminsCanBypass: null, branchRestrictionMode: 'unknown', credentialPresent: null,
    railwayScopeAccepted: false, githubMetadataRequestAttempts: 0, railwayReads: 0, railwayWrites: 0, configurationChanged: false };
  try {
    const observedAt = clock();
    admitCaller(env, event, observedAt);
    Object.assign(receipt, { observedAt, clientCommit: env.GITHUB_SHA, runId: env.GITHUB_RUN_ID, commentId: String(event.comment.id) });
    // Only the job's ephemeral read-only token. No repository/Environment secret
    // or Railway credential is read, named dynamically, requested or provisioned.
    const token = env.BINDING_GITHUB_TOKEN;
    if (typeof token !== 'string' || token.length < 20 || token.length > 4096 || /\s/u.test(token)) fail('E_GITHUB_TOKEN_MISSING');
    receipt.githubMetadataRequestAttempts=1;
    let response;
    try { response = await fetchFn(ENDPOINT, { method: 'GET', redirect: 'error', signal: AbortSignal.timeout(15000),
      headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' } }); }
    catch { fail('E_GITHUB_METADATA_NETWORK'); }
    receipt.githubMetadataHttpStatus = response.status;
    if ([401, 403].includes(response.status)) fail('E_GITHUB_ENVIRONMENT_READ_DENIED');
    // 404 may conceal an access restriction; never infer that a secret is absent.
    if (response.status === 404) fail('E_PROTECTED_ENVIRONMENT_NOT_OBSERVED');
    if (response.status !== 200 || !response.body) fail('E_GITHUB_METADATA_API');
    const length = response.headers.get('content-length');
    if (length !== null && (!/^\d+$/u.test(length) || Number(length) > 65536)) fail('E_GITHUB_METADATA_SIZE');
    let count = 0; const chunks = [];
    try {
      for await (const chunk of response.body) { count += chunk.length; if (count > 65536) fail('E_GITHUB_METADATA_SIZE'); chunks.push(Buffer.from(chunk)); }
    } catch (error) { if (error instanceof DiagnosticError) throw error; fail('E_GITHUB_METADATA_NETWORK'); }
    let data; try { data = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { fail('E_GITHUB_METADATA_SHAPE'); }
    if (data.name !== ENVIRONMENT || data.url !== ENDPOINT || !Number.isSafeInteger(data.id) || data.id < 1 ||
        !Array.isArray(data.protection_rules)) fail('E_GITHUB_METADATA_SHAPE');
    const reviewers = data.protection_rules.filter(r => r.type === 'required_reviewers');
    if (reviewers.length > 1 || (reviewers.length && !Array.isArray(reviewers[0].reviewers))) fail('E_GITHUB_METADATA_SHAPE');
    const policy = data.deployment_branch_policy;
    let mode = 'unknown';
    if (policy === null) mode = 'unrestricted';
    else if (policy && typeof policy.protected_branches === 'boolean' && typeof policy.custom_branch_policies === 'boolean') {
      if (policy.protected_branches && !policy.custom_branch_policies) mode = 'protected-branches';
      else if (!policy.protected_branches && policy.custom_branch_policies) mode = 'custom';
      else fail('E_GITHUB_METADATA_SHAPE');
    }
    return { ...receipt, result: 'OBSERVED_NOT_ACCEPTED', errorCode: 'E_PROTECTED_BINDING_ACCEPTANCE_PENDING',
      environmentObserved: true, requiredReviewersConfigured: reviewers.length > 0 && reviewers[0].reviewers.length > 0,
      preventSelfReview: reviewers.length && typeof reviewers[0].prevent_self_review === 'boolean' ? reviewers[0].prevent_self_review : null,
      adminsCanBypass: typeof data.can_admins_bypass === 'boolean' ? data.can_admins_bypass : null, branchRestrictionMode: mode };
  } catch (error) { return { ...receipt, errorCode: error instanceof DiagnosticError ? error.code : 'E_INPUT' }; }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  let result;
  try {
    const raw = readFileSync(process.env.GITHUB_EVENT_PATH);
    if (raw.length > 1048576) fail('E_INPUT');
    result = await probeBinding({ env: process.env, event: JSON.parse(raw) });
  } catch { result = { schemaVersion: 'agent-ops.n8n-binding-diagnostic/v1', result: 'ABORTED', errorCode: 'E_INPUT', configurationChanged: false }; }
  writeFileSync('n8n-binding-diagnostic.json', JSON.stringify(result, null, 2) + '\n', { mode: 0o600 });
  process.stdout.write(JSON.stringify(result) + '\n');
  if (result.result === 'ABORTED') process.exitCode = 1;
}
