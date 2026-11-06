// Reviewed narrow read capability only. No mutation release or deploy authority.
import { readFileSync, writeFileSync, appendFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const TARGET = Object.freeze({
  projectId: '69cc90c9-7ede-4a57-bc03-f3e63f01cca3',
  environmentId: '369d5bb9-5107-4e39-89d8-668b9b59e230',
  serviceId: '2425a11a-90bd-47fe-9c5b-03ad96ee7a74',
});
export const QUERY = `query N8nOpsScope($environmentId:String!,$serviceId:String!) {
  projectToken { projectId environmentId }
  serviceInstance(environmentId:$environmentId,serviceId:$serviceId) {
    serviceId environmentId latestDeployment { id status deploymentStopped }
  }
}`;
const REPOSITORY = 'markmalina/automations', OWNER = '23397294', REPOSITORY_ID = '1448151721';
const WORKFLOW = REPOSITORY + '/.github/workflows/ops-n8n-inspect.yml@refs/heads/main';
const number = value => typeof value === 'string' && /^[1-9][0-9]{0,19}$/u.test(value);
const sha = value => typeof value === 'string' && /^[a-f0-9]{40}$/u.test(value);
const uuid = value => typeof value === 'string' && /^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/u.test(value);
class ProbeError extends Error { constructor(code) { super(code); this.code = code; } }
const fail = code => { throw new ProbeError(code); };

export function admitCaller(env, event, now) {
  if (env.GITHUB_ACTIONS !== 'true' || env.GITHUB_REPOSITORY !== REPOSITORY ||
      env.GITHUB_REPOSITORY_ID !== REPOSITORY_ID || env.GITHUB_ACTOR_ID !== OWNER ||
      env.GITHUB_REF !== 'refs/heads/main' || env.GITHUB_RUN_ATTEMPT !== '1' ||
      env.GITHUB_EVENT_NAME !== 'issue_comment' || !number(env.GITHUB_RUN_ID) ||
      !sha(env.GITHUB_SHA) || env.GITHUB_WORKFLOW_SHA !== env.GITHUB_SHA ||
      env.GITHUB_WORKFLOW_REF !== WORKFLOW || event.action !== 'created' ||
      String(event.sender?.id) !== OWNER || event.repository?.full_name !== REPOSITORY ||
      String(event.repository?.id) !== REPOSITORY_ID || event.repository?.default_branch !== 'main' ||
      event.issue?.number !== 1 || event.issue?.pull_request ||
      String(event.comment?.user?.id) !== OWNER || !number(String(event.comment?.id ?? '')) ||
      event.comment?.body !== '/n8n-ops inspect' ||
      event.comment.created_at !== event.comment.updated_at) fail('E_CALLER');
  const created = Date.parse(event.comment.created_at);
  if (!Number.isSafeInteger(now) || !Number.isSafeInteger(created) || created > now || now - created > 300000) fail('E_REQUEST_EXPIRED');
}

function initialReceipt() {
  return { schemaVersion: 'agent-ops.n8n-scope/v1', targetId: 'n8n-upload-scope-read-v1',
    target: { ...TARGET }, repository: REPOSITORY, result: 'ABORTED', errorCode: 'E_INPUT',
    centralRepository: null, centralCommit: null, helperSha256: null, profileSha256: null,
    allowed: false, observedAt: null, clientCommit: null, workflowRef: null, runId: null, commentId: null,
    providerRead: false, providerRequestAttempts: 0, providerHttpStatus: null, providerErrorCodes: [],
    providerValidationFields: [], mutationCount: 0, scopeAccepted: false, nativeCapabilityAccepted: false,
    deploymentId: null, deploymentStatus: null, deploymentStopped: null,
    availableDiskBytes: null, persistent: null, journalPreserved: null };
}

const ERROR_CODES = new Set(['INTERNAL_SERVER_ERROR', 'UNAUTHENTICATED', 'FORBIDDEN', 'BAD_USER_INPUT',
  'GRAPHQL_PARSE_FAILED', 'GRAPHQL_VALIDATION_FAILED', 'NOT_FOUND']);
const QUERY_FIELDS = new Set(['projectToken', 'projectId', 'id', 'serviceInstance',
  'serviceId', 'environmentId', 'latestDeployment', 'status', 'deploymentStopped']);
function diagnostics(errors, receipt) {
  for (const error of errors.slice(0, 4)) {
    const code = error?.extensions?.code;
    receipt.providerErrorCodes.push(ERROR_CODES.has(code) ? code : 'UNKNOWN');
    const field = typeof error?.message === 'string' &&
      error.message.match(/^Cannot query field "([A-Za-z_][A-Za-z0-9_]{0,63})" on type "[A-Za-z_][A-Za-z0-9_]{0,63}"\.$/u)?.[1];
    if (QUERY_FIELDS.has(field)) receipt.providerValidationFields.push(field);
  }
}

async function boundedJson(response) {
  if (!response.body) fail('E_PROVIDER_SHAPE');
  const size = response.headers.get('content-length');
  if (size !== null && (!/^\d+$/u.test(size) || Number(size) > 65536)) fail('E_PROVIDER_SIZE');
  const reader = response.body.getReader();
  let length = 0; const chunks = [];
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > 65536) { await reader.cancel(); fail('E_PROVIDER_SIZE'); }
      chunks.push(Buffer.from(value));
    }
  } catch (error) { if (error instanceof ProbeError) throw error; fail('E_PROVIDER_NETWORK'); }
  let body; try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch { fail('E_PROVIDER_SHAPE'); }
  if (!body || typeof body !== 'object' || Array.isArray(body)) fail('E_PROVIDER_SHAPE');
  return body;
}

export async function collectScope({ env, event, mode = 'collect' }, { fetchFn = fetch, clock = () => Date.now() } = {}) {
  const receipt = initialReceipt();
  try {
    if (!['admit', 'collect'].includes(mode)) fail('E_INPUT');
    const now = clock(); admitCaller(env, event, now);
    Object.assign(receipt, { observedAt: now, clientCommit: env.GITHUB_SHA, workflowRef: env.GITHUB_WORKFLOW_REF,
      runId: env.GITHUB_RUN_ID, commentId: String(event.comment.id) });
    if (mode === 'admit') return { ...receipt, result: 'ADMITTED_READ_ONLY', errorCode: null, allowed: true };
    // The first access to the provider secret is strictly after caller admission.
    const token = env.N8N_UPLOAD_RAILWAY_PROJECT_TOKEN;
    if (typeof token !== 'string' || token.length < 20 || token.length > 512 || /\s/u.test(token)) fail('E_TOKEN_MISSING');
    receipt.providerRead = true; receipt.providerRequestAttempts = 1;
    let response;
    try {
      response = await fetchFn('https://backboard.railway.com/graphql/v2', { method: 'POST', redirect: 'error',
        signal: AbortSignal.timeout(15000), headers: { 'Content-Type': 'application/json', 'Project-Access-Token': token },
        body: JSON.stringify({ query: QUERY, variables: { environmentId: TARGET.environmentId, serviceId: TARGET.serviceId } }) });
    } catch { fail('E_PROVIDER_NETWORK'); }
    receipt.providerHttpStatus = response.status;
    if ([401, 403].includes(response.status)) fail('E_TOKEN_SCOPE');
    if (!response.ok && response.status !== 400) fail('E_PROVIDER_HTTP');
    const body = await boundedJson(response);
    if (body.errors !== undefined) {
      if (!Array.isArray(body.errors) || body.errors.length === 0) fail('E_PROVIDER_SHAPE');
      diagnostics(body.errors, receipt); fail('E_PROVIDER_GRAPHQL');
    }
    if (!response.ok) fail('E_PROVIDER_HTTP');
    const data = body.data;
    if (!data || typeof data !== 'object' || Array.isArray(data)) fail('E_PROVIDER_SHAPE');
    if (data.projectToken?.projectId !== TARGET.projectId ||
        data.projectToken?.environmentId !== TARGET.environmentId) fail('E_TOKEN_SCOPE');
    if (data.serviceInstance?.serviceId !== TARGET.serviceId ||
        data.serviceInstance?.environmentId !== TARGET.environmentId) fail('E_TARGET');
    const deployment = data.serviceInstance.latestDeployment;
    if (!deployment || !uuid(deployment.id) ||
        !['SUCCESS', 'FAILED', 'CRASHED', 'REMOVED', 'SLEEPING', 'QUEUED', 'BUILDING', 'DEPLOYING',
          'WAITING', 'INITIALIZING', 'NEEDS_APPROVAL', 'REMOVING', 'SKIPPED'].includes(deployment.status) ||
        typeof deployment.deploymentStopped !== 'boolean') fail('E_PROVIDER_SHAPE');
    return { ...receipt, result: 'OBSERVED_NOT_ACCEPTED', errorCode: 'E_LIVE_ACCEPTANCE_PENDING',
      scopeAccepted: true, deploymentId: deployment.id, deploymentStatus: deployment.status,
      deploymentStopped: deployment.deploymentStopped };
  } catch (error) {
    return { ...receipt, errorCode: error instanceof ProbeError ? error.code : 'E_INPUT' };
  }
}

export async function runCli(provenance) {
  let result;
  let acceptedProvenance;
  try {
    if (provenance !== undefined) {
      if (!provenance || typeof provenance !== 'object' || Array.isArray(provenance) ||
          Object.keys(provenance).sort().join(',') !== 'centralCommit,centralRepository,helperSha256,profileSha256' ||
          provenance.centralRepository !== 'markmalina/ops' || !sha(provenance.centralCommit) ||
          typeof provenance.helperSha256 !== 'string' || !/^[a-f0-9]{64}$/u.test(provenance.helperSha256) ||
          typeof provenance.profileSha256 !== 'string' || !/^[a-f0-9]{64}$/u.test(provenance.profileSha256)) fail('E_PROVENANCE');
      acceptedProvenance = { centralRepository: provenance.centralRepository, centralCommit: provenance.centralCommit,
        helperSha256: provenance.helperSha256, profileSha256: provenance.profileSha256 };
    }
    if (!['admit', 'collect'].includes(process.env.N8N_SCOPE_MODE)) fail('E_INPUT');
    const raw = readFileSync(process.env.GITHUB_EVENT_PATH);
    if (raw.length > 1048576) fail('E_INPUT');
    result = await collectScope({ env: process.env, event: JSON.parse(raw), mode: process.env.N8N_SCOPE_MODE });
  } catch (error) { result = { ...initialReceipt(), errorCode: error instanceof ProbeError ? error.code : 'E_INPUT' }; }
  if (acceptedProvenance) Object.assign(result, acceptedProvenance);
  writeFileSync('n8n-scope-receipt.json', JSON.stringify(result, null, 2) + '\n', { mode: 0o600 });
  if (process.env.GITHUB_OUTPUT) appendFileSync(process.env.GITHUB_OUTPUT, 'allowed=' + (result.allowed === true) + '\n');
  process.stdout.write(JSON.stringify(result) + '\n');
  if (result.result === 'ABORTED') process.exitCode = 1;
  return result;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) await runCli();
