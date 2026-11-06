const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const { DatabaseSync } = require('node:sqlite');
const source = fs.readFileSync(__dirname + '/pilot-bootstrap.cjs', 'utf8');
const helperSource = source.slice(source.indexOf('// OPS_OBSERVATION_START'), source.indexOf('// OPS_OBSERVATION_END'));
const CANARY = 'PRIVATE-token-manifest-receipt-must-not-appear';
const FAILED = '9d94bcf3-9a28-4014-93d5-ce8e5d259c7d';
function helper(fsImpl = fs) {
  const context = { fs: fsImpl, crypto, require, Buffer, process: { env: {} } };
  vm.runInNewContext(helperSource, context, { timeout: 1000 });
  return context;
}
function journal() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'n8n-observe-'));
  const file = path.join(dir, 'uploads.sqlite'); const db = new DatabaseSync(file);
  db.exec('CREATE TABLE uploads (id TEXT,digest TEXT,manifest TEXT,owner TEXT,state TEXT,commit_sha TEXT,receipt TEXT,created_at INTEGER,updated_at INTEGER)');
  db.exec('CREATE TABLE grants (token_hash TEXT,upload_id TEXT,digest TEXT,file_count INTEGER,total_bytes INTEGER,expires_at INTEGER)');
  db.prepare('INSERT INTO uploads VALUES (?,?,?,?,?,?,?,?,?)').run(FAILED,'a'.repeat(64),CANARY,'owner','claimed',null,null,1,1);
  db.prepare('INSERT INTO grants VALUES (?,?,?,?,?,?)').run(CANARY,FAILED,'a'.repeat(64),1,10,100);
  return { dir, file, db, close() { db.close(); fs.rmSync(dir, { recursive: true, force: true }); } };
}
test('journal measurement is read-only, includes uncertain rows and emits no row data', () => {
  const f = journal(); try {
    const h = helper(), before = h.observationJournalSnapshot(f.dir), again = h.observationJournalSnapshot(f.dir);
    assert.equal(before.status, 'OBSERVED'); assert.equal(before.failedUploadPresent, true); assert.equal(before.digest, again.digest);
    assert.ok(!JSON.stringify(before).includes(CANARY));
    assert.equal(f.db.prepare('SELECT state FROM uploads').get().state, 'claimed');
    f.db.prepare("UPDATE uploads SET state='committed',commit_sha=?").run('b'.repeat(40));
    assert.notEqual(h.observationJournalSnapshot(f.dir).digest, before.digest);
    f.db.prepare('DELETE FROM grants').run();
    assert.notEqual(h.observationJournalSnapshot(f.dir).digest, before.digest);
  } finally { f.close(); }
});
test('missing, malformed and symlink journals do not get initialized or accepted', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'n8n-missing-')); try {
    const h = helper(); assert.equal(h.observationJournalSnapshot(dir).status, 'UNAVAILABLE');
    assert.deepEqual(fs.readdirSync(dir), []);
    fs.writeFileSync(path.join(dir, 'uploads.sqlite'), CANARY);
    assert.equal(h.observationJournalSnapshot(dir).status, 'UNAVAILABLE');
    fs.renameSync(path.join(dir, 'uploads.sqlite'), path.join(dir, 'real.sqlite'));
    fs.symlinkSync(path.join(dir, 'real.sqlite'), path.join(dir, 'uploads.sqlite'));
    assert.equal(h.observationJournalSnapshot(dir).status, 'UNAVAILABLE');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});
function evidenceFixture() {
  const env = { RAILWAY_PROJECT_ID: '69cc90c9-7ede-4a57-bc03-f3e63f01cca3', RAILWAY_ENVIRONMENT_ID: '369d5bb9-5107-4e39-89d8-668b9b59e230',
    RAILWAY_SERVICE_ID: '2425a11a-90bd-47fe-9c5b-03ad96ee7a74', RAILWAY_DEPLOYMENT_ID: '17469a53-374f-4c5f-a5d8-beed4c086847',
    UPLOAD_SERVICE_MODE: 'persistent', PILOT_BOOTSTRAP_B64: Buffer.from(source).toString('base64'),
    UPLOAD_PRUNE_FAILED_TEMP_DIRS: '[".n8n-clone-16b4d4c47d6b593ddfcb6b82"]', GH_APP_PRIVATE_KEY: CANARY };
  const ledger = Buffer.from('actual runtime ledger bytes');
  const fsImpl = { realpathSync: p => p, lstatSync: () => ({ isSymbolicLink: () => false }), statSync: () => ({ isFile: () => true, size: ledger.length }),
    readFileSync: p => { assert.equal(p, '/data/work/control/upload-ledger.cjs'); return ledger; }, statfsSync: () => ({ bavail: 1000, bsize: 4096 }) };
  const input = { env, observedAt: 1793988000000, before: { status: 'OBSERVED', digest: 'a'.repeat(64), failedUploadPresent: true },
    after: { status: 'OBSERVED', digest: 'a'.repeat(64), failedUploadPresent: true },
    temporaryCleanup: { results: [{ name: '.n8n-clone-16b4d4c47d6b593ddfcb6b82', state: 'removed' }] }, confirmedCleanup: { results: [] } };
  return { env, ledger, fsImpl, input, result() { return helper(fsImpl).runtimeObservation(input); } };
}
test('runtime evidence measures code bytes and disk, without environment values', () => {
  const f = evidenceFixture(), r = f.result();
  assert.equal(r.status, 'OBSERVED'); assert.equal(r.phase, 'POST_CLEANUP'); assert.equal(r.availableDiskBytes, 4096000);
  assert.equal(r.journalPreserved, true); assert.equal(r.cleanupSafe, true); assert.equal(r.persistent, true);
  assert.equal(r.runtimeFiles[0].sha256, crypto.createHash('sha256').update(source).digest('hex'));
  assert.equal(r.runtimeFiles[1].sha256, crypto.createHash('sha256').update(f.ledger).digest('hex'));
  assert.ok(!JSON.stringify(r).includes(CANARY)); assert.ok(!JSON.stringify(r).includes('base64'));
});
for (const name of ['changed-journal', 'missing-failed-row', 'unreadable-journal', 'unsafe-cleanup', 'extra-temp-clone', 'pilot-mode'])
test('runtime evidence cannot claim acceptance: ' + name, () => {
  const f = evidenceFixture();
  if (name === 'changed-journal') f.input.after.digest = 'b'.repeat(64);
  if (name === 'missing-failed-row') f.input.before.failedUploadPresent = false;
  if (name === 'unreadable-journal') f.input.after.status = 'UNAVAILABLE';
  if (name === 'unsafe-cleanup') f.input.temporaryCleanup.results[0].state = 'local_changes_in_history';
  if (name === 'extra-temp-clone') f.env.UPLOAD_PRUNE_FAILED_TEMP_DIRS = '[".n8n-clone-16b4d4c47d6b593ddfcb6b82","extra"]';
  if (name === 'pilot-mode') f.env.UPLOAD_SERVICE_MODE = 'pilot';
  const r = f.result();
  if (name.includes('journal') || name === 'missing-failed-row') assert.equal(r.journalPreserved, false);
  else if (name === 'pilot-mode') assert.equal(r.persistent, false); else assert.equal(r.cleanupSafe, false);
});
test('unexpected resource, missing deployment, symlink source or disk errors yield only safe unavailable evidence', () => {
  for (const change of [f => f.env.RAILWAY_PROJECT_ID = 'foreign', f => delete f.env.RAILWAY_DEPLOYMENT_ID,
    f => f.fsImpl.lstatSync = () => ({ isSymbolicLink: () => true }), f => f.fsImpl.statfsSync = () => { throw Error(CANARY); }]) {
    const f = evidenceFixture(); change(f); const r = f.result();
    assert.equal(r.status, 'UNAVAILABLE'); assert.ok(!JSON.stringify(r).includes(CANARY));
  }
});
