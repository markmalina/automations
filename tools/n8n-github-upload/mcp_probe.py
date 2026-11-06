"""Diagnostic stock MCP client. Keeps authentication and grant values out of stdout."""
import json,pathlib,urllib.request,urllib.error
ROOT=pathlib.Path(__file__).parent
META={'io.modelcontextprotocol/protocolVersion':'2026-07-28','io.modelcontextprotocol/clientInfo':{'name':'work-upload-acceptance','version':'1'},'io.modelcontextprotocol/clientCapabilities':{}}
def rpc(method,params=None):
 token=json.loads((ROOT/'.mcp-api-key.json').read_text())['data']['apiKey']
 params={**(params or {}),'_meta':META}
 headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'application/json, text/event-stream','MCP-Protocol-Version':'2026-07-28','Mcp-Method':method}
 if method=='tools/call':headers['Mcp-Name']=params['name']
 q={'jsonrpc':'2.0','id':1,'method':method,'params':params}
 req=urllib.request.Request('https://n8n-upload-pilot.up.railway.app/mcp-server/http',headers=headers,data=json.dumps(q).encode())
 try:
  with urllib.request.urlopen(req,timeout=40)as r:text=r.read().decode()
 except urllib.error.HTTPError as e:raise RuntimeError('MCP HTTP '+str(e.code)+': '+e.read().decode()[:500])
 if text.startswith('event:')or text.startswith('data:'):text=next(line[5:].strip()for line in text.splitlines()if line.startswith('data:'))
 value=json.loads(text)
 if 'error'in value:raise RuntimeError(json.dumps(value['error']))
 return value['result']
if __name__=='__main__':
 result=rpc('tools/list');(ROOT/'mcp-tools-list-response.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 selected=[t for t in result['tools']if t['name']in ['execute_workflow','get_workflow_details','get_workflow_execution']]
 print(json.dumps({'count':len(result['tools']),'selected':selected},ensure_ascii=False))
