"""Produce a stock-node multipart hash probe export; not a GitHub uploader."""
import json
import pathlib
import uuid

root = pathlib.Path(__file__).parent
workflow = json.loads((root / 'probe.workflow.json').read_text())
workflow['id'] = 'workMultipartPilot'
workflow['name'] = 'Work multipart hashes — NOT GitHub upload'
webhook = workflow['nodes'][0]
webhook['parameters'].update({'path': 'work-multipart-hash-probe-v1', 'responseData': 'firstEntryJson'})
webhook['parameters']['options'] = {}
webhook['webhookId'] = str(uuid.uuid4())
webhook['credentials'] = {'httpHeaderAuth': {'id': 'workPilotHeaderAuth', 'name': 'Work pilot header'}}
unpack = """const input = $input.first();
const manifest = JSON.parse(input.json.body.manifest);
if (!Array.isArray(manifest.files) || manifest.files.length > 120) throw new Error('Invalid manifest');
const keys = Object.keys(input.binary || {});
if (keys.length !== manifest.files.length) throw new Error('File count mismatch');
const start = Date.now();
return manifest.files.map(f => {
  if (!input.binary[f.field]) throw new Error('Missing field ' + f.field);
  if (!f.path || f.path.startsWith('/') || f.path.split('/').some(p => !p || p === '.' || p === '..') || f.path.includes('\\\\')) throw new Error('Invalid relative path');
  return {json: {path:f.path, expected:f.sha256, bytes:f.bytes, processingStarted:start}, binary:{data:input.binary[f.field]}};
});"""
summary = """const items = $input.all().map(i => i.json);
const files = items.map(i => ({path:i.path, bytes:i.bytes, sha256:i.sha256, match:i.sha256===i.expected}));
return [{json:{files, fileCount:files.length, totalBytes:files.reduce((n,f)=>n+f.bytes,0), allMatch:files.every(f=>f.match), processingMs:Date.now()-items[0].processingStarted, githubTested:false}}];"""
def node(name, type_, version, params, x):
    return {'id': str(uuid.uuid4()), 'name': name, 'type': type_, 'typeVersion': version, 'parameters': params, 'position': [x, 0]}
workflow['nodes'] = [webhook,
    node('Manifest to file references', 'n8n-nodes-base.code', 2, {'jsCode': unpack}, 240),
    node('Hash received bytes', 'n8n-nodes-base.crypto', 2, {'action': 'hash', 'binaryData': True, 'binaryPropertyName': 'data', 'type': 'SHA256', 'encoding': 'hex', 'dataPropertyName': 'sha256'}, 480),
    node('Return hash receipt', 'n8n-nodes-base.code', 2, {'jsCode': summary}, 720)]
workflow['connections'] = {}
for a, b in zip(workflow['nodes'], workflow['nodes'][1:]):
    workflow['connections'][a['name']] = {'main': [[{'node': b['name'], 'type': 'main', 'index': 0}]]}
(root / 'multipart-probe.workflow.json').write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + '\n')
print('Multipart probe export generated; credentials are references only')
