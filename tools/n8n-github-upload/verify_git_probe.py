"""Ask stock n8n HTTP Request/Crypto nodes to download and hash a pinned commit."""
import json
import pathlib
import sys
import time
import urllib.request
from probe_work import NoRedirect

root=pathlib.Path(__file__).parent
upload=json.loads(pathlib.Path(sys.argv[1]).read_text())['receipt']
token=json.loads((root/'.pilot-secrets.json').read_text())['PILOT_UPLOAD_TOKEN']
started=time.perf_counter()
request=urllib.request.Request('https://n8n-upload-pilot.up.railway.app/webhook/work-git-verify-pilot-v1',method='POST',data=json.dumps({'commitSha':upload['commitSha'],'files':upload['files']}).encode(),headers={'Content-Type':'application/json','X-Work-Upload-Token':token})
with urllib.request.build_opener(NoRedirect).open(request,timeout=240) as response:result=json.load(response)
result['total_seconds']=round(time.perf_counter()-started,6)
output=root/(pathlib.Path(sys.argv[1]).stem+'-verified.json')
output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in result.items()if k!='files'},ensure_ascii=False))
if not result.get('allMatch') or result.get('fileCount')!=upload['fileCount']:raise SystemExit(1)
