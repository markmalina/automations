// n8n bootstrap: explicit persistent mode or a bounded pilot. Uses stock n8n CLI and local owner-setup endpoint.
// Contains no file-upload implementation or credentials.
const fs = require('node:fs');
const cp = require('node:child_process');
const { once } = require('node:events');
const crypto = require('node:crypto');
let server;
let githubPilotCredentials;
// OPS_OBSERVATION_START — metadata only; no token, manifest, receipt or row is logged.
function observationJournalSnapshot(directory = '/data/work/control') {
  let db;
  try {
    const path = require('node:path');
    const file = path.join(directory, 'uploads.sqlite');
    if (fs.realpathSync(directory) !== path.resolve(directory) || fs.lstatSync(file).isSymbolicLink() ||
        !fs.statSync(file).isFile() || fs.statSync(file).size > 67108864) throw Error('journal');
    db = new (require('node:sqlite').DatabaseSync)(file, { readOnly: true });
    db.exec('BEGIN');
    if (db.prepare('PRAGMA quick_check').all().some(row => row.quick_check !== 'ok')) throw Error('journal');
    const hash = crypto.createHash('sha256'); let rows = 0, bytes = 0;
    const tables = {
      uploads: ['id', 'digest', 'manifest', 'owner', 'state', 'commit_sha', 'receipt', 'created_at', 'updated_at'],
      grants: ['token_hash', 'upload_id', 'digest', 'file_count', 'total_bytes', 'expires_at'],
    };
    // Normalize the additive universal-target column to null on an old journal.
    // This preserves comparison across migration and includes future bindings.
    const hasGrantTarget = db.prepare('PRAGMA table_info(grants)').all().some(column => column.name === 'target_json');
    for (const [table, columns] of Object.entries(tables)) {
      hash.update(table + '\n');
      const projection = columns.join(',') + (table === 'grants' ? ',' + (hasGrantTarget ? 'target_json' : 'NULL AS target_json') : '');
      for (const row of db.prepare('SELECT ' + projection + ' FROM ' + table + ' ORDER BY ' + columns[0]).iterate()) {
        const raw = JSON.stringify(columns.map(column => row[column]).concat(table === 'grants' ? [row.target_json] : []));
        rows++; bytes += Buffer.byteLength(raw);
        if (rows > 100000 || bytes > 67108864) throw Error('journal');
        hash.update(raw + '\n');
      }
    }
    const failedUploadPresent = Boolean(db.prepare('SELECT 1 FROM uploads WHERE id=?').get('9d94bcf3-9a28-4014-93d5-ce8e5d259c7d'));
    db.exec('COMMIT'); db.close(); db = null;
    return { status: 'OBSERVED', digest: hash.digest('hex'), failedUploadPresent };
  } catch { return { status: 'UNAVAILABLE', errorCode: 'E_JOURNAL_OBSERVATION_UNAVAILABLE' }; }
  finally { try { if (db) db.close(); } catch {} }
}
function runtimeObservation({ before, after, temporaryCleanup, confirmedCleanup, env = process.env, observedAt = Date.now() }) {
  try {
    const ids = { projectId: '69cc90c9-7ede-4a57-bc03-f3e63f01cca3', environmentId: '369d5bb9-5107-4e39-89d8-668b9b59e230', serviceId: '2425a11a-90bd-47fe-9c5b-03ad96ee7a74' };
    if (env.RAILWAY_PROJECT_ID !== ids.projectId || env.RAILWAY_ENVIRONMENT_ID !== ids.environmentId ||
        env.RAILWAY_SERVICE_ID !== ids.serviceId || !/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(env.RAILWAY_DEPLOYMENT_ID || '') ||
        !Number.isSafeInteger(observedAt) || observedAt < 0) throw Error('target');
    const digest = value => crypto.createHash('sha256').update(value).digest('hex');
    if (typeof env.PILOT_BOOTSTRAP_B64 !== 'string' || env.PILOT_BOOTSTRAP_B64.length > 150000 ||
        fs.realpathSync('/data/work/control') !== '/data/work/control' ||
        fs.lstatSync('/data/work/control/upload-ledger.cjs').isSymbolicLink() ||
        !fs.statSync('/data/work/control/upload-ledger.cjs').isFile() ||
        fs.statSync('/data/work/control/upload-ledger.cjs').size > 100000) throw Error('source');
    const bootstrap = Buffer.from(env.PILOT_BOOTSTRAP_B64, 'base64');
    const ledger = fs.readFileSync('/data/work/control/upload-ledger.cjs');
    if (bootstrap.length < 1 || bootstrap.length > 100000 || ledger.length < 1 || ledger.length > 100000) throw Error('source');
    const disk = fs.statfsSync('/data'); const availableDiskBytes = Number(disk.bavail) * Number(disk.bsize);
    if (!Number.isSafeInteger(availableDiskBytes) || availableDiskBytes < 0) throw Error('disk');
    const temporaryNames = JSON.parse(env.UPLOAD_PRUNE_FAILED_TEMP_DIRS || '[]');
    const safeStates = new Set(['removed', 'absent']);
    const cleanupSafe = Array.isArray(temporaryNames) && temporaryNames.length === 1 &&
      temporaryNames[0] === '.n8n-clone-16b4d4c47d6b593ddfcb6b82' &&
      Array.isArray(temporaryCleanup?.results) && temporaryCleanup.results.length === 1 &&
      temporaryCleanup.results[0].name === temporaryNames[0] && safeStates.has(temporaryCleanup.results[0].state) &&
      Array.isArray(confirmedCleanup?.results) && confirmedCleanup.results.every(row => safeStates.has(row.state));
    const journalPreserved = before?.status === 'OBSERVED' && after?.status === 'OBSERVED' &&
      before.failedUploadPresent === true && after.failedUploadPresent === true &&
      /^[0-9a-f]{64}$/.test(before.digest) && before.digest === after.digest;
    return { schemaVersion: 'n8n-upload.runtime-observation/v1', status: 'OBSERVED', phase: 'POST_CLEANUP',
      ...ids, deploymentId: env.RAILWAY_DEPLOYMENT_ID, observedAt,
      runtimeFiles: [
        { path: 'tools/n8n-github-upload/pilot-bootstrap.cjs', sha256: digest(bootstrap) },
        { path: 'tools/n8n-github-upload/upload-ledger.cjs', sha256: digest(ledger) },
      ], persistent: env.UPLOAD_SERVICE_MODE === 'persistent', availableDiskBytes,
      journalPreserved, journalDigestBefore: before?.status === 'OBSERVED' ? before.digest : null,
      journalDigestAfter: after?.status === 'OBSERVED' ? after.digest : null, cleanupSafe };
  } catch { return { schemaVersion: 'n8n-upload.runtime-observation/v1', status: 'UNAVAILABLE', errorCode: 'E_RUNTIME_OBSERVATION_UNAVAILABLE' }; }
}
// OPS_OBSERVATION_END
function runtimeChildEnvironment(env, persistentMode) {
  // One production execution on this upload instance also bounds aggregate
  // GitHub write rate across simultaneous Work requests. No other service is changed.
  return { ...env, ...(persistentMode ? { N8N_CONCURRENCY_PRODUCTION_LIMIT: '1' } : {}),
    N8N_LISTEN_ADDRESS: '0.0.0.0', N8N_PORT: '5678', N8N_SECURE_COOKIE: 'true' };
}
// UNIVERSAL_WORKFLOWS_START
const UNIVERSAL_WORKFLOWS = [{"id":"workUploadGrantPilot","name":"Issue one upload grant (metadata only)","description":"Upload to markmalina repositories via existing OAuth. Before execution read https://github.com/markmalina/automations/blob/main/tools/n8n-github-upload/UNIVERSAL_ROUTE.md. Metadata only; never display grants.","active":false,"nodes":[{"parameters":{"httpMethod":"POST","path":"work-upload-grant-pilot-v1","authentication":"headerAuth","responseMode":"lastNode","responseData":"firstEntryJson","responseBinaryPropertyName":"data","options":{}},"id":"09b7fd9e-b1f8-4738-bfa4-5a80d05aef2f","name":"OAuth grant input","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[0,0],"webhookId":"344a7789-4a7b-4863-aa2a-f35912078fc7","credentials":{"httpHeaderAuth":{"id":"workPilotHeaderAuth","name":"Work pilot header"}}},{"id":"b1f10b16-ffc1-4b93-a34e-6c048b86a4f2","name":"Issue bound grant","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[0,800],"parameters":{"executeOnce":true,"command":"={{ (()=>{const p=$json.body;if(!p || Object.keys(p).some(k=>!['id','digest','fileCount','totalBytes','target'].includes(k)))throw Error('Invalid grant fields');const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs grant '+quote(JSON.stringify(p));})() }}"}},{"id":"a7b921b1-98a6-408d-a78b-e4e4af21b16a","name":"Return temporary grant","type":"n8n-nodes-base.code","typeVersion":2,"position":[600,0],"parameters":{"jsCode":"const r=JSON.parse($json.stdout);if(r.error)throw Error(r.error);return [{json:r}];"}}],"connections":{"OAuth grant input":{"main":[[{"node":"Issue bound grant","type":"main","index":0}]]},"Issue bound grant":{"main":[[{"node":"Return temporary grant","type":"main","index":0}]]}},"settings":{"executionOrder":"v1","saveDataSuccessExecution":"all","saveDataErrorExecution":"none","saveManualExecutions":true,"saveExecutionProgress":false,"availableInMCP":true}},{"id":"workOwnerRepositoryUploadV1","name":"Work binary upload to an owned GitHub repository","active":false,"description":"Candidate: target-bound manifest and grant, stock n8n nodes, one Git Data commit. No clone. Native/live acceptance pending.","nodes":[{"id":"83461db3-37b3-5090-bba3-5fe303fe5490","name":"Binary upload","type":"n8n-nodes-base.webhook","typeVersion":2,"position":[0,0],"parameters":{"httpMethod":"POST","path":"work-owner-repository-upload-v1","authentication":"none","responseMode":"lastNode","responseData":"firstEntryJson","responseBinaryPropertyName":"data","options":{}},"webhookId":"a8cb36f9-85c5-58b3-b63b-3c015894cac3"},{"id":"f6e27b7b-c80f-55f0-b2ed-fbb873899765","name":"Prepare upload","type":"n8n-nodes-base.code","typeVersion":2,"position":[280,0],"parameters":{"jsCode":"const input=$input.first();\nconst exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&JSON.stringify(Object.keys(o).sort())===JSON.stringify(keys.sort());\nlet m;try{const raw=input.json.body.manifest;if(typeof raw!=='string'||raw.length>30000)throw Error();m=JSON.parse(raw);}catch{throw Error('E_MANIFEST');}\nif(!exact(m,['schemaVersion','uploadId','target','files'])||m.schemaVersion!=='work-upload/v2'||!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(m.uploadId)||!Array.isArray(m.files)||m.files.length<1||m.files.length>100)throw Error('E_MANIFEST');\nconst t=m.target;\nif(!exact(t,['repositoryId','repository','branch','prefix'])||!Number.isSafeInteger(t.repositoryId)||t.repositoryId<1||typeof t.repository!=='string'||!/^markmalina\\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(t.repository))throw Error('E_TARGET');\nif(typeof t.branch!=='string'||t.branch.length>200||!/^[A-Za-z0-9][A-Za-z0-9._\\/-]*$/.test(t.branch)||t.branch.includes('..')||t.branch.includes('//')||t.branch.endsWith('/')||t.branch.endsWith('.')||t.branch.toUpperCase()==='HEAD'||t.branch.split('/').some(s=>s.startsWith('.')||s.toLowerCase().endsWith('.lock')))throw Error('E_BRANCH');\nconst safePath=s=>typeof s==='string'&&s.length>0&&s.isWellFormed()&&Buffer.byteLength(s,'utf8')<=2048&&s===s.normalize('NFC')&&!s.startsWith('/')&&!/[\\\\\\u0000-\\u001f\\u007f,]/.test(s)&&!s.split('/').some(p=>!p||p==='.'||p==='..'||p.toLowerCase()==='.git'||Buffer.byteLength(p,'utf8')>255);\nif(typeof t.prefix!=='string'||(t.prefix!==''&&!safePath(t.prefix)))throw Error('E_PREFIX');\nconst prefix=t.prefix?t.prefix+'/':'';const seen=new Set(),fields=new Set();let total=0;\nfor(const f of m.files){if(!exact(f,['field','path','bytes','sha256'])||!safePath(f.path)||typeof f.field!=='string'||!/^file(?:0|[1-9][0-9]?)$/.test(f.field)||fields.has(f.field)||!input.binary?.[f.field]||typeof f.sha256!=='string'||!/^[a-f0-9]{64}$/.test(f.sha256)||!Number.isSafeInteger(f.bytes)||f.bytes<0||f.bytes>32000000)throw Error('E_FILE');const path=prefix+f.path;if(!safePath(path))throw Error('E_RESOLVED_PATH');if(/^\\.github\\/workflows(?:\\/|$)/i.test(path))throw Error('E_WORKFLOWS_PERMISSION');const folded=path.toLowerCase();if(seen.has(folded))throw Error('E_DUPLICATE_PATH');seen.add(folded);fields.add(f.field);total+=f.bytes;}\nfor(const p of seen){const parts=p.split('/');for(let i=1;i<parts.length;i++)if(seen.has(parts.slice(0,i).join('/')))throw Error('E_PATH_COLLISION');}\nif(total>32000000||Object.keys(input.binary||{}).length!==m.files.length)throw Error('E_BUNDLE_LIMIT');\nconst grant=input.json.headers?.['x-work-upload-grant'];if(typeof grant!=='string'||!/^[a-f0-9]{64}$/.test(grant))throw Error('GRANT_DENIED');\nreturn [{json:{manifest:m,target:t,prefix,started:Date.now(),owner:String($execution.id),grant,apiBase:'https://api.github.com/repos/'+t.repository.split('/').map(encodeURIComponent).join('/'),branchEncoded:encodeURIComponent(t.branch)}}];"}},{"id":"ef3caa9e-3d70-5c53-b1b0-fde074bb6d68","name":"Restore file references","type":"n8n-nodes-base.code","typeVersion":2,"position":[560,0],"parameters":{"jsCode":"const p=$('Prepare upload').first().json,binary=$('Binary upload').first().binary;\nreturn p.manifest.files.map(f=>({json:{...f,targetPath:p.prefix+f.path},binary:{data:binary[f.field]}}));"}},{"id":"80b06715-fc3f-577b-b21e-39bb9ab42577","name":"Read binary bytes for GitHub","type":"n8n-nodes-base.code","typeVersion":2,"position":[840,0],"parameters":{"jsCode":"const items=$input.all(),result=[];\n// Read binary while it is present on this node input. Crypto deliberately drops processed binary fields.\nfor(let i=0;i<items.length;i++){const buffer=await this.helpers.getBinaryDataBuffer(i,'data');if(buffer.length!==items[i].json.bytes)throw Error('E_SOURCE_SIZE');result.push({json:{...items[i].json,actualBytes:buffer.length,contentBase64:buffer.toString('base64')},binary:items[i].binary});}\nreturn result;"}},{"id":"b5687d8d-4bcb-5c42-acde-415ef151810f","name":"Hash source bytes","type":"n8n-nodes-base.crypto","typeVersion":2,"position":[1120,0],"parameters":{"action":"hash","binaryData":true,"binaryPropertyName":"data","type":"SHA256","encoding":"hex","dataPropertyName":"actualSha256"}},{"id":"6f53487a-5068-5ac3-bd78-78d57d6a2459","name":"Verify bytes and encode for GitHub","type":"n8n-nodes-base.code","typeVersion":2,"position":[0,200],"parameters":{"jsCode":"const items=$input.all();\nif(items.length!==$('Prepare upload').first().json.manifest.files.length)throw Error('E_FILE_COUNT');\nfor(const item of items){if(item.json.actualSha256!==item.json.sha256)throw Error('E_SOURCE_DIGEST');if(item.json.actualBytes!==item.json.bytes)throw Error('E_SOURCE_SIZE');}\nreturn items.map(item=>({json:item.json}));"}},{"id":"1405d501-2aad-5e08-8b30-1be15b1fde39","name":"Bundle checked","type":"n8n-nodes-base.code","typeVersion":2,"position":[280,200],"parameters":{"jsCode":"return [{json:{fileCount:$input.all().length}}];"}},{"id":"72260236-598c-5f4a-be81-90029fccaf60","name":"Hash upload grant","type":"n8n-nodes-base.crypto","typeVersion":2,"position":[560,200],"parameters":{"action":"hash","binaryData":false,"value":"={{ $('Prepare upload').first().json.grant }}","type":"SHA256","encoding":"hex","dataPropertyName":"grantHash"}},{"id":"b907c457-648d-5e72-b293-9150bbef436b","name":"Claim durable upload","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[840,200],"parameters":{"executeOnce":true,"command":"={{ (()=>{const p={id:$('Prepare upload').first().json.manifest.uploadId,manifest:$('Prepare upload').first().json.manifest,owner:$('Prepare upload').first().json.owner,grantHash:$('Hash upload grant').first().json.grantHash};const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs claim-granted-hash '+quote(JSON.stringify(p));})() }}"}},{"id":"9816c70e-ef59-56f2-9fd8-d4627d9e1155","name":"Parse claim","type":"n8n-nodes-base.code","typeVersion":2,"position":[1120,200],"parameters":{"jsCode":"const r=JSON.parse($json.stdout),p=$('Prepare upload').first().json;\nif(r.error)throw Error(r.error);if(!['new','verify'].includes(r.route))throw Error('UPLOAD_UNCERTAIN');\nconst canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);\nif(canonical(r.target)!==canonical(p.target)||r.id!==p.manifest.uploadId||!/^[a-f0-9]{64}$/.test(r.digest))throw Error('E_TARGET_BINDING');\nif(r.route==='verify'&&!/^[a-f0-9]{40}$/.test(r.commitSha||''))throw Error('E_COMMIT');return [{json:r}];"}},{"id":"dfb82584-7190-5e22-b722-de94424ddb9a","name":"Sign GitHub App JWT","type":"n8n-nodes-base.jwt","typeVersion":1,"position":[0,400],"parameters":{"operation":"sign","useJson":true,"claimsJson":"={{ JSON.stringify({iss:'5641721',iat:Math.floor(Date.now()/1000)-30,exp:Math.floor(Date.now()/1000)+300}) }}","options":{}},"credentials":{"jwtAuth":{"id":"workPilotGithubJwt","name":"GitHub App signing key"}}},{"id":"4c4a42f6-e24b-511c-a30a-36c844683ba4","name":"Issue installation token","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[280,400],"parameters":{"method":"POST","url":"https://api.github.com/app/installations/179245428/access_tokens","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Sign GitHub App JWT').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}},"sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify({repository_ids:[$('Prepare upload').first().json.target.repositoryId],permissions:{contents:'write'} }) }}"},"retryOnFail":false},{"id":"d808a46c-7999-5eec-af0f-e846eaf4b059","name":"Validate installation scope","type":"n8n-nodes-base.code","typeVersion":2,"position":[560,400],"parameters":{"jsCode":"const r=$json,t=$('Prepare upload').first().json.target;\nif(typeof r.token!=='string'||r.token.length<20||r.token.length>512||/\\s/.test(r.token)||!Array.isArray(r.repositories)||r.repositories.length!==1||r.repositories[0].id!==t.repositoryId||r.repositories[0].full_name!==t.repository||!r.permissions||r.permissions.contents!=='write'||Object.entries(r.permissions).some(([k,v])=>!(k==='contents'&&v==='write'||k==='metadata'&&v==='read')))throw Error('E_INSTALLATION_SCOPE');\nreturn [{json:{repositoryId:t.repositoryId}}];"}},{"id":"55c2e2bc-f2b0-5bcd-9c0c-362fc2a08c4a","name":"Read repository","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[840,400],"parameters":{"method":"GET","url":"={{ $('Prepare upload').first().json.apiBase }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}}},"retryOnFail":false},{"id":"7d7e5a59-f39f-5fac-883e-cf48c9268361","name":"Validate repository owner","type":"n8n-nodes-base.code","typeVersion":2,"position":[1120,400],"parameters":{"jsCode":"const t=$('Prepare upload').first().json.target;\nif($json.id!==t.repositoryId||$json.full_name!==t.repository||$json.owner?.id!==23397294||$json.owner?.login!=='markmalina')throw Error('E_REPOSITORY_OWNER');return [{json:{verified:true}}];"}},{"id":"1cf8e68d-779c-50ae-ae81-cc821ad5a3c1","name":"Already has commit","type":"n8n-nodes-base.if","typeVersion":2.2,"position":[0,600],"parameters":{"conditions":{"options":{"caseSensitive":true,"leftValue":"","typeValidation":"strict","version":2},"conditions":[{"id":"12c8661b-b75d-5158-a22a-aaeab6915a5d","leftValue":"={{ $('Parse claim').first().json.route==='verify' }}","rightValue":true,"operator":{"type":"boolean","operation":"true","singleValue":true}}],"combinator":"and"},"options":{}}},{"id":"78a40ed0-8b81-5101-b2c4-2cf89832eac6","name":"Select replay commit","type":"n8n-nodes-base.code","typeVersion":2,"position":[280,600],"parameters":{"jsCode":"return [{json:{commitSha:$('Parse claim').first().json.commitSha}}];"}},{"id":"11193955-1f3e-5356-998d-12b9b0db94e0","name":"Read branch head","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[560,600],"parameters":{"method":"GET","url":"={{ $('Prepare upload').first().json.apiBase+'/git/ref/heads/'+$('Prepare upload').first().json.branchEncoded }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}}},"retryOnFail":false},{"id":"798eba68-b4b9-5753-b927-5639f449ce27","name":"Validate branch head","type":"n8n-nodes-base.code","typeVersion":2,"position":[840,600],"parameters":{"jsCode":"const p=$('Prepare upload').first().json;if($json.ref!=='refs/heads/'+p.target.branch||$json.object?.type!=='commit'||!/^[a-f0-9]{40}$/.test($json.object?.sha||''))throw Error('E_BRANCH_HEAD');return [{json:{parentSha:$json.object.sha}}];"}},{"id":"1e98acbd-3593-5279-bbd4-5421f2039222","name":"Read base commit","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[1120,600],"parameters":{"method":"GET","url":"={{ $('Prepare upload').first().json.apiBase+'/git/commits/'+$('Validate branch head').first().json.parentSha }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}}},"retryOnFail":false},{"id":"87021f28-bf6d-504f-8ae1-ee872b73c2d7","name":"Blob requests","type":"n8n-nodes-base.code","typeVersion":2,"position":[0,800],"parameters":{"jsCode":"if($json.sha!==$('Validate branch head').first().json.parentSha||!/^[a-f0-9]{40}$/.test($json.tree?.sha||''))throw Error('E_BASE_TREE');return $('Verify bytes and encode for GitHub').all().map(i=>({json:i.json}));"}},{"id":"fa896cea-3160-5534-ab02-a3db0f9d60ee","name":"Create file blobs","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[280,800],"parameters":{"method":"POST","url":"={{ $('Prepare upload').first().json.apiBase+'/git/blobs' }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}},"batching":{"batch":{"batchSize":1,"batchInterval":1000}}},"sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify({content:$json.contentBase64,encoding:'base64'}) }}"},"retryOnFail":false},{"id":"3fdd100c-3300-51cd-95b3-05a9536e6edb","name":"Collect tree entries","type":"n8n-nodes-base.code","typeVersion":2,"position":[560,800],"parameters":{"jsCode":"const blobs=$input.all(),files=$('Blob requests').all();if(blobs.length!==files.length||blobs.length<1)throw Error('E_BLOB_COUNT');const tree=blobs.map((b,i)=>{if(!/^[a-f0-9]{40}$/.test(b.json.sha||''))throw Error('E_BLOB_SHA');return {path:files[i].json.targetPath,mode:'100644',type:'blob',sha:b.json.sha};});return [{json:{tree,baseTree:$('Read base commit').first().json.tree.sha}}];"}},{"id":"7e94c173-2702-5dd1-8ddd-ce334eba5fc8","name":"Create bundle tree","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[840,800],"parameters":{"method":"POST","url":"={{ $('Prepare upload').first().json.apiBase+'/git/trees' }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}},"sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify({base_tree:$json.baseTree,tree:$json.tree}) }}"},"retryOnFail":false},{"id":"4cb34f4a-448d-5473-bcad-7ea4890d6271","name":"Validate bundle tree","type":"n8n-nodes-base.code","typeVersion":2,"position":[1120,800],"parameters":{"jsCode":"if(!/^[a-f0-9]{40}$/.test($json.sha||''))throw Error('E_TREE_SHA');return [{json:{treeSha:$json.sha}}];"}},{"id":"3ec1baf1-93a9-57d7-9e7e-3ba95448650b","name":"Create bundle commit","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[0,1000],"parameters":{"method":"POST","url":"={{ $('Prepare upload').first().json.apiBase+'/git/commits' }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}},"sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify({message:'work-upload:'+$('Prepare upload').first().json.manifest.uploadId+':'+$('Parse claim').first().json.digest,tree:$json.treeSha,parents:[$('Validate branch head').first().json.parentSha]}) }}"},"retryOnFail":false},{"id":"38b2da8b-0f5c-5354-8885-18516ba60a24","name":"Validate bundle commit","type":"n8n-nodes-base.code","typeVersion":2,"position":[280,1000],"parameters":{"jsCode":"const r=$json;if(!/^[a-f0-9]{40}$/.test(r.sha||'')||r.parents?.length!==1||r.parents[0].sha!==$('Validate branch head').first().json.parentSha||r.tree?.sha!==$('Validate bundle tree').first().json.treeSha)throw Error('E_COMMIT_SHAPE');return [{json:{commitSha:r.sha}}];"}},{"id":"4d6ce816-94e5-5cf5-9b53-9bdd9874c51b","name":"Journal committed SHA","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[560,1000],"parameters":{"executeOnce":true,"command":"={{ (()=>{const p={id:$('Prepare upload').first().json.manifest.uploadId,owner:$('Prepare upload').first().json.owner,sha:$('Validate bundle commit').first().json.commitSha};const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs committed '+quote(JSON.stringify(p));})() }}"}},{"id":"9e8831fe-469d-523e-861b-b6eec49a2f5b","name":"Commit recorded","type":"n8n-nodes-base.code","typeVersion":2,"position":[840,1000],"parameters":{"jsCode":"const r=JSON.parse($json.stdout);if(r.error)throw Error(r.error);if(r.commitSha!==$('Validate bundle commit').first().json.commitSha||r.state!=='committed')throw Error('E_COMMIT_NOT_RECORDED');return [{json:{commitSha:r.commitSha}}];"}},{"id":"ff8ae7e5-db07-5792-9702-17abf850a832","name":"Publish branch fast forward","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[1120,1000],"parameters":{"method":"PATCH","url":"={{ $('Prepare upload').first().json.apiBase+'/git/refs/heads/'+$('Prepare upload').first().json.branchEncoded }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}},"sendBody":true,"specifyBody":"json","jsonBody":"={{ JSON.stringify({sha:$('Commit recorded').first().json.commitSha,force:false}) }}"},"retryOnFail":false},{"id":"7ea64911-055b-5a39-bb30-8618554cc590","name":"Select published commit","type":"n8n-nodes-base.code","typeVersion":2,"position":[0,1200],"parameters":{"jsCode":"const sha=$('Commit recorded').first().json.commitSha,p=$('Prepare upload').first().json;if($json.ref!=='refs/heads/'+p.target.branch||$json.object?.sha!==sha)throw Error('E_REF_RESULT');return [{json:{commitSha:sha}}];"}},{"id":"2e33bca6-93ec-59a8-8dbd-cfae2eae7b90","name":"Verify remote reachability","type":"n8n-nodes-base.httpRequest","typeVersion":4.2,"position":[280,1200],"parameters":{"method":"GET","url":"={{ $('Prepare upload').first().json.apiBase+'/compare/'+$json.commitSha+'...'+$('Prepare upload').first().json.branchEncoded }}","authentication":"none","sendHeaders":true,"headerParameters":{"parameters":[{"name":"Authorization","value":"={{ 'Bearer '+$('Issue installation token').first().json.token }}"},{"name":"Accept","value":"application/vnd.github+json"},{"name":"X-GitHub-Api-Version","value":"2022-11-28"},{"name":"User-Agent","value":"markmalina-n8n-upload"}]},"options":{"timeout":60000,"redirect":{"redirect":{"followRedirects":false}}}},"retryOnFail":false},{"id":"5387541b-2687-555d-a059-123ed560c714","name":"Build verified receipt","type":"n8n-nodes-base.code","typeVersion":2,"position":[560,1200],"parameters":{"jsCode":"const p=$('Prepare upload').first().json,r=$('Parse claim').first().json;\nif(!['ahead','identical'].includes($json.status))throw Error('REMOTE_NOT_CONFIRMED');\nconst sha=r.route==='verify'?r.commitSha:$('Commit recorded').first().json.commitSha;\nif($json.merge_base_commit?.sha!==sha||!/^[a-f0-9]{40}$/.test(sha))throw Error('E_REMOTE_COMMIT');\nconst receipt=r.receipt||{success:true,repository:p.target.repository,repositoryId:p.target.repositoryId,branch:p.target.branch,commitSha:sha,url:'https://github.com/'+p.target.repository+'/commit/'+sha,uploadId:p.manifest.uploadId,manifestDigest:r.digest,fileCount:p.manifest.files.length,totalBytes:p.manifest.files.reduce((n,f)=>n+f.bytes,0),files:p.manifest.files.map(f=>({path:p.prefix+f.path,sourcePath:f.path,sha256:f.sha256,bytes:f.bytes})),productionReady:false};\nif(receipt.repository!==p.target.repository||receipt.repositoryId!==p.target.repositoryId||receipt.branch!==p.target.branch||receipt.commitSha!==sha||receipt.uploadId!==p.manifest.uploadId||receipt.manifestDigest!==r.digest||receipt.fileCount!==p.manifest.files.length||receipt.totalBytes!==p.manifest.files.reduce((n,f)=>n+f.bytes,0)||JSON.stringify(receipt.files)!==JSON.stringify(p.manifest.files.map(f=>({path:p.prefix+f.path,sourcePath:f.path,sha256:f.sha256,bytes:f.bytes}))))throw Error('E_RECEIPT_BINDING');return [{json:{receipt,replayed:r.route==='verify',processingMs:Date.now()-p.started}}];"}},{"id":"7d441aa4-7d94-5e49-85db-5fc0919e5989","name":"Confirm durable receipt","type":"n8n-nodes-base.executeCommand","typeVersion":1,"position":[840,1200],"parameters":{"executeOnce":true,"command":"={{ (()=>{const p={id:$('Prepare upload').first().json.manifest.uploadId,receipt:$('Build verified receipt').first().json.receipt};const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs confirmed '+quote(JSON.stringify(p));})() }}"}},{"id":"c95e1b38-ced4-5043-9f65-a64d3b7b8818","name":"Return durable receipt","type":"n8n-nodes-base.code","typeVersion":2,"position":[1120,1200],"parameters":{"jsCode":"const r=JSON.parse($json.stdout);if(r.error||r.state!=='confirmed'||!r.receipt)throw Error('E_CONFIRMATION');const b=$('Build verified receipt').first().json;return [{json:{...r.receipt,replayed:b.replayed,processingMs:b.processingMs}}];"}}],"connections":{"Binary upload":{"main":[[{"node":"Prepare upload","type":"main","index":0}]]},"Prepare upload":{"main":[[{"node":"Restore file references","type":"main","index":0}]]},"Restore file references":{"main":[[{"node":"Read binary bytes for GitHub","type":"main","index":0}]]},"Read binary bytes for GitHub":{"main":[[{"node":"Hash source bytes","type":"main","index":0}]]},"Hash source bytes":{"main":[[{"node":"Verify bytes and encode for GitHub","type":"main","index":0}]]},"Verify bytes and encode for GitHub":{"main":[[{"node":"Bundle checked","type":"main","index":0}]]},"Bundle checked":{"main":[[{"node":"Hash upload grant","type":"main","index":0}]]},"Hash upload grant":{"main":[[{"node":"Claim durable upload","type":"main","index":0}]]},"Claim durable upload":{"main":[[{"node":"Parse claim","type":"main","index":0}]]},"Parse claim":{"main":[[{"node":"Sign GitHub App JWT","type":"main","index":0}]]},"Sign GitHub App JWT":{"main":[[{"node":"Issue installation token","type":"main","index":0}]]},"Issue installation token":{"main":[[{"node":"Validate installation scope","type":"main","index":0}]]},"Validate installation scope":{"main":[[{"node":"Read repository","type":"main","index":0}]]},"Read repository":{"main":[[{"node":"Validate repository owner","type":"main","index":0}]]},"Validate repository owner":{"main":[[{"node":"Already has commit","type":"main","index":0}]]},"Already has commit":{"main":[[{"node":"Select replay commit","type":"main","index":0}],[{"node":"Read branch head","type":"main","index":0}]]},"Select replay commit":{"main":[[{"node":"Verify remote reachability","type":"main","index":0}]]},"Read branch head":{"main":[[{"node":"Validate branch head","type":"main","index":0}]]},"Validate branch head":{"main":[[{"node":"Read base commit","type":"main","index":0}]]},"Read base commit":{"main":[[{"node":"Blob requests","type":"main","index":0}]]},"Blob requests":{"main":[[{"node":"Create file blobs","type":"main","index":0}]]},"Create file blobs":{"main":[[{"node":"Collect tree entries","type":"main","index":0}]]},"Collect tree entries":{"main":[[{"node":"Create bundle tree","type":"main","index":0}]]},"Create bundle tree":{"main":[[{"node":"Validate bundle tree","type":"main","index":0}]]},"Validate bundle tree":{"main":[[{"node":"Create bundle commit","type":"main","index":0}]]},"Create bundle commit":{"main":[[{"node":"Validate bundle commit","type":"main","index":0}]]},"Validate bundle commit":{"main":[[{"node":"Journal committed SHA","type":"main","index":0}]]},"Journal committed SHA":{"main":[[{"node":"Commit recorded","type":"main","index":0}]]},"Commit recorded":{"main":[[{"node":"Publish branch fast forward","type":"main","index":0}]]},"Publish branch fast forward":{"main":[[{"node":"Select published commit","type":"main","index":0}]]},"Select published commit":{"main":[[{"node":"Verify remote reachability","type":"main","index":0}]]},"Verify remote reachability":{"main":[[{"node":"Build verified receipt","type":"main","index":0}]]},"Build verified receipt":{"main":[[{"node":"Confirm durable receipt","type":"main","index":0}]]},"Confirm durable receipt":{"main":[[{"node":"Return durable receipt","type":"main","index":0}]]}},"settings":{"executionOrder":"v1","executionTimeout":300,"saveDataSuccessExecution":"none","saveDataErrorExecution":"none","saveManualExecutions":false,"saveExecutionProgress":false,"availableInMCP":false}}];

async function installUniversalWorkflows() {
  // Reuses existing workflow IDs/credential references and stock n8n CLI.
  // A failed import/publish aborts startup; the public child is not started.
  for (const workflow of UNIVERSAL_WORKFLOWS) {
    if (!['workUploadGrantPilot', 'workOwnerRepositoryUploadV1'].includes(workflow.id)) throw Error('WORKFLOW_ID');
    const filename = '/data/.n8n/owner-upload-import-' + workflow.id + '.json';
    try {
      fs.writeFileSync(filename, JSON.stringify(workflow), { mode: 0o600 });
      await cli(['import:workflow', '--input=' + filename]);
      await cli(['publish:workflow', '--id=' + workflow.id]);
    } finally { if (fs.existsSync(filename)) fs.unlinkSync(filename); }
  }
}
// UNIVERSAL_WORKFLOWS_END
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
  const observationBefore = observationJournalSnapshot();
  let temporaryCleanup = null, confirmedCleanup = null;
  if(process.env.PILOT_LEDGER_B64) {
    const source=Buffer.from(process.env.PILOT_LEDGER_B64,'base64');
    const names=JSON.parse(process.env.UPLOAD_PRUNE_FAILED_TEMP_DIRS||'[]');
    // This exact allowlist is checked before deleting a failed pre-commit clone.
    // Run the verified helper from stdin first, so cleanup works on a full disk.
    if(names.length) {
      const result=cp.execFileSync('node',['-','prune-failed-temporary',JSON.stringify({names})],{input:source,encoding:'utf8'});
      const parsed=JSON.parse(result);
      if(parsed.error) throw Error('Temporary clone cleanup failed');
      temporaryCleanup = parsed;
      console.log('UPLOAD_TEMPORARY_CLEANUP',JSON.stringify(parsed));
    }
    fs.writeFileSync('/data/work/control/upload-ledger.cjs',source,{mode:0o600});
    const result=cp.execFileSync('node',['/data/work/control/upload-ledger.cjs','prune-confirmed','{}'],{encoding:'utf8'});
    const parsed=JSON.parse(result);
    if(parsed.error) throw Error('Confirmed clone cleanup failed');
    confirmedCleanup = parsed;
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
  if (persistent) {
    if (!githubPilotCredentials) throw Error('GITHUB_APP_UNAVAILABLE');
    await installUniversalWorkflows();
  }
  console.log('UPLOAD_OPS_OBSERVATION_V1', JSON.stringify(runtimeObservation({ before: observationBefore,
    after: observationJournalSnapshot(), temporaryCleanup, confirmedCleanup })));
  console.log(persistent ? 'UPLOAD_SERVICE_READY' : 'PILOT_READY_TO_START', persistent ? 'persistent' : new Date(deadline).toISOString());
  server = cp.spawn('n8n', ['start'], { stdio: 'inherit', env: runtimeChildEnvironment(process.env, persistent) });
  let shutdownRequested=false;
  process.on('SIGTERM', () => {shutdownRequested=true;server.kill('SIGTERM');});
  process.on('SIGINT', () => {shutdownRequested=true;server.kill('SIGTERM');});
  const [code] = await once(server, 'exit');
  if(watchdog) clearTimeout(watchdog);
  // A persistent service must surface an unexpected child exit to ON_FAILURE.
  process.exit(childExitCode(persistent,shutdownRequested,code));
}
main().catch(async e => { console.error('PILOT_BOOTSTRAP_FAILED', e.message); await stop(); process.exit(1); });

