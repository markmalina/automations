import { createHash } from 'node:crypto';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const centralCommit = '6e8598bddf7b33a9cda65efab878fff994048176';
const acceptedHelperHash = 'f825b933429bece9472315d485234cc218fa6438af33b74a7422ed84d4d95aab';
const acceptedProfileHash = 'e024d2e7987bee01624cfca60ae56483c65f0b759cc9ba77919e7b84de2018cd';
const root = new URL('./', import.meta.url);
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

export function verifySource({ read = path => readFileSync(new URL(path, root)) } = {}) {
  const lock = JSON.parse(read('ops-scope.lock.json'));
  if (lock.schemaVersion !== 'agent-ops.n8n-scope-lock/v1' ||
      lock.centralRepository !== 'markmalina/ops' || lock.centralCommit !== centralCommit ||
      !/^[a-f0-9]{40}$/u.test(lock.centralCommit) ||
      lock.helperPath !== 'agent-ops/n8n-upload/scope-probe.mjs' ||
      lock.profilePath !== 'agent-ops/registry/targets/n8n-upload-scope-read-v1.json' ||
      lock.helperSha256 !== acceptedHelperHash || lock.profileSha256 !== acceptedProfileHash ||
      !/^[a-f0-9]{64}$/u.test(lock.helperSha256) || !/^[a-f0-9]{64}$/u.test(lock.profileSha256) ||
      Object.keys(lock).length !== 7) throw new Error('E_SOURCE_LOCK');
  if (sha256(read('ops-scope-probe.mjs')) !== lock.helperSha256 ||
      sha256(read('ops-scope-profile.json')) !== lock.profileSha256) throw new Error('E_SOURCE_DIGEST');
  return lock;
}

async function runVerified(lock, { load = () => import('./ops-scope-probe.mjs') } = {}) {
  const probe = await load();
  if (typeof probe.runCli !== 'function') throw new Error('E_SOURCE_ENTRY');
  return probe.runCli({ centralRepository: lock.centralRepository, centralCommit: lock.centralCommit,
    helperSha256: lock.helperSha256, profileSha256: lock.profileSha256 });
}

export async function verifyAndRun({ read, load } = {}) {
  return runVerified(verifySource({ read }), { load });
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  let sourceVerified = false;
  try {
    const lock = verifySource();
    sourceVerified = true;
    await runVerified(lock);
  }
  catch {
    const receipt = { schemaVersion: 'agent-ops.n8n-scope/v1', result: 'ABORTED',
      errorCode: sourceVerified ? 'E_SCOPE_EXECUTION_UNKNOWN' : 'E_SOURCE_NOT_ACCEPTED',
      providerRead: sourceVerified ? null : false, mutationCount: 0 };
    // An output failure may happen after the provider read. Preserve any receipt
    // already written by the verified reader; never relabel it as no provider call.
    if (!sourceVerified || !existsSync('n8n-scope-receipt.json')) {
      writeFileSync('n8n-scope-receipt.json', JSON.stringify(receipt) + '\n', { mode: 0o600 });
    }
    process.stdout.write(JSON.stringify(receipt) + '\n');
    process.exitCode = 1;
  }
}
