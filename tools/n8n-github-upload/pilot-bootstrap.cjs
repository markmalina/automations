// n8n bootstrap: explicit persistent mode or a bounded pilot. Uses stock n8n CLI and local owner-setup endpoint.
// Contains no file-upload implementation or credentials.
const fs = require('node:fs');
const cp = require('node:child_process');
const { once } = require('node:events');
const crypto = require('node:crypto');
let server;
let githubPilotCredentials;
function childExitCode(persistentMode, shutdownRequested, code) {
  if(persistentMode&&!shutdownRequested) return typeof code==='number'&&code!==0?code:1;
  return code||0;
}
const persistent = process.env.UPLOAD_SERVICE_MODE === 'persistent';
const deadline = Number(process.env.PILOT_DEADLINE_MS);
if (!persistent && (!Number.isFinite(deadline) || deadline <= Date.now())) process.exit(0);
const watchdog = persistent ? null : setTimeout(() => {
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
  for (const path of ['/data', '/data/.n8n', '/data/work', '/data/work/git', '/data/work/uploads', '/data/work/receipts', '/data/work/control']) {
    fs.mkdirSync(path, { recursive: true, mode: 0o700 });
    if (process.getuid() === 0) fs.chownSync(path, 1000, 1000);
  }
  if (process.getuid() === 0) { process.setgid(1000); process.setuid(1000); }
  console.log('PILOT_UID', process.getuid());
  if(process.env.PILOT_LEDGER_B64) {
    const source=Buffer.from(process.env.PILOT_LEDGER_B64,'base64');
    const names=JSON.parse(process.env.UPLOAD_PRUNE_FAILED_TEMP_DIRS||'[]');
    // This exact allowlist is checked before deleting a failed pre-commit clone.
    // Run the verified helper from stdin first, so cleanup works on a full disk.
    if(names.length) {
      const result=cp.execFileSync('node',['-','prune-failed-temporary',JSON.stringify({names})],{input:source,encoding:'utf8'});
      const parsed=JSON.parse(result);
      if(parsed.error) throw Error('Temporary clone cleanup failed');
      console.log('UPLOAD_TEMPORARY_CLEANUP',JSON.stringify(parsed));
    }
    fs.writeFileSync('/data/work/control/upload-ledger.cjs',source,{mode:0o600});
    const result=cp.execFileSync('node',['/data/work/control/upload-ledger.cjs','prune-confirmed','{}'],{encoding:'utf8'});
    const parsed=JSON.parse(result);
    if(parsed.error) throw Error('Confirmed clone cleanup failed');
    console.log('UPLOAD_CONFIRMED_CLEANUP',JSON.stringify(parsed));
    const disk=fs.statfsSync('/data');
    console.log('UPLOAD_DISK_BYTES',JSON.stringify({available:Number(disk.bavail)*Number(disk.bsize),total:Number(disk.blocks)*Number(disk.bsize)}));
  }
  console.log(cp.execFileSync('git', ['--version'], { encoding: 'utf8' }).trim());
  fs.writeFileSync('/data/work/.write-probe', 'ok', { mode: 0o600 });
  for (const id of (persistent ? [] : (process.env.PILOT_PRUNE_FAILED_CLONES || '').split(',').filter(Boolean))) {
    if (!/^[0-9a-f-]{36}$/.test(id)) throw new Error('Invalid failed-pilot cleanup ID');
    fs.rmSync('/data/work/git/pilot-'+id,{recursive:true,force:true});
    console.log('PILOT_FAILED_CLONE_PRUNED',id);
  }
  if (process.env.GH_APP_PRIVATE_KEY) {
    const key = crypto.createPrivateKey(process.env.GH_APP_PRIVATE_KEY);
    if (key.asymmetricKeyType !== 'rsa') throw new Error('GitHub App key must be RSA PEM');
    const fingerprint = crypto.createHash('sha256').update(crypto.createPublicKey(key).export({type:'spki',format:'der'})).digest('base64');
    const now = Math.floor(Date.now()/1000);
    const unsigned = Buffer.from(JSON.stringify({alg:'RS256',typ:'JWT'})).toString('base64url')+'.'+Buffer.from(JSON.stringify({iat:now-30,exp:now+300,iss:'5641721'})).toString('base64url');
    const jwt = unsigned+'.'+crypto.sign('RSA-SHA256',Buffer.from(unsigned),key).toString('base64url');
    const result = await fetch('https://api.github.com/app', {headers:{Authorization:'Bearer '+jwt,Accept:'application/vnd.github+json','User-Agent':'markmalina-n8n-upload-pilot'}});
    if (!result.ok) throw new Error('GitHub App verification HTTP '+result.status);
    const app = await result.json();
    if (app.id !== 5641721 || app.slug !== 'markmalina-n8n-upload') throw new Error('Unexpected GitHub App identity');
    const receipt = {appId:app.id,slug:app.slug,fingerprint,permissions:app.permissions,verifiedAt:new Date().toISOString()};
    fs.writeFileSync('/data/work/receipts/github-app-auth.json',JSON.stringify(receipt,null,2),{mode:0o600});
    console.log('PILOT_GITHUB_APP_VERIFIED',JSON.stringify(receipt));
    const tokenResponse = await fetch('https://api.github.com/app/installations/179245428/access_tokens', {
      method:'POST',headers:{Authorization:'Bearer '+jwt,Accept:'application/vnd.github+json','User-Agent':'markmalina-n8n-upload-pilot','Content-Type':'application/json'},
      body:JSON.stringify({repository_ids:[1378687935],permissions:{contents:'write'}})
    });
    if (!tokenResponse.ok) throw new Error('Installation token HTTP '+tokenResponse.status);
    const installation = await tokenResponse.json();
    if (!installation.token || installation.repositories?.length !== 1 || installation.repositories[0].full_name !== 'markmalina/freelance') throw new Error('Unexpected installation token scope');
    githubPilotCredentials = [
      {id:'workPilotGitPassword',name:'Freelance pilot Git token',type:'gitPassword',data:{username:'x-access-token',password:installation.token}},
      {id:'workPilotGithubApi',name:'Freelance pilot GitHub token',type:'githubApi',data:{accessToken:installation.token,server:'https://api.github.com'}},
      {id:'workPilotGithubHeader',name:'Freelance pilot GitHub API header',type:'httpHeaderAuth',data:{name:'Authorization',value:'Bearer '+installation.token}},
      {id:'workPilotGithubJwt',name:'GitHub App signing key',type:'jwtAuth',data:{keyType:'pemKey',privateKey:process.env.GH_APP_PRIVATE_KEY,algorithm:'RS256'}}
    ];
    console.log('PILOT_GITHUB_TOKEN_SCOPED',JSON.stringify({repository:'markmalina/freelance',expiresAt:installation.expires_at}));
  }
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
  if (githubPilotCredentials) {
    const filename='/data/.n8n/github-pilot-import.json';
    try {
      fs.writeFileSync(filename,JSON.stringify(githubPilotCredentials),{mode:0o600});
      await cli(['import:credentials','--input='+filename]);
    } finally { if(fs.existsSync(filename)) fs.unlinkSync(filename); }
  }
  console.log(persistent ? 'UPLOAD_SERVICE_READY' : 'PILOT_READY_TO_START', persistent ? 'persistent' : new Date(deadline).toISOString());
  server = cp.spawn('n8n', ['start'], { stdio: 'inherit', env: { ...process.env, N8N_LISTEN_ADDRESS: '0.0.0.0', N8N_PORT: '5678', N8N_SECURE_COOKIE: 'true' } });
  let shutdownRequested=false;
  process.on('SIGTERM', () => {shutdownRequested=true;server.kill('SIGTERM');});
  process.on('SIGINT', () => {shutdownRequested=true;server.kill('SIGTERM');});
  const [code] = await once(server, 'exit');
  if(watchdog) clearTimeout(watchdog);
  // A persistent service must surface an unexpected child exit to ON_FAILURE.
  process.exit(childExitCode(persistent,shutdownRequested,code));
}
main().catch(async e => { console.error('PILOT_BOOTSTRAP_FAILED', e.message); await stop(); process.exit(1); });

