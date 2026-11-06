"""Generate reviewable exported n8n JSON; no network or credentials are used."""
import copy,json,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parent
GRANT_TEMPLATE={'id': 'workUploadGrantPilot', 'name': 'Issue one upload grant (metadata only)', 'description': 'Upload to markmalina repositories via existing OAuth. Before execution read https://github.com/markmalina/automations/blob/main/tools/n8n-github-upload/UNIVERSAL_ROUTE.md. Metadata only; never display grants.', 'active': False, 'nodes': [{'parameters': {'httpMethod': 'POST', 'path': 'work-upload-grant-pilot-v1', 'authentication': 'headerAuth', 'responseMode': 'lastNode', 'responseData': 'firstEntryJson', 'responseBinaryPropertyName': 'data', 'options': {}}, 'id': '09b7fd9e-b1f8-4738-bfa4-5a80d05aef2f', 'name': 'OAuth grant input', 'type': 'n8n-nodes-base.webhook', 'typeVersion': 2, 'position': [0, 0], 'webhookId': '344a7789-4a7b-4863-aa2a-f35912078fc7', 'credentials': {'httpHeaderAuth': {'id': 'workPilotHeaderAuth', 'name': 'Work pilot header'}}}, {'id': 'b1f10b16-ffc1-4b93-a34e-6c048b86a4f2', 'name': 'Issue bound grant', 'type': 'n8n-nodes-base.executeCommand', 'typeVersion': 1, 'position': [0, 800], 'parameters': {'executeOnce': True, 'command': "={{ (()=>{const p=$json.body;if(!p || Object.keys(p).some(k=>!['id','digest','fileCount','totalBytes','target'].includes(k)))throw Error('Invalid grant fields');const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs grant '+quote(JSON.stringify(p));})() }}"}}, {'id': 'a7b921b1-98a6-408d-a78b-e4e4af21b16a', 'name': 'Return temporary grant', 'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': [600, 0], 'parameters': {'jsCode': 'const r=JSON.parse($json.stdout);if(r.error)throw Error(r.error);return [{json:r}];'}}], 'connections': {'OAuth grant input': {'main': [[{'node': 'Issue bound grant', 'type': 'main', 'index': 0}]]}, 'Issue bound grant': {'main': [[{'node': 'Return temporary grant', 'type': 'main', 'index': 0}]]}}, 'settings': {'executionOrder': 'v1', 'saveDataSuccessExecution': 'all', 'saveDataErrorExecution': 'none', 'saveManualExecutions': True, 'saveExecutionProgress': False, 'availableInMCP': True}}
nodes=[]; connections={}
def node(name,kind,parameters,version=2,**extra):
 n={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'n8n-upload-v2:'+name)),'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[len(nodes)%5*280,len(nodes)//5*200],'parameters':parameters,**extra}; nodes.append(n); return n

def code(name,source):return node(name,'code',{'jsCode':source})
def edge(a,b,out=0):
 outputs=connections.setdefault(a,{'main':[]})['main']
 while len(outputs)<=out:outputs.append([])
 outputs[out].append({'node':b,'type':'main','index':0})
def http(name,url,method='GET',body=None,jwt=False):
 auth="={{ 'Bearer '+$('Sign GitHub App JWT').first().json.token }}" if jwt else "={{ 'Bearer '+$('Issue installation token').first().json.token }}"
 p={'method':method,'url':url,'authentication':'none','sendHeaders':True,'headerParameters':{'parameters':[{'name':'Authorization','value':auth},{'name':'Accept','value':'application/vnd.github+json'},{'name':'X-GitHub-Api-Version','value':'2022-11-28'},{'name':'User-Agent','value':'markmalina-n8n-upload'}]},'options':{'timeout':60000,'redirect':{'redirect':{'followRedirects':False}}}}
 if body is not None:p.update(sendBody=True,specifyBody='json',jsonBody=body)
 return node(name,'httpRequest',p,4.2,retryOnFail=False)
def command(name,action,payload):
 expr="={{ (()=>{const p="+payload+";const quote=s=>String.fromCharCode(39)+s.replaceAll(String.fromCharCode(39),String.fromCharCode(39,92,39,39))+String.fromCharCode(39);return 'node /data/work/control/upload-ledger.cjs "+action+" '+quote(JSON.stringify(p));})() }}"
 return node(name,'executeCommand',{'executeOnce':True,'command':expr},1)

node('Binary upload','webhook',{'httpMethod':'POST','path':'work-owner-repository-upload-v1','authentication':'none','responseMode':'lastNode','responseData':'firstEntryJson','responseBinaryPropertyName':'data','options':{}},webhookId=str(uuid.uuid5(uuid.NAMESPACE_URL,'work-owner-repository-upload-v1')))
code('Prepare upload',r'''const input=$input.first();
const exact=(o,keys)=>o&&typeof o==='object'&&!Array.isArray(o)&&JSON.stringify(Object.keys(o).sort())===JSON.stringify(keys.sort());
let m;try{const raw=input.json.body.manifest;if(typeof raw!=='string'||raw.length>30000)throw Error();m=JSON.parse(raw);}catch{throw Error('E_MANIFEST');}
if(!exact(m,['schemaVersion','uploadId','target','files'])||m.schemaVersion!=='work-upload/v2'||!/^[a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12}$/.test(m.uploadId)||!Array.isArray(m.files)||m.files.length<1||m.files.length>100)throw Error('E_MANIFEST');
const t=m.target;
if(!exact(t,['repositoryId','repository','branch','prefix'])||!Number.isSafeInteger(t.repositoryId)||t.repositoryId<1||typeof t.repository!=='string'||!/^markmalina\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(t.repository))throw Error('E_TARGET');
if(typeof t.branch!=='string'||t.branch.length>200||!/^[A-Za-z0-9][A-Za-z0-9._\/-]*$/.test(t.branch)||t.branch.includes('..')||t.branch.includes('//')||t.branch.endsWith('/')||t.branch.endsWith('.')||t.branch.toUpperCase()==='HEAD'||t.branch.split('/').some(s=>s.startsWith('.')||s.toLowerCase().endsWith('.lock')))throw Error('E_BRANCH');
const safePath=s=>typeof s==='string'&&s.length>0&&s.isWellFormed()&&Buffer.byteLength(s,'utf8')<=2048&&s===s.normalize('NFC')&&!s.startsWith('/')&&!/[\\\u0000-\u001f\u007f,]/.test(s)&&!s.split('/').some(p=>!p||p==='.'||p==='..'||p.toLowerCase()==='.git'||Buffer.byteLength(p,'utf8')>255);
if(typeof t.prefix!=='string'||(t.prefix!==''&&!safePath(t.prefix)))throw Error('E_PREFIX');
const prefix=t.prefix?t.prefix+'/':'';const seen=new Set(),fields=new Set();let total=0;
for(const f of m.files){if(!exact(f,['field','path','bytes','sha256'])||!safePath(f.path)||typeof f.field!=='string'||!/^file(?:0|[1-9][0-9]?)$/.test(f.field)||fields.has(f.field)||!input.binary?.[f.field]||typeof f.sha256!=='string'||!/^[a-f0-9]{64}$/.test(f.sha256)||!Number.isSafeInteger(f.bytes)||f.bytes<0||f.bytes>32000000)throw Error('E_FILE');const path=prefix+f.path;if(!safePath(path))throw Error('E_RESOLVED_PATH');if(/^\.github\/workflows(?:\/|$)/i.test(path))throw Error('E_WORKFLOWS_PERMISSION');const folded=path.toLowerCase();if(seen.has(folded))throw Error('E_DUPLICATE_PATH');seen.add(folded);fields.add(f.field);total+=f.bytes;}
for(const p of seen){const parts=p.split('/');for(let i=1;i<parts.length;i++)if(seen.has(parts.slice(0,i).join('/')))throw Error('E_PATH_COLLISION');}
if(total>32000000||Object.keys(input.binary||{}).length!==m.files.length)throw Error('E_BUNDLE_LIMIT');
const grant=input.json.headers?.['x-work-upload-grant'];if(typeof grant!=='string'||!/^[a-f0-9]{64}$/.test(grant))throw Error('GRANT_DENIED');
return [{json:{manifest:m,target:t,prefix,started:Date.now(),owner:String($execution.id),grant,apiBase:'https://api.github.com/repos/'+t.repository.split('/').map(encodeURIComponent).join('/'),branchEncoded:encodeURIComponent(t.branch)}}];''')
code('Restore file references',r'''const p=$('Prepare upload').first().json,binary=$('Binary upload').first().binary;
return p.manifest.files.map(f=>({json:{...f,targetPath:p.prefix+f.path},binary:{data:binary[f.field]}}));''')
code('Read binary bytes for GitHub',r'''const items=$input.all(),result=[];
// Read binary while it is present on this node input. Crypto deliberately drops processed binary fields.
for(let i=0;i<items.length;i++){const buffer=await this.helpers.getBinaryDataBuffer(i,'data');if(buffer.length!==items[i].json.bytes)throw Error('E_SOURCE_SIZE');result.push({json:{...items[i].json,actualBytes:buffer.length,contentBase64:buffer.toString('base64')},binary:items[i].binary});}
return result;''')
node('Hash source bytes','crypto',{'action':'hash','binaryData':True,'binaryPropertyName':'data','type':'SHA256','encoding':'hex','dataPropertyName':'actualSha256'})
code('Verify bytes and encode for GitHub',r'''const items=$input.all();
if(items.length!==$('Prepare upload').first().json.manifest.files.length)throw Error('E_FILE_COUNT');
for(const item of items){if(item.json.actualSha256!==item.json.sha256)throw Error('E_SOURCE_DIGEST');if(item.json.actualBytes!==item.json.bytes)throw Error('E_SOURCE_SIZE');}
return items.map(item=>({json:item.json}));''')
code('Bundle checked',"return [{json:{fileCount:$input.all().length}}];")
node('Hash upload grant','crypto',{'action':'hash','binaryData':False,'value':"={{ $('Prepare upload').first().json.grant }}",'type':'SHA256','encoding':'hex','dataPropertyName':'grantHash'})
command('Claim durable upload','claim-granted-hash',"{id:$('Prepare upload').first().json.manifest.uploadId,manifest:$('Prepare upload').first().json.manifest,owner:$('Prepare upload').first().json.owner,grantHash:$('Hash upload grant').first().json.grantHash}")
code('Parse claim',r'''const r=JSON.parse($json.stdout),p=$('Prepare upload').first().json;
if(r.error)throw Error(r.error);if(!['new','verify'].includes(r.route))throw Error('UPLOAD_UNCERTAIN');
const canonical=v=>Array.isArray(v)?'['+v.map(canonical).join(',')+']':v&&typeof v==='object'?'{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}':JSON.stringify(v);
if(canonical(r.target)!==canonical(p.target)||r.id!==p.manifest.uploadId||!/^[a-f0-9]{64}$/.test(r.digest))throw Error('E_TARGET_BINDING');
if(r.route==='verify'&&!/^[a-f0-9]{40}$/.test(r.commitSha||''))throw Error('E_COMMIT');return [{json:r}];''')
node('Sign GitHub App JWT','jwt',{'operation':'sign','useJson':True,'claimsJson':"={{ JSON.stringify({iss:'5641721',iat:Math.floor(Date.now()/1000)-30,exp:Math.floor(Date.now()/1000)+300}) }}",'options':{}},1,credentials={'jwtAuth':{'id':'workPilotGithubJwt','name':'GitHub App signing key'}})
http('Issue installation token','https://api.github.com/app/installations/179245428/access_tokens','POST',"={{ JSON.stringify({repository_ids:[$('Prepare upload').first().json.target.repositoryId],permissions:{contents:'write'}}) }}",jwt=True)
code('Validate installation scope',r'''const r=$json,t=$('Prepare upload').first().json.target;
if(typeof r.token!=='string'||r.token.length<20||r.token.length>512||/\s/.test(r.token)||!Array.isArray(r.repositories)||r.repositories.length!==1||r.repositories[0].id!==t.repositoryId||r.repositories[0].full_name!==t.repository||!r.permissions||r.permissions.contents!=='write'||Object.entries(r.permissions).some(([k,v])=>!(k==='contents'&&v==='write'||k==='metadata'&&v==='read')))throw Error('E_INSTALLATION_SCOPE');
return [{json:{repositoryId:t.repositoryId}}];''')
http('Read repository',"={{ $('Prepare upload').first().json.apiBase }}")
code('Validate repository owner',r'''const t=$('Prepare upload').first().json.target;
if($json.id!==t.repositoryId||$json.full_name!==t.repository||$json.owner?.id!==23397294||$json.owner?.login!=='markmalina')throw Error('E_REPOSITORY_OWNER');return [{json:{verified:true}}];''')
node('Already has commit','if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},'conditions':[{'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'already-known-v2')),'leftValue':"={{ $('Parse claim').first().json.route==='verify' }}",'rightValue':True,'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},2.2)
code('Select replay commit',"return [{json:{commitSha:$('Parse claim').first().json.commitSha}}];")
http('Read branch head',"={{ $('Prepare upload').first().json.apiBase+'/git/ref/heads/'+$('Prepare upload').first().json.branchEncoded }}")
code('Validate branch head',r'''const p=$('Prepare upload').first().json;if($json.ref!=='refs/heads/'+p.target.branch||$json.object?.type!=='commit'||!/^[a-f0-9]{40}$/.test($json.object?.sha||''))throw Error('E_BRANCH_HEAD');return [{json:{parentSha:$json.object.sha}}];''')
http('Read base commit',"={{ $('Prepare upload').first().json.apiBase+'/git/commits/'+$('Validate branch head').first().json.parentSha }}")
code('Blob requests',r'''if($json.sha!==$('Validate branch head').first().json.parentSha||!/^[a-f0-9]{40}$/.test($json.tree?.sha||''))throw Error('E_BASE_TREE');return $('Verify bytes and encode for GitHub').all().map(i=>({json:i.json}));''')
http('Create file blobs',"={{ $('Prepare upload').first().json.apiBase+'/git/blobs' }}",'POST',"={{ JSON.stringify({content:$json.contentBase64,encoding:'base64'}) }}")['parameters']['options']['batching']={'batch':{'batchSize':1,'batchInterval':1000}}
code('Collect tree entries',r'''const blobs=$input.all(),files=$('Blob requests').all();if(blobs.length!==files.length||blobs.length<1)throw Error('E_BLOB_COUNT');const tree=blobs.map((b,i)=>{if(!/^[a-f0-9]{40}$/.test(b.json.sha||''))throw Error('E_BLOB_SHA');return {path:files[i].json.targetPath,mode:'100644',type:'blob',sha:b.json.sha};});return [{json:{tree,baseTree:$('Read base commit').first().json.tree.sha}}];''')
http('Create bundle tree',"={{ $('Prepare upload').first().json.apiBase+'/git/trees' }}",'POST',"={{ JSON.stringify({base_tree:$json.baseTree,tree:$json.tree}) }}")
code('Validate bundle tree',"if(!/^[a-f0-9]{40}$/.test($json.sha||''))throw Error('E_TREE_SHA');return [{json:{treeSha:$json.sha}}];")
http('Create bundle commit',"={{ $('Prepare upload').first().json.apiBase+'/git/commits' }}",'POST',"={{ JSON.stringify({message:'work-upload:'+$('Prepare upload').first().json.manifest.uploadId+':'+$('Parse claim').first().json.digest,tree:$json.treeSha,parents:[$('Validate branch head').first().json.parentSha]}) }}")
code('Validate bundle commit',r'''const r=$json;if(!/^[a-f0-9]{40}$/.test(r.sha||'')||r.parents?.length!==1||r.parents[0].sha!==$('Validate branch head').first().json.parentSha||r.tree?.sha!==$('Validate bundle tree').first().json.treeSha)throw Error('E_COMMIT_SHAPE');return [{json:{commitSha:r.sha}}];''')
command('Journal committed SHA','committed',"{id:$('Prepare upload').first().json.manifest.uploadId,owner:$('Prepare upload').first().json.owner,sha:$('Validate bundle commit').first().json.commitSha}")
code('Commit recorded',r'''const r=JSON.parse($json.stdout);if(r.error)throw Error(r.error);if(r.commitSha!==$('Validate bundle commit').first().json.commitSha||r.state!=='committed')throw Error('E_COMMIT_NOT_RECORDED');return [{json:{commitSha:r.commitSha}}];''')
http('Publish branch fast forward',"={{ $('Prepare upload').first().json.apiBase+'/git/refs/heads/'+$('Prepare upload').first().json.branchEncoded }}",'PATCH',"={{ JSON.stringify({sha:$('Commit recorded').first().json.commitSha,force:false}) }}")
code('Select published commit',r'''const sha=$('Commit recorded').first().json.commitSha,p=$('Prepare upload').first().json;if($json.ref!=='refs/heads/'+p.target.branch||$json.object?.sha!==sha)throw Error('E_REF_RESULT');return [{json:{commitSha:sha}}];''')
http('Verify remote reachability',"={{ $('Prepare upload').first().json.apiBase+'/compare/'+$json.commitSha+'...'+$('Prepare upload').first().json.branchEncoded }}")
code('Build verified receipt',r'''const p=$('Prepare upload').first().json,r=$('Parse claim').first().json;
if(!['ahead','identical'].includes($json.status))throw Error('REMOTE_NOT_CONFIRMED');
const sha=r.route==='verify'?r.commitSha:$('Commit recorded').first().json.commitSha;
if($json.merge_base_commit?.sha!==sha||!/^[a-f0-9]{40}$/.test(sha))throw Error('E_REMOTE_COMMIT');
const receipt=r.receipt||{success:true,repository:p.target.repository,repositoryId:p.target.repositoryId,branch:p.target.branch,commitSha:sha,url:'https://github.com/'+p.target.repository+'/commit/'+sha,uploadId:p.manifest.uploadId,manifestDigest:r.digest,fileCount:p.manifest.files.length,totalBytes:p.manifest.files.reduce((n,f)=>n+f.bytes,0),files:p.manifest.files.map(f=>({path:p.prefix+f.path,sourcePath:f.path,sha256:f.sha256,bytes:f.bytes})),productionReady:false};
if(receipt.repository!==p.target.repository||receipt.repositoryId!==p.target.repositoryId||receipt.branch!==p.target.branch||receipt.commitSha!==sha||receipt.uploadId!==p.manifest.uploadId||receipt.manifestDigest!==r.digest||receipt.fileCount!==p.manifest.files.length||receipt.totalBytes!==p.manifest.files.reduce((n,f)=>n+f.bytes,0)||JSON.stringify(receipt.files)!==JSON.stringify(p.manifest.files.map(f=>({path:p.prefix+f.path,sourcePath:f.path,sha256:f.sha256,bytes:f.bytes}))))throw Error('E_RECEIPT_BINDING');return [{json:{receipt,replayed:r.route==='verify',processingMs:Date.now()-p.started}}];''')
command('Confirm durable receipt','confirmed',"{id:$('Prepare upload').first().json.manifest.uploadId,receipt:$('Build verified receipt').first().json.receipt}")
code('Return durable receipt',r'''const r=JSON.parse($json.stdout);if(r.error||r.state!=='confirmed'||!r.receipt)throw Error('E_CONFIRMATION');const b=$('Build verified receipt').first().json;return [{json:{...r.receipt,replayed:b.replayed,processingMs:b.processingMs}}];''')
linear=['Binary upload','Prepare upload','Restore file references','Read binary bytes for GitHub','Hash source bytes','Verify bytes and encode for GitHub','Bundle checked','Hash upload grant','Claim durable upload','Parse claim','Sign GitHub App JWT','Issue installation token','Validate installation scope','Read repository','Validate repository owner','Already has commit']
for a,b in zip(linear,linear[1:]):edge(a,b)
edge('Already has commit','Select replay commit',0);edge('Select replay commit','Verify remote reachability')
new=['Read branch head','Validate branch head','Read base commit','Blob requests','Create file blobs','Collect tree entries','Create bundle tree','Validate bundle tree','Create bundle commit','Validate bundle commit','Journal committed SHA','Commit recorded','Publish branch fast forward','Select published commit','Verify remote reachability','Build verified receipt','Confirm durable receipt','Return durable receipt']
edge('Already has commit',new[0],1)
for a,b in zip(new,new[1:]):edge(a,b)
workflow={'id':'workOwnerRepositoryUploadV1','name':'Work binary upload to an owned GitHub repository','active':False,'description':'Candidate: target-bound manifest and grant, stock n8n nodes, one Git Data commit. No clone. Native/live acceptance pending.','nodes':nodes,'connections':connections,'settings':{'executionOrder':'v1','executionTimeout':300,'saveDataSuccessExecution':'none','saveDataErrorExecution':'none','saveManualExecutions':False,'saveExecutionProgress':False}}
grant=copy.deepcopy(GRANT_TEMPLATE)
grant['settings']['availableInMCP']=True
workflow['settings']['availableInMCP']=False
(ROOT/'owner-repository-upload.workflow.json').write_text(json.dumps(workflow,ensure_ascii=False,indent=2)+'\n')
grant['description']='Upload to markmalina repositories via existing OAuth. Before execution read https://github.com/markmalina/automations/blob/main/tools/n8n-github-upload/UNIVERSAL_ROUTE.md. Metadata only; never display grants.'
for n in grant['nodes']:
 if n['name']=='Issue bound grant':n['parameters']['command']=n['parameters']['command'].replace("['id','digest','fileCount','totalBytes']","['id','digest','fileCount','totalBytes','target']")
(ROOT/'upload-grant.workflow.json').write_text(json.dumps(grant,ensure_ascii=False,indent=2)+'\n')
print('Generated',len(nodes),'stock n8n nodes; no network calls made')
