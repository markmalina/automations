// Small transactional metadata journal; HTTP, binary I/O and Git remain stock n8n nodes.
// No persistent credentials or file contents are accepted here. Single service/volume only.
const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const directory = process.env.UPLOAD_LEDGER_DIR || '/data/work/control';
function initializationFailed() {
 console.log(JSON.stringify({error:'E_LEDGER_UNAVAILABLE'}));
 process.exit(0);
}
try {fs.mkdirSync(directory, {recursive:true,mode:0o700});} catch {initializationFailed();}

const cloneRoot = process.env.UPLOAD_GIT_ROOT || '/data/work/git';
const temporaryRoot = path.dirname(cloneRoot);
function safeDirectory(candidate, parent) {
 try {
  if(fs.realpathSync(parent)!==path.resolve(parent)) return 'unsafe_parent';
  const s=fs.lstatSync(candidate);
  return s.isDirectory() && !s.isSymbolicLink() ? 'directory' : 'unsafe_path';
 } catch(e) {return e.code==='ENOENT' ? 'absent' : 'inspect_failed';}
}
function pruneConfirmedClone(id) {
 if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(id)) return {state:'invalid_id'};
 const candidate=path.join(cloneRoot,'pilot-'+id);
 const state=safeDirectory(candidate,cloneRoot);
 if(state!=='directory') return {state};
 try {fs.rmSync(candidate,{recursive:true,force:true});return {state:'removed'};}
 catch(e) {return {state:'cleanup_failed',code:String(e.code||'UNKNOWN')};}
}
function pruneFailedTemporary(names) {
 if(!Array.isArray(names)||names.length>10) throw Error('Invalid temporary cleanup list');
 const results=[];
 for(const name of names) {
  if(typeof name!=='string'||!/^\.n8n-clone-[a-f0-9]{16,64}$/.test(name)) throw Error('Invalid temporary clone name');
  const candidate=path.join(temporaryRoot,name);
  const state=safeDirectory(candidate,temporaryRoot);
  if(state!=='directory'){results.push({name,state});continue;}
  const git=path.join(candidate,'.git');
  if(safeDirectory(git,candidate)!=='directory'){results.push({name,state:'missing_git_directory'});continue;}
  const configPath=path.join(git,'config');
  const configStat=fs.lstatSync(configPath);
  if(!configStat.isFile()||configStat.isSymbolicLink()||configStat.size>1000000){results.push({name,state:'unverified_config'});continue;}
  const config=fs.readFileSync(configPath,'utf8');
  const origin=config.split(/(?=^\[)/m).find(section=>/^\[remote "origin"\]/.test(section));
  if(!origin||!/^\s*url\s*=\s*https:\/\/github\.com\/markmalina\/freelance\.git\s*$/m.test(origin)){
   results.push({name,state:'unexpected_origin'});continue;
  }
  const logPath=path.join(git,'logs','HEAD');
  if(!fs.existsSync(logPath)||fs.lstatSync(logPath).isSymbolicLink()||fs.statSync(logPath).size>1000000){
   results.push({name,state:'unverified_history'});continue;
  }
  const log=fs.readFileSync(logPath,'utf8');
  if(!log.includes('clone: from ')||/\t(?:commit|reset|rebase|merge|cherry-pick)/.test(log)){
   results.push({name,state:'local_changes_in_history'});continue;
  }
  try {fs.rmSync(candidate,{recursive:true,force:true});results.push({name,state:'removed'});}
  catch(e){results.push({name,state:'cleanup_failed',code:String(e.code||'UNKNOWN')});}
 }
 return {results};
}
if(process.argv[2]==='prune-failed-temporary'){
 try {console.log(JSON.stringify(pruneFailedTemporary(JSON.parse(process.argv[3]||'{}').names)));}
 catch(e){console.log(JSON.stringify({error:e.message}));process.exitCode=1;}
 process.exit(process.exitCode||0);
}

let db;
try {
 db = new DatabaseSync(path.join(directory,'uploads.sqlite'));
 db.exec('PRAGMA busy_timeout=15000; PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;');
 db.exec(`CREATE TABLE IF NOT EXISTS uploads (
 id TEXT PRIMARY KEY, digest TEXT NOT NULL, manifest TEXT NOT NULL,
 owner TEXT NOT NULL, state TEXT NOT NULL, commit_sha TEXT, receipt TEXT,
 created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);`);
 db.exec(`CREATE TABLE IF NOT EXISTS grants (
 token_hash TEXT PRIMARY KEY, upload_id TEXT NOT NULL, digest TEXT NOT NULL,
 file_count INTEGER NOT NULL, total_bytes INTEGER NOT NULL, expires_at INTEGER NOT NULL
);`);
// Additive, serialized migration. Existing upload rows and grants are never reset.
 db.exec('BEGIN IMMEDIATE');
 try {
  if(!db.prepare('PRAGMA table_info(grants)').all().some(column=>column.name==='target_json'))
   db.exec('ALTER TABLE grants ADD COLUMN target_json TEXT');
  db.exec('COMMIT');
 } catch(e) {db.exec('ROLLBACK');throw e;}
} catch {
 try {if(db)db.close();} catch {}
 initializationFailed();
}
function canonical(v) {
 if(Array.isArray(v)) return '['+v.map(canonical).join(',')+']';
 if(v!==null && typeof v==='object') return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
 return JSON.stringify(v);
}
const own=(object,key)=>Object.prototype.hasOwnProperty.call(object,key);
const uuid=value=>typeof value==='string'&&/^[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}$/.test(value);
function exactKeys(value,names,code) {
 if(!value||typeof value!=='object'||Array.isArray(value)||canonical(Object.keys(value).sort())!==canonical([...names].sort())) throw Error(code);
}
function relativePath(value,empty=false) {
 if(typeof value!=='string'||(!empty&&!value)||!value.isWellFormed()||Buffer.byteLength(value)>2048||value!==value.normalize('NFC')||/[\\\u0000-\u001f\u007f,]/u.test(value)) throw Error('E_PATH');
 if(!value&&empty)return value;
 if(value.split('/').some(part=>!part||part==='.'||part==='..'||part.toLowerCase()==='.git'||Buffer.byteLength(part)>255)) throw Error('E_PATH');
 return value;
}
function validateTarget(value) {
 exactKeys(value,['repositoryId','repository','branch','prefix'],'E_TARGET');
 if(!Number.isSafeInteger(value.repositoryId)||value.repositoryId<1||
    typeof value.repository!=='string'||!/^markmalina\/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(value.repository)||
    typeof value.branch!=='string'||!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$/.test(value.branch)||
    value.branch.includes('..')||value.branch.includes('//')||value.branch.includes('@{')||/[/.]$/.test(value.branch)||
    value.branch.toUpperCase()==='HEAD'||value.branch.split('/').some(part=>part.startsWith('.')||part.toLowerCase().endsWith('.lock'))) throw Error('E_TARGET');
 relativePath(value.prefix,true);
 if(value.prefix.toLowerCase()==='.github/workflows'||value.prefix.toLowerCase().startsWith('.github/workflows/')) throw Error('E_WORKFLOWS_PERMISSION');
 return {repositoryId:value.repositoryId,repository:value.repository,branch:value.branch,prefix:value.prefix};
}
function isUniversal(manifest) {
 return Boolean(manifest&&typeof manifest==='object'&&(own(manifest,'target')||own(manifest,'schemaVersion')));
}
function validateUniversalManifest(manifest) {
 exactKeys(manifest,['schemaVersion','uploadId','target','files'],'E_MANIFEST');
 if(manifest.schemaVersion!=='work-upload/v2'||!uuid(manifest.uploadId)||!Array.isArray(manifest.files)||manifest.files.length<1||manifest.files.length>100) throw Error('E_MANIFEST');
 const target=validateTarget(manifest.target),prefix=target.prefix?target.prefix+'/':'';
 const fields=new Set(),paths=new Set();let totalBytes=0;
 for(const file of manifest.files) {
  exactKeys(file,['field','path','bytes','sha256'],'E_MANIFEST');
  if(typeof file.field!=='string'||!/^file(?:0|[1-9][0-9]?)$/.test(file.field)||fields.has(file.field)||
     !Number.isSafeInteger(file.bytes)||file.bytes<0||typeof file.sha256!=='string'||!/^[0-9a-f]{64}$/.test(file.sha256)) throw Error('E_MANIFEST');
  fields.add(file.field);relativePath(file.path);
  const resolved=prefix+file.path;relativePath(resolved);
  const folded=resolved.toLowerCase();
  if(folded==='.github/workflows'||folded.startsWith('.github/workflows/')) throw Error('E_WORKFLOWS_PERMISSION');
  if([...paths].some(path=>folded===path||folded.startsWith(path+'/')||path.startsWith(folded+'/'))) throw Error('E_PATH_COLLISION');
  paths.add(folded);totalBytes+=file.bytes;
  if(!Number.isSafeInteger(totalBytes)||totalBytes>32000000) throw Error('E_MANIFEST_LIMIT');
 }
 if(canonical(manifest).length>30000) throw Error('E_MANIFEST_TOO_LARGE');
 return {target,prefix,fileCount:manifest.files.length,totalBytes};
}
function storedTarget(row) {
 const manifest=JSON.parse(row.manifest);
 return isUniversal(manifest)?validateUniversalManifest(manifest):{
  target:{repositoryId:1378687935,repository:'markmalina/freelance',branch:'test/n8n-upload-20261106',prefix:'n8n-retry-tests/'+row.id},
  prefix:'n8n-retry-tests/'+row.id+'/'
 };
}
function run(action,input) {
 const now=Date.now();
 if(action==='prune-confirmed') {
  const rows=db.prepare("SELECT id FROM uploads WHERE state='confirmed' AND commit_sha IS NOT NULL AND receipt IS NOT NULL").all();
  return {results:rows.map(row=>({id:row.id,...pruneConfirmedClone(row.id)}))};
 }
 if(!uuid(input.id)) throw Error('Invalid upload ID');
 if(action==='validate-manifest') {
  if(input.manifest?.uploadId!==input.id)throw Error('E_MANIFEST');
  return {valid:true,...validateUniversalManifest(input.manifest)};
 }
 db.exec('BEGIN IMMEDIATE');
 try {
  let row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
  if(action==='grant') {
   if(own(input,'target'))exactKeys(input,['id','digest','fileCount','totalBytes','target'],'E_GRANT');
   if(!/^[0-9a-f]{64}$/.test(input.digest||'') || !Number.isInteger(input.fileCount) || input.fileCount<1 || input.fileCount>100 || !Number.isSafeInteger(input.totalBytes) || input.totalBytes<0 || input.totalBytes>32000000) throw Error('Invalid grant binding');
   const target=own(input,'target')?validateTarget(input.target):null;
   if(row && row.digest!==input.digest) throw Error('ID_CONFLICT');
   if(row&&((isUniversal(JSON.parse(row.manifest)))!==Boolean(target)||target&&canonical(storedTarget(row).target)!==canonical(target))) throw Error('ID_CONFLICT');
   const token=crypto.randomBytes(32).toString('hex');
   const hash=crypto.createHash('sha256').update(token).digest('hex');
   const expiresAt=now+600000;
   db.prepare('DELETE FROM grants WHERE expires_at<?').run(now);
   db.prepare('INSERT INTO grants (token_hash,upload_id,digest,file_count,total_bytes,expires_at,target_json) VALUES (?,?,?,?,?,?,?)').run(hash,input.id,input.digest,input.fileCount,input.totalBytes,expiresAt,target?canonical(target):null);
   db.exec('COMMIT');
   return {uploadId:input.id,uploadUrl:'https://n8n-upload-pilot.up.railway.app/webhook/'+(target?'work-owner-repository-upload-v1':'work-fresh-token-upload-pilot-v1'),headerName:'X-Work-Upload-Grant',token,expiresAt:new Date(expiresAt).toISOString(),repository:target?target.repository:'markmalina/freelance',branch:target?target.branch:'test/n8n-upload-20261106',...(target?{target}:{}),manifestDigest:input.digest,productionReady:false};
  }
  if(action==='claim-granted'||action==='claim-granted-hash') {
   const hashed=action==='claim-granted-hash';
   if(!hashed&&isUniversal(input.manifest))throw Error('GRANT_DENIED');
   if(hashed&&(!isUniversal(input.manifest)||input.manifest.schemaVersion!=='work-upload/v2'))throw Error('GRANT_DENIED');
   if(!/^[0-9a-f]{64}$/.test((hashed?input.grantHash:input.grant)||'')) throw Error('GRANT_DENIED');
   const hash=hashed?input.grantHash:crypto.createHash('sha256').update(input.grant).digest('hex');
   const grant=db.prepare('SELECT * FROM grants WHERE token_hash=?').get(hash);
   const digest=crypto.createHash('sha256').update(canonical(input.manifest)).digest('hex');
   if(!grant || grant.upload_id!==input.id || grant.digest!==digest || grant.expires_at<now || grant.file_count!==input.manifest?.files?.length || grant.total_bytes!==input.manifest.files.reduce((n,f)=>n+f.bytes,0)) throw Error('GRANT_DENIED');
   const universal=isUniversal(input.manifest);
   if(grant.target_json===null?universal:!universal||canonical(validateUniversalManifest(input.manifest).target)!==grant.target_json) throw Error('GRANT_DENIED');
   action='claim';
  }
  if(action==='claim') {
   const manifest=canonical(input.manifest);
   const digest=crypto.createHash('sha256').update(manifest).digest('hex');
   if(input.manifest?.uploadId!==input.id || typeof input.owner!=='string' || !input.owner) throw Error('Invalid claim');
   if(row && row.digest!==digest) throw Error('ID_CONFLICT: upload ID already binds different metadata');
   if(isUniversal(input.manifest))validateUniversalManifest(input.manifest);
   if(!row) {
    db.prepare('INSERT INTO uploads VALUES (?,?,?,?,?,?,?,?,?)').run(input.id,digest,manifest,input.owner,'claimed',null,null,now,now);
    row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
    row.route='new';
   } else row.route=row.commit_sha?'verify':row.owner===input.owner?'new':'uncertain';
  } else if(action==='committed') {
   if(!row || row.owner!==input.owner || !/^[0-9a-f]{40}$/.test(input.sha||'')) throw Error('Invalid commit claim');
   if(row.commit_sha && row.commit_sha!==input.sha) throw Error('COMMIT_CONFLICT');
   db.prepare("UPDATE uploads SET commit_sha=?,state='committed',updated_at=? WHERE id=?").run(input.sha,now,input.id);
   row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
  } else if(action==='confirmed') {
   if(!row || !row.commit_sha || row.commit_sha!==input.receipt?.commitSha || input.receipt?.uploadId!==input.id) throw Error('Invalid confirmation');
   if(isUniversal(JSON.parse(row.manifest))) {
    const target=storedTarget(row).target;
    if(input.receipt.repository!==target.repository||input.receipt.branch!==target.branch||
       own(input.receipt,'repositoryId')&&input.receipt.repositoryId!==target.repositoryId) throw Error('E_RECEIPT_TARGET');
   }
   if(!row.receipt) db.prepare("UPDATE uploads SET state='confirmed',receipt=?,updated_at=? WHERE id=?").run(JSON.stringify(input.receipt),now,input.id);
   row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
  } else if(action!=='read') throw Error('Unknown action');
  const bound=row?storedTarget(row):null;
  db.exec('COMMIT');
  if(!row) return {found:false};
  const cleanup=action==='confirmed'&&row.state==='confirmed'?pruneConfirmedClone(row.id):undefined;
  return {found:true,id:row.id,digest:row.digest,state:row.state,route:row.route,commitSha:row.commit_sha,receipt:row.receipt?JSON.parse(row.receipt):null,target:bound.target,prefix:bound.prefix,...(cleanup?{cleanup}:{})};
 } catch(e) {db.exec('ROLLBACK');throw e;}
}
try {
 let payload;
 try {payload=JSON.parse(process.argv[3]||'{}');} catch {throw Error('E_INPUT_JSON');}
 console.log(JSON.stringify(run(process.argv[2],payload)));
}
catch(e){console.log(JSON.stringify({error:e.message}));}
finally{db.close();}


