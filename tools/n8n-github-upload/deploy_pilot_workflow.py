"""Administer a probe workflow through stock n8n REST; no secret values printed."""
import json
import pathlib
import sys
import urllib.request
import urllib.error

root=pathlib.Path(__file__).parent
cookies=json.loads((root/'.pilot-session.json').read_text())
headers={'Content-Type':'application/json','Cookie':'; '.join(k+'='+v for k,v in cookies.items())}
base='https://n8n-upload-pilot.up.railway.app'
def call(path,method='GET',data=None):
    req=urllib.request.Request(base+path,method=method,headers=headers,data=None if data is None else json.dumps(data).encode())
    with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)['data']
workflow=json.loads(pathlib.Path(sys.argv[1]).read_text())
workflow.pop('pinData',None)
workflow.pop('active',None)
try:
    current=call('/rest/workflows/'+workflow['id'])
except urllib.error.HTTPError as e:
    if e.code!=404 or b'Application not found' in e.read():raise
    saved=call('/rest/workflows','POST',workflow)
else:
    workflow['versionId']=current['versionId']
    saved=call('/rest/workflows/'+workflow['id'],'PATCH',workflow)
active=call('/rest/workflows/'+saved['id']+'/activate','POST',{'versionId':saved['versionId']})
print(json.dumps({k:active.get(k)for k in ['id','active','activeVersionId']}))
