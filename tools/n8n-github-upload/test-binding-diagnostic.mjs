import assert from 'node:assert/strict';
import test from 'node:test';
import { probeBinding, ENDPOINT, ENVIRONMENT, REPOSITORY } from './probe-github-binding.mjs';
const NOW = 1793992200000, TOKEN = 'read-only-test-canary-1234567890';
function fixture() {
  const env = { GITHUB_REPOSITORY: REPOSITORY, GITHUB_REPOSITORY_ID: '1448151721', GITHUB_ACTOR_ID: '23397294',
    GITHUB_REF: 'refs/heads/main', GITHUB_RUN_ATTEMPT: '1', GITHUB_RUN_ID: '100', GITHUB_SHA: 'a'.repeat(40), GITHUB_WORKFLOW_SHA: 'a'.repeat(40),
    GITHUB_EVENT_NAME: 'issue_comment', GITHUB_WORKFLOW_REF: REPOSITORY + '/.github/workflows/ops-n8n-binding-check.yml@refs/heads/main', BINDING_GITHUB_TOKEN: TOKEN };
  const event = { action: 'created', sender: { id: 23397294 }, repository: { full_name: REPOSITORY, id: 1448151721, default_branch: 'main' },
    issue: { number: 1 }, comment: { id: 200, user: { id: 23397294 }, body: '/n8n-ops binding-check', created_at: new Date(NOW - 1).toISOString(), updated_at: new Date(NOW - 1).toISOString() } };
  const data = { id: 300, name: ENVIRONMENT, url: ENDPOINT, protection_rules: [{ type: 'required_reviewers', reviewers: [{ type: 'User', reviewer: { login: 'private-name', id: 1 } }], prevent_self_review: true }],
    deployment_branch_policy: { protected_branches: false, custom_branch_policies: true }, can_admins_bypass: false };
  let calls = 0;
  const fetchFn = async (url, options) => { calls++; assert.equal(url, ENDPOINT); assert.equal(options.method, 'GET'); assert.equal(options.redirect, 'error'); assert.equal(options.headers.Authorization, 'Bearer ' + TOKEN); return new Response(JSON.stringify(data)); };
  return { env, event, data, fetchFn, get calls() { return calls; }, run() { return probeBinding({ env, event }, { fetchFn, clock: () => NOW }); } };
}
test('fixed read-only metadata observation never becomes credential/provider acceptance', async () => {
  const f = fixture(), r = await f.run();
  assert.equal(r.result, 'OBSERVED_NOT_ACCEPTED'); assert.equal(r.environmentObserved, true); assert.equal(r.requiredReviewersConfigured, true);
  assert.equal(r.preventSelfReview, true); assert.equal(r.adminsCanBypass, false); assert.equal(r.branchRestrictionMode, 'custom');
  assert.equal(r.credentialPresent, null); assert.equal(r.railwayScopeAccepted, false); assert.equal(r.githubMetadataRequestAttempts, 1); assert.equal(r.railwayReads, 0); assert.equal(r.railwayWrites, 0);
  assert.equal(f.calls, 1); assert.ok(!JSON.stringify(r).includes(TOKEN)); assert.ok(!JSON.stringify(r).includes('private-name'));
});
for (const field of ['GITHUB_REPOSITORY', 'GITHUB_REPOSITORY_ID', 'GITHUB_ACTOR_ID', 'GITHUB_REF', 'GITHUB_RUN_ATTEMPT', 'GITHUB_RUN_ID', 'GITHUB_SHA', 'GITHUB_WORKFLOW_SHA', 'GITHUB_EVENT_NAME', 'GITHUB_WORKFLOW_REF'])
test('wrong caller stops before token/API: ' + field, async () => {
  const f = fixture(); f.env[field] = 'wrong'; Object.defineProperty(f.env, 'BINDING_GITHUB_TOKEN', { get() { assert.fail('token read'); } });
  const r = await f.run(); assert.equal(r.errorCode, 'E_CALLER'); assert.equal(f.calls, 0);
});
test('edited/foreign/stale comments cannot start a metadata request', async () => {
  for (const change of [f => f.event.action = 'edited', f => f.event.comment.updated_at = new Date(NOW).toISOString(),
    f => f.event.comment.user.id = 1, f => f.event.issue.number = 2, f => f.event.issue.pull_request = {},
    f => f.event.comment.body += '\n', f => f.event.comment.created_at = f.event.comment.updated_at = new Date(NOW - 300001).toISOString()]) {
    const f = fixture(); change(f); const r = await f.run(); assert.equal(r.result, 'ABORTED'); assert.equal(f.calls, 0);
  }
});
for (const [status, code] of [[401, 'E_GITHUB_ENVIRONMENT_READ_DENIED'], [403, 'E_GITHUB_ENVIRONMENT_READ_DENIED'], [404, 'E_PROTECTED_ENVIRONMENT_NOT_OBSERVED'], [500, 'E_GITHUB_METADATA_API']])
test('non-success HTTP preserves unknown bindings: ' + status, async () => {
  const f = fixture(); const r = await probeBinding(f, { clock: () => NOW, fetchFn: async () => new Response('private-error-' + TOKEN, { status }) });
  assert.equal(r.errorCode, code); assert.equal(r.githubMetadataHttpStatus, status); assert.equal(r.environmentObserved, false); assert.equal(r.credentialPresent, null); assert.ok(!JSON.stringify(r).includes(TOKEN));
});
test('missing token, network failure and malformed/oversized replies are redacted', async () => {
  const f = fixture(); delete f.env.BINDING_GITHUB_TOKEN; assert.equal((await f.run()).errorCode, 'E_GITHUB_TOKEN_MISSING'); assert.equal(f.calls, 0);
  f.env.BINDING_GITHUB_TOKEN = TOKEN;
  for (const fetchFn of [async () => { throw Error(TOKEN); }, async () => new Response(TOKEN),
    async () => new Response('x'.repeat(65537)), async () => new Response('{}', { headers: { 'content-length': '999999' } })]) {
    const r = await probeBinding(f, { clock: () => NOW, fetchFn }); assert.equal(r.result, 'ABORTED'); assert.ok(!JSON.stringify(r).includes(TOKEN));
  }
});
test('foreign or partial Environment shape never implies accepted protection', async () => {
  for (const change of [f => f.data.name = 'foreign', f => f.data.url = 'https://evil.invalid/', f => delete f.data.protection_rules,
    f => f.data.protection_rules[0].reviewers = null, f => f.data.deployment_branch_policy.protected_branches = true]) {
    const f = fixture(); change(f); const r = await f.run(); assert.equal(r.errorCode, 'E_GITHUB_METADATA_SHAPE'); assert.equal(r.environmentObserved, false);
  }
});
test('explicit absence of protections is observed without claiming secret absence', async () => {
  const f = fixture(); f.data.protection_rules = []; f.data.deployment_branch_policy = null; delete f.data.can_admins_bypass;
  const r = await f.run(); assert.equal(r.requiredReviewersConfigured, false); assert.equal(r.branchRestrictionMode, 'unrestricted'); assert.equal(r.adminsCanBypass, null); assert.equal(r.credentialPresent, null);
});
