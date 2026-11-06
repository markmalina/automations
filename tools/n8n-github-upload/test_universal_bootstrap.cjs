const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const cp = require('node:child_process');
const source = fs.readFileSync(__dirname + '/pilot-bootstrap.cjs', 'utf8');
const start = source.indexOf('// UNIVERSAL_WORKFLOWS_START');
const end = source.indexOf('// UNIVERSAL_WORKFLOWS_END');
assert(start >= 0 && end > start);
const block = source.slice(start, end);

function harness(failAt = null) {
  const files = new Map(), calls = [];
  const context = {
    fs: {
      writeFileSync(path, text, options) { assert.equal(options.mode, 0o600); files.set(path, text); },
      existsSync(path) { return files.has(path); },
      unlinkSync(path) { files.delete(path); },
    },
    async cli(args) {
      calls.push([...args]);
      if (args[0] === 'import:workflow') {
        const path = args[1].slice('--input='.length);
        const payload = JSON.parse(files.get(path));
        assert(['workUploadGrantPilot', 'workOwnerRepositoryUploadV1'].includes(payload.id));
        assert.equal(JSON.stringify(payload).includes('PRIVATE_CANARY'), false);
      }
      if (calls.length === failAt) throw Error('EXPECTED_CLI_FAILURE');
    },
  };
  vm.runInNewContext(block, context, { timeout: 1000 });
  return { context, calls, files };
}

test('bootstrap imports and publishes both fixed workflow IDs using stock CLI and removes files', async () => {
  const h = harness();
  await h.context.installUniversalWorkflows();
  assert.deepEqual(h.calls.map(a => a[0]), ['import:workflow', 'publish:workflow', 'import:workflow', 'publish:workflow']);
  assert.deepEqual(h.calls.filter(a => a[0] === 'publish:workflow').map(a => a[1]),
    ['--id=workUploadGrantPilot', '--id=workOwnerRepositoryUploadV1']);
  assert.equal(h.files.size, 0);
});
for (const at of [1, 2, 3, 4]) test('failed import/publish aborts before public startup and removes source file: ' + at, async () => {
  const h = harness(at);
  await assert.rejects(h.context.installUniversalWorkflows(), /EXPECTED_CLI_FAILURE/u);
  assert.equal(h.calls.length, at);
  assert.equal(h.files.size, 0);
});
test('workflow installation is persistent-only, after credentials and before public child', () => {
  const call = source.indexOf('    await installUniversalWorkflows();');
  assert(call > source.indexOf("await cli(['import:credentials','--input='+filename])"));
  assert(source.slice(call - 110, call).includes('if (persistent)'));
  assert(call < source.indexOf('env: runtimeChildEnvironment(process.env, persistent)'));
  assert(source.slice(call - 110, call).includes('GITHUB_APP_UNAVAILABLE'));
});
test('persistent upload instance serializes production executions, bounded pilot keeps its configured limit', () => {
  const tail = source.slice(source.indexOf('function runtimeChildEnvironment('), source.indexOf('async function cli('));
  const context = { process: { env: { UPLOAD_SERVICE_MODE: 'persistent' } } };
  // Only the pure declaration is evaluated; the watchdog and main are excluded.
  const declaration = tail.slice(0, tail.indexOf('function childExitCode('));
  vm.runInNewContext(declaration, context);
  const original = { N8N_CONCURRENCY_PRODUCTION_LIMIT: '9', CUSTOM_VALUE: 'kept' };
  assert.equal(context.runtimeChildEnvironment(original, true).N8N_CONCURRENCY_PRODUCTION_LIMIT, '1');
  assert.equal(context.runtimeChildEnvironment(original, false).N8N_CONCURRENCY_PRODUCTION_LIMIT, '9');
  assert.equal(original.N8N_CONCURRENCY_PRODUCTION_LIMIT, '9');
  assert.equal(context.runtimeChildEnvironment(original, true).CUSTOM_VALUE, 'kept');
});
test('embedding is reproducible, bounded and matches reviewed JSON files', () => {
  const before = fs.readFileSync(__dirname + '/pilot-bootstrap.cjs');
  cp.execFileSync('python', [__dirname + '/build_universal_bootstrap.py']);
  assert.deepEqual(fs.readFileSync(__dirname + '/pilot-bootstrap.cjs'), before);
  assert(before.length < 100000);
  const capture = {};
  vm.runInNewContext(block + '\nthis.payload = UNIVERSAL_WORKFLOWS;', capture, { timeout: 1000 });
  const expected = ['upload-grant.workflow.json', 'owner-repository-upload.workflow.json'].map(name =>
    JSON.parse(fs.readFileSync(__dirname + '/' + name)));
  assert.equal(JSON.stringify(capture.payload), JSON.stringify(expected));
});
