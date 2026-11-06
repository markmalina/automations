"""Meaningful metadata-journal checks: concurrent claim, conflicts, grants and expiry."""
import concurrent.futures,hashlib,json,os,pathlib,sqlite3,subprocess,tempfile,uuid
ROOT=pathlib.Path(__file__).parent
with tempfile.TemporaryDirectory()as directory:
 env={**os.environ,'UPLOAD_LEDGER_DIR':directory,'UPLOAD_GIT_ROOT':str(pathlib.Path(directory)/'git')};upload_id=str(uuid.uuid4())
 manifest={'uploadId':upload_id,'files':[{'field':'f000','path':"Кириллица и ' апостроф.bin",'bytes':7,'sha256':'a'*64}]}
 def call(action,payload):
  run=subprocess.run(['node',str(ROOT/'upload-ledger.cjs'),action,json.dumps(payload,ensure_ascii=False)],env=env,capture_output=True,text=True,check=True)
  return json.loads(run.stdout)
 def claim(owner):return call('claim',{'id':upload_id,'manifest':manifest,'owner':str(owner)})
 with concurrent.futures.ThreadPoolExecutor(max_workers=8)as executor:results=list(executor.map(claim,range(16)))
 assert sum(r.get('route')=='new'for r in results)==1,results
 owner=str(next(i for i,r in enumerate(results)if r['route']=='new'))
 assert 'ID_CONFLICT'in call('claim',{'id':upload_id,'owner':owner,'manifest':{**manifest,'files':[]}})['error']
 assert call('committed',{'id':upload_id,'owner':owner,'sha':'b'*40})['state']=='committed'
 assert claim('retry')['route']=='verify'
 receipt={'commitSha':'b'*40,'uploadId':upload_id,'success':True}
 call('confirmed',{'id':upload_id,'receipt':receipt});assert claim('new-process')['receipt']==receipt
 digest=hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 grant=call('grant',{'id':upload_id,'digest':digest,'fileCount':1,'totalBytes':7})
 payload={'id':upload_id,'owner':'grant-retry','manifest':manifest,'grant':grant['token']}
 assert call('claim-granted',payload)['route']=='verify'
 assert call('claim-granted',{**payload,'grant':'0'*64})['error']=='GRANT_DENIED'
 assert call('claim-granted',{**payload,'manifest':{**manifest,'files':[]}})['error']=='GRANT_DENIED'
 with sqlite3.connect(pathlib.Path(directory)/'uploads.sqlite')as db:db.execute('UPDATE grants SET expires_at=0')
 assert call('claim-granted',payload)['error']=='GRANT_DENIED'
 print(json.dumps({'concurrentClaims':16,'newClaims':1,'differentManifestRejected':True,'committedRetryVerifiesRemote':True,'receiptSurvivesNewProcess':True,'validGrantAccepted':True,'wrongTokenRejected':True,'changedManifestRejected':True,'expiredGrantRejected':True}))

