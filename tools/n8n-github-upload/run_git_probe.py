"""Send local files directly to the bounded Git probe; no model-visible bytes."""
import argparse
import hashlib
import http.client
import json
import mimetypes
import pathlib
import secrets
import time
import urllib.request
import urllib.error
import uuid
from probe_work import NoRedirect

parser=argparse.ArgumentParser()
parser.add_argument('--single',type=pathlib.Path)
parser.add_argument('--mixed-root',type=pathlib.Path)
parser.add_argument('--label',required=True)
parser.add_argument('--target-path')
parser.add_argument('--endpoint',default='work-git-pilot-v1')
args=parser.parse_args()
root=pathlib.Path(__file__).parent
if args.single:
    data=args.single.read_bytes();files=[{'field':'f000','path':args.single.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}];local=[args.single]
elif args.mixed_root:
    files=json.loads((args.mixed_root.parent/'mixed-manifest.json').read_text())['files'];local=[args.mixed_root/f['path'] for f in files]
else:
    raise SystemExit('Choose --single or --mixed-root')
if args.target_path:
    if len(files)!=1:raise SystemExit('One file required for target override')
    files[0]['path']=args.target_path
manifest={'uploadId':str(uuid.uuid4()),'files':files}
boundary='WorkGitProbe'+secrets.token_hex(16)
parts=[]
def part(headers,payload):parts.extend([('--'+boundary+'\r\n'+headers+'\r\n\r\n').encode(),payload,b'\r\n'])
part('Content-Disposition: form-data; name="manifest"',json.dumps(manifest,ensure_ascii=False).encode())
for entry,path in zip(files,local):
    data=path.read_bytes()
    if len(data)!=entry['bytes'] or hashlib.sha256(data).hexdigest()!=entry['sha256']:raise SystemExit('Fixture changed')
    part('Content-Disposition: form-data; name="'+entry['field']+'"; filename="'+path.name+'"\r\nContent-Type: '+(mimetypes.guess_type(path.name)[0] or 'application/octet-stream'),data)
parts.append(('--'+boundary+'--\r\n').encode())
token=json.loads((root/'.pilot-secrets.json').read_text())['PILOT_UPLOAD_TOKEN']
body=b''.join(parts)
send_times={}
original_send=http.client.HTTPConnection.send
def measured_send(c,d):
    if d is body:
        send_times['start']=time.perf_counter();v=original_send(c,d);send_times['end']=time.perf_counter();return v
    return original_send(c,d)
http.client.HTTPConnection.send=measured_send
started=time.perf_counter()
request=urllib.request.Request('https://n8n-upload-pilot.up.railway.app/webhook/'+args.endpoint,data=body,headers={'Content-Type':'multipart/form-data; boundary='+boundary,'X-Work-Upload-Token':token},method='POST')
try:
    with urllib.request.build_opener(NoRedirect).open(request,timeout=240) as response:receipt=json.load(response);status=response.status
except urllib.error.HTTPError as exc:
    print(json.dumps({'status':exc.code,'body_suppressed':True,'uploadId':manifest['uploadId'],'total_seconds':time.perf_counter()-started}));raise SystemExit(1)
report={'http_status':status,'total_seconds':round(time.perf_counter()-started,6),'receipt':receipt,'manifest':manifest,'sourceFileBytes':sum(f['bytes'] for f in files),'download_hash_verification':False}
http.client.HTTPConnection.send=original_send
if 'end' in send_times:report['client_body_send_seconds']=round(send_times['end']-send_times['start'],6)
(root/(args.label+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({**{k:v for k,v in report.items()if k not in ('manifest','receipt')},'receipt':{k:v for k,v in receipt.items()if k!='files'}},ensure_ascii=False))
if not receipt.get('success'):raise SystemExit(1)
