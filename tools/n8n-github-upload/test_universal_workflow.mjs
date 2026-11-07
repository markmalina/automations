import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
const root=new URL('./',import.meta.url);
const w=JSON.parse(fs.readFileSync(new URL('owner-repository-upload.workflow.json',root)));
const grant=JSON.parse(fs.readFileSync(new URL('upload-grant.workflow.json',root)));
const byName=Object.fromEntries(w.nodes.map(n=>[n.name,n]));
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const sha=c=>c.repeat(40);
const fixture=(count=2)=>{
 const buffers=Array.from({length:count},(_,i)=>Buffer.from([0,255,i,13,10]));
 const manifest={schemaVersion:'work-upload/v2',uploadId:'11111111-1111-4111-8111-111111111111',target:{repositoryId:123456,repository:'markmalina/another-repository',branch:'test/universal',prefix:'папка'},files:buffers.map((b,i)=>({field:'file'+i,path:i?'sub/файл '+i+'.bin':'zero.bin',bytes:b.length,sha256:hash(b)}))};
 const input={json:{body:{manifest:JSON.stringify(manifest)},headers:{'x-work-upload-grant':'a'.repeat(64)}},binary:Object.fromEntries(manifest.files.map(f=>[f.field,{id:'binary:'+f.field}]))};
 return {manifest,buffers,input};
};
async function run(name,{items=[],refs={},json=items[0]?.json,bufferAt=async()=>Buffer.alloc(0)}={}){
 const fn=new AsyncFunction('$input','$','$json','$execution',byName[name].parameters.jsCode);
 const lookup=n=>({first:()=>{if(!refs[n]?.length)throw Error('Missing node '+n);return refs[n][0];},all:()=>refs[n]||[]});
 return fn.call({helpers:{getBinaryDataBuffer:bufferAt}},{first:()=>items[0],all:()=>items},lookup,json,{id:'1234'});
}
async function prepared(f=fixture()){
 const p=await run('Prepare upload',{items:[f.input]});return {...f,p,refs:{'Prepare upload':p,'Binary upload':[f.input]}};
}
test('all Code node snippets compile and graph references are closed',()=>{
 for(const n of w.nodes)if(n.type==='n8n-nodes-base.code')assert.doesNotThrow(()=>new AsyncFunction('$input','$','$json','$execution',n.parameters.jsCode),n.name);
 assert.equal(new Set(w.nodes.map(n=>n.name)).size,w.nodes.length);
 for(const [from,o]of Object.entries(w.connections)){assert.ok(byName[from]);for(const branch of o.main)for(const e of branch)assert.ok(byName[e.node]);}
});
test('stock nodes only; no clone/filesystem payload implementation or unpinned arbitrary request target',()=>{
 const allowed=new Set(['webhook','code','crypto','executeCommand','jwt','httpRequest','if'].map(x=>'n8n-nodes-base.'+x));
 for(const n of w.nodes){assert.ok(allowed.has(n.type));if(n.type==='n8n-nodes-base.httpRequest'){assert.equal(n.parameters.options.redirect.redirect.followRedirects,false);assert.equal(n.retryOnFail,false);}}
 assert.equal(w.nodes.filter(n=>n.type==='n8n-nodes-base.jwt').length,1);
 assert.equal(byName['Sign GitHub App JWT'].credentials.jwtAuth.id,'workPilotGithubJwt');
});
test('universal binary workflow disables execution/MCP storage, grant preserves existing OAuth identity',()=>{
 assert.equal(w.id,'workOwnerRepositoryUploadV1');assert.equal(w.settings.availableInMCP,false);
 assert.equal(w.settings.saveDataSuccessExecution,'none');assert.equal(w.settings.saveDataErrorExecution,'none');assert.equal(w.settings.saveManualExecutions,false);
 assert.equal(grant.id,'workUploadGrantPilot');assert.equal(grant.settings.availableInMCP,true);
 assert.equal(grant.nodes[0].credentials.httpHeaderAuth.id,'workPilotHeaderAuth');
 assert.ok(grant.nodes.find(n=>n.name==='Issue bound grant').parameters.command.includes("'target'"));
});
test('v2 preparation accepts another owned repository, unicode paths, and root prefix',async()=>{
 const f=await prepared();assert.deepEqual(f.p[0].json.target,f.manifest.target);assert.equal(f.p[0].json.prefix,'папка/');assert.equal(f.p[0].json.apiBase,'https://api.github.com/repos/markmalina/another-repository');
 const rootf=fixture();rootf.manifest.target.prefix='';rootf.input.json.body.manifest=JSON.stringify(rootf.manifest);
 assert.equal((await prepared(rootf)).p[0].json.prefix,'');
});
for(const [label,modify]of [
 ['foreign owner',m=>m.target.repository='other/repo'],['dot repository',m=>m.target.repository='markmalina/.repo'],['owner traversal',m=>m.target.repository='markmalina/../x'],['wrong id type',m=>m.target.repositoryId='123'],['branch option',m=>m.target.branch='--all'],['branch traversal',m=>m.target.branch='foo/../bar'],['branch lock',m=>m.target.branch='foo.lock'],['branch HEAD',m=>m.target.branch='head'],['branch uppercase lock',m=>m.target.branch='foo.LOCK'],['branch dot component',m=>m.target.branch='foo/.bar'],['path traversal',m=>m.files[0].path='../key'],['oversized segment',m=>m.files[0].path='a'.repeat(256)],['bad Unicode',m=>m.files[0].path='\ud800'],['git metadata',m=>m.files[0].path='.git/config'],['absolute',m=>m.files[0].path='/etc/passwd'],['backslash',m=>m.files[0].path='a\\b'],['control',m=>m.files[0].path='a\nb'],['noncanonical field',m=>m.files[0].field='file00'],['generic field',m=>m.files[0].field='other'],['duplicate field',m=>m.files[1].field=m.files[0].field],['duplicate path',m=>m.files[1].path=m.files[0].path],['bad hash',m=>m.files[0].sha256='x'.repeat(64)],['oversize',m=>m.files[0].bytes=32000001],['unknown manifest key',m=>m.apiBase='https://attacker.invalid'],['target unknown key',m=>m.target.url='https://attacker.invalid'],['workflow path',m=>{m.target.prefix='';m.files[0].path='.github/workflows/ci.yml';}],
 ])test('pre-GitHub preparation rejects '+label,async()=>{const f=fixture();modify(f.manifest);f.input.json.body.manifest=JSON.stringify(f.manifest);await assert.rejects(run('Prepare upload',{items:[f.input]}));});
test('nonadjacent ancestor collision is rejected (a, a-b, a/x)',async()=>{
 const f=fixture(3);f.manifest.target.prefix='';['a','a-b','a/x'].forEach((p,i)=>f.manifest.files[i].path=p);f.input.json.body.manifest=JSON.stringify(f.manifest);await assert.rejects(run('Prepare upload',{items:[f.input]}),/E_PATH_COLLISION/);
});
test('100 files pass and 101 fail before any provider node',async()=>{
 assert.equal((await prepared(fixture(100))).p[0].json.manifest.files.length,100);
 await assert.rejects(prepared(fixture(101)),/E_MANIFEST/);
});
test('metadata length is bounded for ExecuteCommand argument safety',async()=>{
 const f=fixture();f.input.json.body.manifest=' '.repeat(30001);await assert.rejects(run('Prepare upload',{items:[f.input]}),/E_MANIFEST/);
});
test('grant shape is rejected before hash/blob/token calls',async()=>{
 const f=fixture();f.input.json.headers['x-work-upload-grant']='not-a-grant';await assert.rejects(run('Prepare upload',{items:[f.input]}),/GRANT_DENIED/);
});
test('actual binary sizes and hashes are checked before metadata journal/GitHub path',async()=>{
 const f=await prepared();const refs=f.refs;const files=await run('Restore file references',{refs});
 const read=await run('Read binary bytes for GitHub',{items:files,refs,bufferAt:async i=>f.buffers[i]});
 assert.ok(read.every(i=>i.binary?.data));
 // CryptoV2 drops the binary field after hashing: validate without relying on restoring a remote worker's input.
 const hashed=read.map((i,n)=>({json:{...i.json,actualSha256:hash(f.buffers[n])}}));
 const checked=await run('Verify bytes and encode for GitHub',{items:hashed,refs});
 assert.deepEqual(Buffer.from(checked[1].json.contentBase64,'base64'),f.buffers[1]);
 hashed[0].json.actualSha256='0'.repeat(64);await assert.rejects(run('Verify bytes and encode for GitHub',{items:hashed,refs}),/E_SOURCE_DIGEST/);
 await assert.rejects(run('Read binary bytes for GitHub',{items:files,refs,bufferAt:async i=>i?f.buffers[i]:Buffer.alloc(1)}),/E_SOURCE_SIZE/);
 assert.equal(w.connections['Restore file references'].main[0][0].node,'Read binary bytes for GitHub');
 assert.equal(w.connections['Read binary bytes for GitHub'].main[0][0].node,'Hash source bytes');
});
test('raw grant is SHA256-hashed by stock text Crypto before ExecuteCommand; command receives only grantHash',async()=>{
 const f=await prepared(),token=f.p[0].json.grant,grantHash=hash(Buffer.from(token));
 const n=byName['Hash upload grant'];
 assert.equal(n.type,'n8n-nodes-base.crypto');assert.equal(n.parameters.binaryData,false);assert.equal(n.parameters.action,'hash');assert.equal(n.parameters.type,'SHA256');assert.equal(n.parameters.encoding,'hex');assert.equal(n.parameters.dataPropertyName,'grantHash');
 assert.equal(n.parameters.value,"={{ $('Prepare upload').first().json.grant }}");
 const expr=byName['Claim durable upload'].parameters.command;
 const lookup=name=>({first:()=>name==='Hash upload grant'?{json:{grantHash}}:f.refs[name][0]});
 const command=new Function('$','return ('+expr.slice(3,-2)+');')(lookup);
 assert.ok(command.includes(' claim-granted-hash '));assert.ok(command.includes(grantHash));assert.ok(!command.includes(token));assert.ok(!command.includes('\"grant\":'));
 assert.equal(w.connections['Bundle checked'].main[0][0].node,'Hash upload grant');assert.equal(w.connections['Hash upload grant'].main[0][0].node,'Claim durable upload');
 for(const n of w.nodes.filter(n=>n.type==='n8n-nodes-base.executeCommand'))assert.ok(!n.parameters.command.includes('json.grant}'));
});
test('blob requests are throttled by supported HTTP batching parameters and never retried automatically',()=>{
 const n=byName['Create file blobs'];assert.deepEqual(n.parameters.options.batching,{batch:{batchSize:1,batchInterval:1000}});assert.equal(n.retryOnFail,false);
});
test('durable claim must bind exact target before JWT/token node',async()=>{
 const f=await prepared();const r={id:f.manifest.uploadId,target:f.manifest.target,route:'new',digest:'a'.repeat(64)};
 assert.equal((await run('Parse claim',{json:{stdout:JSON.stringify(r)},refs:f.refs}))[0].json.route,'new');
 const wrong={...r,target:{...r.target,repositoryId:999}};await assert.rejects(run('Parse claim',{json:{stdout:JSON.stringify(wrong)},refs:f.refs}),/E_TARGET_BINDING/);
 await assert.rejects(run('Parse claim',{json:{stdout:JSON.stringify({...r,route:'uncertain'})},refs:f.refs}),/UPLOAD_UNCERTAIN/);
});
test('installation token request is restricted to exactly chosen repository and contents write',()=>{
 const body=byName['Issue installation token'].parameters.jsonBody;
 assert.ok(body.includes('repository_ids:'));assert.ok(body.includes('.target.repositoryId'));assert.ok(body.includes("permissions:{contents:'write'}"));
 assert.equal(byName['Issue installation token'].parameters.url,'https://api.github.com/app/installations/179245428/access_tokens');
});
test('installation request expression evaluates to exact selected repository and permissions',()=>{
 const expression=byName['Issue installation token'].parameters.jsonBody;
 assert.ok(expression.startsWith('={{')&&expression.endsWith('}}'));
 for(const repositoryId of [91717001,1448151721]){
  const lookup=name=>{assert.equal(name,'Prepare upload');return {first:()=>({json:{target:{repositoryId}}})};};
  const body=new Function('$','return ('+expression.slice(3,-2)+');')(lookup);
  assert.deepEqual(JSON.parse(body),{repository_ids:[repositoryId],permissions:{contents:'write'}});
 }
});
test('foreign/multi-repo/broad-permission token responses and foreign owner are rejected',async()=>{
 const f=await prepared(),target=f.manifest.target;
 const token={token:'test-fixture-token-not-a-secret',permissions:{contents:'write',metadata:'read'},repositories:[{id:target.repositoryId,full_name:target.repository}]};
 await run('Validate installation scope',{json:token,refs:f.refs});
 for(const bad of [{...token,repositories:[...token.repositories,...token.repositories]},{...token,repositories:[{...token.repositories[0],id:1}]},{...token,permissions:{...token.permissions,workflows:'write'}}])await assert.rejects(run('Validate installation scope',{json:bad,refs:f.refs}),/E_INSTALLATION_SCOPE/);
 await run('Validate repository owner',{json:{id:target.repositoryId,full_name:target.repository,owner:{id:23397294,login:'markmalina'}},refs:f.refs});
 await assert.rejects(run('Validate repository owner',{json:{id:target.repositoryId,full_name:target.repository,owner:{id:123,login:'markmalina'}},refs:f.refs}),/E_REPOSITORY_OWNER/);
});
test('tree contains only supplied paths with independently returned blob SHAs',async()=>{
 const files=[{json:{targetPath:'папка/a'}},{json:{targetPath:'папка/b'}}];const tree=await run('Collect tree entries',{items:[{json:{sha:sha('a')}},{json:{sha:sha('b')}}],refs:{'Blob requests':files,'Read base commit':[{json:{tree:{sha:sha('c')}}}]}});
 assert.deepEqual(tree[0].json,{baseTree:sha('c'),tree:[{path:'папка/a',mode:'100644',type:'blob',sha:sha('a')},{path:'папка/b',mode:'100644',type:'blob',sha:sha('b')}]});
});
test('branch publish is non-force, commit is recorded before publish, only one commit node',()=>{
 assert.ok(byName['Publish branch fast forward'].parameters.jsonBody.includes('force:false'));
 assert.equal(w.nodes.filter(n=>n.name==='Create bundle commit').length,1);
 const next=n=>w.connections[n]?.main.flat().map(e=>e.node)||[];
 assert.deepEqual(next('Create bundle commit'),['Validate bundle commit']);assert.deepEqual(next('Validate bundle commit'),['Journal committed SHA']);assert.deepEqual(next('Journal committed SHA'),['Commit recorded']);assert.deepEqual(next('Commit recorded'),['Publish branch fast forward']);
 assert.deepEqual(next('Select replay commit'),['Verify remote reachability']);
 assert.equal(w.connections['Already has commit'].main[0][0].node,'Select replay commit');
});
test('remote receipt requires ancestry of the exact recorded commit and rejects wrong metadata',async()=>{
 const f=await prepared();const record={route:'new',digest:'a'.repeat(64),receipt:null};const refs={...f.refs,'Parse claim':[{json:record}],'Commit recorded':[{json:{commitSha:sha('d')}}]};
 const result=await run('Build verified receipt',{json:{status:'ahead',merge_base_commit:{sha:sha('d')}},refs});
 assert.equal(result[0].json.receipt.repository,f.manifest.target.repository);assert.equal(result[0].json.receipt.commitSha,sha('d'));assert.equal(result[0].json.receipt.fileCount,2);
 await assert.rejects(run('Build verified receipt',{json:{status:'ahead',merge_base_commit:{sha:sha('e')}},refs}),/E_REMOTE_COMMIT/);
 await assert.rejects(run('Build verified receipt',{json:{status:'behind',merge_base_commit:{sha:sha('d')}},refs}),/REMOTE_NOT_CONFIRMED/);
 const replay={...record,route:'verify',commitSha:sha('d'),receipt:result[0].json.receipt};refs['Parse claim']=[{json:replay}];delete refs['Commit recorded'];
 const replayed=await run('Build verified receipt',{json:{status:'identical',merge_base_commit:{sha:sha('d')}},refs});assert.equal(replayed[0].json.replayed,true);
 replay.receipt={...replay.receipt,totalBytes:999};await assert.rejects(run('Build verified receipt',{json:{status:'identical',merge_base_commit:{sha:sha('d')}},refs}),/E_RECEIPT_BINDING/);
});

test('field grammar rejects noncanonical names even when matching binary exists',async()=>{
 for(const field of ['file00','file000','file100','other']){const f=fixture();f.manifest.files[0].field=field;f.input.binary[field]=f.input.binary.file0;delete f.input.binary.file0;f.input.json.body.manifest=JSON.stringify(f.manifest);await assert.rejects(run('Prepare upload',{items:[f.input]}),/E_FILE/);}
});
test('casefold duplicate/ancestor collisions match journal policy',async()=>{
 const f=fixture(3);f.manifest.target.prefix='';['A','a-b','a/x'].forEach((p,i)=>f.manifest.files[i].path=p);f.input.json.body.manifest=JSON.stringify(f.manifest);await assert.rejects(run('Prepare upload',{items:[f.input]}),/E_PATH_COLLISION/);
 const d=fixture();d.manifest.files[1].path=d.manifest.files[0].path.toUpperCase();d.input.json.body.manifest=JSON.stringify(d.manifest);await assert.rejects(run('Prepare upload',{items:[d.input]}),/E_DUPLICATE_PATH/);
});
test('generator is self-contained and byte reproducible without sibling baseline files',()=>{
 const dir=fs.mkdtempSync(path.join(fileURLToPath(root),'.repro-'));
 try{fs.copyFileSync(new URL('build_universal_workflow.py',root),path.join(dir,'build_universal_workflow.py'));const r=spawnSync('python',['build_universal_workflow.py'],{cwd:dir,encoding:'utf8'});assert.equal(r.status,0,r.stderr);for(const name of ['owner-repository-upload.workflow.json','upload-grant.workflow.json'])assert.deepEqual(fs.readFileSync(path.join(dir,name)),fs.readFileSync(new URL(name,root)));}finally{fs.rmSync(dir,{recursive:true,force:true});}
});

test('binary JSON declares native workflow.settings.executionTimeout in seconds',()=>{assert.equal(w.settings.executionTimeout,300);assert.ok(Number.isInteger(w.settings.executionTimeout));assert.ok(w.settings.executionTimeout>0);});
