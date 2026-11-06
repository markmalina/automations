import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { verifySource, verifyAndRun } from './verify-scope-source.mjs';

const read = name => readFileSync(new URL(name, import.meta.url));
const changeLock = change => name => name === 'ops-scope.lock.json'
  ? Buffer.from(JSON.stringify(change(JSON.parse(read(name))))) : read(name);

test('accepted exact Ops source verifies without any network or credential lookup', () => {
  assert.equal(verifySource().centralRepository, 'markmalina/ops');
});
for (const [key, value] of [
  ['centralRepository', 'another/ops'], ['centralCommit', '0'.repeat(40)],
  ['helperPath', '../other.mjs'], ['profilePath', 'another.json'],
  ['helperSha256', '0'.repeat(64)], ['profileSha256', '0'.repeat(64)],
  ['schemaVersion', 'another/v1'], ['unexpected', true],
]) {
  test('source admission rejects lock alteration: ' + key, () => {
    assert.throws(() => verifySource({ read: changeLock(lock => ({ ...lock, [key]: value })) }), /E_SOURCE_LOCK/u);
  });
}
for (const path of ['ops-scope-probe.mjs', 'ops-scope-profile.json']) {
  test('source hash rejects altered ' + path + ' before loading code', async () => {
    let loaded = false;
    await assert.rejects(verifyAndRun({
      read: name => name === path ? Buffer.concat([read(name), Buffer.from('\nchanged')]) : read(name),
      load: async () => { loaded = true; throw new Error('must not load'); },
    }), /E_SOURCE_DIGEST/u);
    assert.equal(loaded, false);
  });
}
test('verified module receives immutable central provenance once', async () => {
  let called = 0;
  const result = await verifyAndRun({ load: async () => ({ runCli: async provenance => {
    called++;
    assert.deepEqual(provenance, {
      centralRepository: 'markmalina/ops', centralCommit: verifySource().centralCommit,
      helperSha256: verifySource().helperSha256, profileSha256: verifySource().profileSha256,
    });
    return 'ok';
  } }) });
  assert.equal(called, 1);
  assert.equal(result, 'ok');
});
