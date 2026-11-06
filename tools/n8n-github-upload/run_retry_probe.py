"""Repeatable real-HTTP fault probe. Bytes go from local files directly to n8n."""
import argparse,hashlib,json,pathlib,secrets,time,urllib.request,urllib.error,uuid
from probe_work import NoRedirect
p=argparse.ArgumentParser();p.add_argument('label');p.add_argument('--fault',action='store_true');p.add_argument('--replay',action='store_true');p.add_argument('--conflict',action='store_true');p.add_argument('--disconnect',action='store_true');p.add_argument('--label-output');args=p.parse_args()
root=pathlib.Path(__file__).parent;out=root/(args.label+'.json')
fixture=root.parent/'n8n-fixtures'/'update.bin';data=fixture.read_bytes()
if args.replay or args.conflict:manifest=json.loads(out.read_text())['manifest']
else:manifest={'uploadId':str(uuid.uuid4()),'files':[{'field':'f000','path':'Кириллица и пробелы/повтор.bin','bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}]}
if args.fault:manifest['testFault']='afterPush'
if args.conflict:manifest['files'][0]['path']='changed.bin'
boundary='WorkRetry'+secrets.token_hex(12)
body=(('--'+boundary+'\r\nContent-Disposition: form-data; name="manifest"\r\n\r\n').encode()+json.dumps(manifest,ensure_ascii=False).encode()+('\r\n--'+boundary+'\r\nContent-Disposition: form-data; name="f000"; filename="probe.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+data+('\r\n--'+boundary+'--\r\n').encode())
token=json.loads((root/'.pilot-secrets.json').read_text())['PILOT_UPLOAD_TOKEN']
request=urllib.request.Request('https://n8n-upload-pilot.up.railway.app/webhook/work-git-retry-pilot-v1',data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-Work-Upload-Token':token},method='POST')
started=time.perf_counter();receipt=None;status=None;error=None
if args.disconnect:
 import http.client,os,urllib.parse
 # Send the whole HTTP body over TLS, close without reading the response.
 proxy=urllib.parse.urlsplit(urllib.request.getproxies()['https'])
 conn=http.client.HTTPSConnection(proxy.hostname,proxy.port or 80,timeout=30)
 conn.set_tunnel('n8n-upload-pilot.up.railway.app',443)
 conn.request('POST','/webhook/work-git-retry-pilot-v1',body=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-Work-Upload-Token':token,'Connection':'close'})
 conn.close()
 error='connection_closed_before_response'
else:
 try:
  with urllib.request.build_opener(NoRedirect).open(request,timeout=120)as r:status=r.status;receipt=json.load(r)
 except urllib.error.HTTPError as e:status=e.code;error='http_error_body_suppressed'
report={'manifest':manifest,'status':status,'receipt':receipt,'error':error,'seconds':round(time.perf_counter()-started,6)}
suffix='-conflict'if args.conflict else '-replayed'if args.replay else ''
(root/((args.label_output or args.label+suffix)+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='manifest'},ensure_ascii=False))
