"""Stock MCP permission -> direct multipart bytes, never prints a bearer token."""
import argparse,hashlib,json,pathlib,secrets,time,urllib.request,urllib.error,uuid
from mcp_probe import rpc,ROOT
from probe_work import NoRedirect
p=argparse.ArgumentParser();p.add_argument('mode',choices=['issue','poll','upload','wrong']);p.add_argument('--label',default='granted-upload');p.add_argument('--endpoint');p.add_argument('--mixed',action='store_true');args=p.parse_args()
private=ROOT/'.upload-grant.json';fixture=ROOT.parent/'n8n-fixtures'/'update.bin';data=fixture.read_bytes()
def result(x):
 if x.get('isError'):raise RuntimeError('MCP tool returned error: '+str(x))
 return x.get('structuredContent') or json.loads(x['content'][0]['text'])
if args.mode=='issue':
 manifest={'uploadId':str(uuid.uuid4()),'files':[{'field':'f000','path':"MCP разрешение/файл с пробелами.bin",'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
 if args.mixed:manifest['files']=json.loads((ROOT.parent/'n8n-fixtures'/'mixed-manifest.json').read_text())['files']
 binding={'id':manifest['uploadId'],'digest':hashlib.sha256(json.dumps(manifest,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'fileCount':len(manifest['files']),'totalBytes':sum(f['bytes']for f in manifest['files'])}
 details=result(rpc('tools/call',{'name':'get_workflow_details','arguments':{'workflowId':'workUploadGrantPilot','detailLevel':'execution'}}))
 assert details['workflow']['canExecute']
 execution=result(rpc('tools/call',{'name':'execute_workflow','arguments':{'workflowId':'workUploadGrantPilot','executionMode':'production','triggerNodeName':'OAuth grant input','inputs':{'webhookData':{'method':'POST','body':binding}}}}))
 private.write_text(json.dumps({'manifest':manifest,'binding':binding,'execution':execution,'mixed':args.mixed}));print(json.dumps({'execution':execution,'manifestDigest':binding['digest']}))
elif args.mode=='poll':
 state=json.loads(private.read_text());execution=result(rpc('tools/call',{'name':'get_workflow_execution','arguments':{'workflowId':'workUploadGrantPilot','executionId':state['execution']['executionId'],'includeData':True,'nodeNames':['Return temporary grant'],'truncateData':1}}))
 def find(v):
  if isinstance(v,dict):
   if 'uploadUrl'in v and 'token'in v:return v
   for x in v.values():
    r=find(x)
    if r:return r
  if isinstance(v,list):
   for x in v:
    r=find(x)
    if r:return r
 grant=find(execution)
 if not grant:print(json.dumps({'execution':execution.get('execution'),'grantReturned':False}));raise SystemExit(1)
 state['grant']=grant;private.write_text(json.dumps(state));print(json.dumps({'execution':execution.get('execution'),'grantReturned':True,'grant':{k:v for k,v in grant.items()if k!='token'}}))
else:
 state=json.loads(private.read_text());grant=state['grant'];manifest=state['manifest'];boundary='WorkGranted'+secrets.token_hex(12)
 parts=[('--'+boundary+'\r\nContent-Disposition: form-data; name="manifest"\r\n\r\n').encode(),json.dumps(manifest,ensure_ascii=False).encode(),b'\r\n']
 for f in manifest['files']:
  source=(ROOT.parent/'n8n-fixtures'/'mixed'/f['path'])if state.get('mixed')else fixture
  content=source.read_bytes()
  assert len(content)==f['bytes']and hashlib.sha256(content).hexdigest()==f['sha256']
  parts.extend([('--'+boundary+'\r\nContent-Disposition: form-data; name="'+f['field']+'"; filename="part.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode(),content,b'\r\n'])
 parts.append(('--'+boundary+'--\r\n').encode());body=b''.join(parts)
 token=grant['token']if args.mode=='upload'else'0'*64
 upload_url=grant['uploadUrl'] if not args.endpoint else 'https://n8n-upload-pilot.up.railway.app/webhook/'+args.endpoint
 import http.client
 send_times={};original_send=http.client.HTTPConnection.send
 def measured_send(connection,payload):
  if payload is body:
   send_times['start']=time.perf_counter();value=original_send(connection,payload);send_times['end']=time.perf_counter();return value
  return original_send(connection,payload)
 http.client.HTTPConnection.send=measured_send
 req=urllib.request.Request(upload_url,data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,grant['headerName']:token},method='POST');start=time.perf_counter()
 try:
  with urllib.request.build_opener(NoRedirect).open(req,timeout=120)as r:status=r.status;receipt=json.load(r)
 except urllib.error.HTTPError as e:status=e.code;receipt=None
 http.client.HTTPConnection.send=original_send
 report={'clientBodySendSeconds':round(send_times['end']-send_times['start'],6)if 'end'in send_times else None,'status':status,'receipt':receipt,'seconds':round(time.perf_counter()-start,6),'manifest':manifest,'mcpExecutionId':state['execution']['executionId']}
 (ROOT/(args.label+'-'+args.mode+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({**{k:v for k,v in report.items()if k not in ('manifest','receipt')},'receipt':{k:v for k,v in (receipt or {}).items()if k!='files'}},ensure_ascii=False))
