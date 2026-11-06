// Small transactional metadata journal; HTTP, binary I/O and Git remain stock n8n nodes.
// No credentials or file contents are accepted here. Single service/volume only.
const { DatabaseSync } = require('node:sqlite');
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const directory = process.env.UPLOAD_LEDGER_DIR || '/data/work/control';
fs.mkdirSync(directory, {recursive:true,mode:0o700});
const db = new DatabaseSync(path.join(directory,'uploads.sqlite'));
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
function canonical(v) {
 if(Array.isArray(v)) return '['+v.map(canonical).join(',')+']';
 if(v!==null && typeof v==='object') return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';
 return JSON.stringify(v);
}
function run(action,input) {
 const now=Date.now();
 if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(input.id||'')) throw Error('Invalid upload ID');
 db.exec('BEGIN IMMEDIATE');
 try {
  let row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
  if(action==='grant') {
   if(!/^[0-9a-f]{64}$/.test(input.digest||'') || !Number.isInteger(input.fileCount) || input.fileCount<1 || input.fileCount>100 || !Number.isSafeInteger(input.totalBytes) || input.totalBytes<0 || input.totalBytes>32000000) throw Error('Invalid grant binding');
   if(row && row.digest!==input.digest) throw Error('ID_CONFLICT');
   const token=crypto.randomBytes(32).toString('hex');
   const hash=crypto.createHash('sha256').update(token).digest('hex');
   const expiresAt=now+600000;
   db.prepare('DELETE FROM grants WHERE expires_at<?').run(now);
   db.prepare('INSERT INTO grants VALUES (?,?,?,?,?,?)').run(hash,input.id,input.digest,input.fileCount,input.totalBytes,expiresAt);
   db.exec('COMMIT');
   return {uploadId:input.id,uploadUrl:'https://n8n-upload-pilot.up.railway.app/webhook/work-granted-upload-pilot-v1',headerName:'X-Work-Upload-Grant',token,expiresAt:new Date(expiresAt).toISOString(),repository:'markmalina/freelance',branch:'test/n8n-upload-20261106',manifestDigest:input.digest,productionReady:false};
  }
  if(action==='claim-granted') {
   if(!/^[0-9a-f]{64}$/.test(input.grant||'')) throw Error('GRANT_DENIED');
   const hash=crypto.createHash('sha256').update(input.grant).digest('hex');
   const grant=db.prepare('SELECT * FROM grants WHERE token_hash=?').get(hash);
   const digest=crypto.createHash('sha256').update(canonical(input.manifest)).digest('hex');
   if(!grant || grant.upload_id!==input.id || grant.digest!==digest || grant.expires_at<now || grant.file_count!==input.manifest?.files?.length || grant.total_bytes!==input.manifest.files.reduce((n,f)=>n+f.bytes,0)) throw Error('GRANT_DENIED');
   action='claim';
  }
  if(action==='claim') {
   const manifest=canonical(input.manifest);
   const digest=crypto.createHash('sha256').update(manifest).digest('hex');
   if(input.manifest?.uploadId!==input.id || typeof input.owner!=='string' || !input.owner) throw Error('Invalid claim');
   if(row && row.digest!==digest) throw Error('ID_CONFLICT: upload ID already binds different metadata');
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
   if(!row.receipt) db.prepare("UPDATE uploads SET state='confirmed',receipt=?,updated_at=? WHERE id=?").run(JSON.stringify(input.receipt),now,input.id);
   row=db.prepare('SELECT * FROM uploads WHERE id=?').get(input.id);
  } else if(action!=='read') throw Error('Unknown action');
  db.exec('COMMIT');
  if(!row) return {found:false};
  return {found:true,id:row.id,digest:row.digest,state:row.state,route:row.route,commitSha:row.commit_sha,receipt:row.receipt?JSON.parse(row.receipt):null};
 } catch(e) {db.exec('ROLLBACK');throw e;}
}
try {console.log(JSON.stringify(run(process.argv[2],JSON.parse(process.argv[3]||'{}'))));}
catch(e){console.log(JSON.stringify({error:e.message}));}
finally{db.close();}
