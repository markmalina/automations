// Bounded pilot bootstrap. Uses stock n8n CLI and local owner-setup endpoint.
// Contains no file-upload implementation or credentials.
const fs = require('node:fs');
const cp = require('node:child_process');
const { once } = require('node:events');
let server;
const deadline = Number(process.env.PILOT_DEADLINE_MS);
if (!Number.isFinite(deadline) || deadline <= Date.now()) process.exit(0);
const watchdog = setTimeout(() => {
  console.log('PILOT_DEADLINE_REACHED');
  if (server) server.kill('SIGTERM');
  setTimeout(() => process.exit(0), 20000);
}, deadline - Date.now());
async function cli(args) {
  const child = cp.spawn('n8n', args, { stdio: 'inherit' });
  const [code] = await once(child, 'exit');
  if (code !== 0) throw new Error('n8n CLI failed: ' + args[0]);
}
async function stop() {
  if (!server || server.exitCode !== null) return;
  const done = once(server, 'exit');
  server.kill('SIGTERM');
  await done;
}
async function main() {
  for (const path of ['/data', '/data/.n8n', '/data/work', '/data/work/git', '/data/work/uploads', '/data/work/receipts']) {
    fs.mkdirSync(path, { recursive: true, mode: 0o700 });
    if (process.getuid() === 0) fs.chownSync(path, 1000, 1000);
  }
  if (process.getuid() === 0) { process.setgid(1000); process.setuid(1000); }
  console.log('PILOT_UID', process.getuid());
  console.log(cp.execFileSync('git', ['--version'], { encoding: 'utf8' }).trim());
  fs.writeFileSync('/data/work/.write-probe', 'ok', { mode: 0o600 });
  const marker = '/data/.n8n/pilot-initialized';
  if (!fs.existsSync(marker)) {
    server = cp.spawn('n8n', ['start'], { stdio: 'inherit', env: { ...process.env, N8N_LISTEN_ADDRESS: '127.0.0.1', N8N_PORT: '15678', N8N_SECURE_COOKIE: 'false' } });
    let ready = false;
    for (let i = 0; i < 150; i++) {
      if (server.exitCode !== null) throw new Error('initial n8n exited');
      try {
        const r = await fetch('http://127.0.0.1:15678/rest/settings');
        if (r.ok && (r.headers.get('content-type') || '').includes('application/json')) {
          const settings = await r.json();
          if (settings.data) { ready = true; break; }
        }
      } catch {}
      await new Promise(r => setTimeout(r, 1000));
    }
    if (!ready) throw new Error('initial n8n not ready');
    const r = await fetch('http://127.0.0.1:15678/rest/owner/setup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'pilot@localhost.invalid', firstName: 'Mark', lastName: 'Pilot', password: process.env.PILOT_OWNER_PASSWORD })
    });
    if (!r.ok || !(r.headers.get('content-type') || '').includes('application/json')) {
      // A previous attempt may have completed owner setup before import failed.
      const login = await fetch('http://127.0.0.1:15678/rest/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emailOrLdapLoginId: 'pilot@localhost.invalid', password: process.env.PILOT_OWNER_PASSWORD })
      });
      if (!login.ok) throw new Error('local owner verification status ' + login.status);
    }
    console.log('PILOT_OWNER_INITIALIZED');
    await stop();
    const credential = [{ id: 'workPilotHeaderAuth', name: 'Work pilot header', type: 'httpHeaderAuth', data: { name: 'X-Work-Upload-Token', value: process.env.PILOT_UPLOAD_TOKEN } }];
    const workflow = JSON.parse(Buffer.from(process.env.PILOT_WORKFLOW_B64, 'base64').toString());
    workflow.id = 'workBinaryPilot';
    workflow.active = true;
    workflow.nodes[0].credentials = { httpHeaderAuth: { id: 'workPilotHeaderAuth', name: 'Work pilot header' } };
    const credsPath = '/data/.n8n/pilot-import-credentials.json';
    const workflowPath = '/data/.n8n/pilot-import-workflow.json';
    try {
      fs.writeFileSync(credsPath, JSON.stringify(credential), { mode: 0o600 });
      fs.writeFileSync(workflowPath, JSON.stringify(workflow), { mode: 0o600 });
      await cli(['import:credentials', '--input=' + credsPath]);
      await cli(['import:workflow', '--input=' + workflowPath]);
      await cli(['publish:workflow', '--id=workBinaryPilot']);
    } finally {
      for (const p of [credsPath, workflowPath]) { if (fs.existsSync(p)) fs.unlinkSync(p); }
    }
    fs.writeFileSync(marker, new Date().toISOString(), { mode: 0o600 });
  }
  console.log('PILOT_READY_TO_START', new Date(deadline).toISOString());
  server = cp.spawn('n8n', ['start'], { stdio: 'inherit', env: { ...process.env, N8N_LISTEN_ADDRESS: '0.0.0.0', N8N_PORT: '5678', N8N_SECURE_COOKIE: 'true' } });
  process.on('SIGTERM', () => server.kill('SIGTERM'));
  process.on('SIGINT', () => server.kill('SIGTERM'));
  const [code] = await once(server, 'exit');
  clearTimeout(watchdog);
  process.exit(code || 0);
}
main().catch(async e => { console.error('PILOT_BOOTSTRAP_FAILED', e.message); await stop(); process.exit(1); });
