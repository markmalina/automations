"""Embed the reviewed workflow exports into the existing bootstrap, idempotently.

No network, credentials, provider writes or live installation occur here.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
START = '// UNIVERSAL_WORKFLOWS_START'
END = '// UNIVERSAL_WORKFLOWS_END'
CALL = "  if (persistent) {\n    if (!githubPilotCredentials) throw Error('GITHUB_APP_UNAVAILABLE');\n    await installUniversalWorkflows();\n  }\n"


def build():
    path = ROOT / 'pilot-bootstrap.cjs'
    source = path.read_text()
    if START in source:
        if source.count(START) != 1 or source.count(END) != 1:
            raise ValueError('Ambiguous generated block')
        left, rest = source.split(START)
        _, right = rest.split(END)
        source = left + right.lstrip('\n')
    source = source.replace(CALL, '')
    workflows = [json.loads((ROOT / name).read_text()) for name in
                 ('upload-grant.workflow.json', 'owner-repository-upload.workflow.json')]
    if [w['id'] for w in workflows] != ['workUploadGrantPilot', 'workOwnerRepositoryUploadV1']:
        raise ValueError('Unexpected workflow IDs')
    grant, binary = workflows
    if grant['settings'].get('availableInMCP') is not True:
        raise ValueError('Existing OAuth grant must remain available')
    if binary['settings'].get('availableInMCP') is not False:
        raise ValueError('Binary endpoint is not an MCP payload interface')
    if any(binary['settings'].get(key) != 'none' for key in
           ('saveDataSuccessExecution', 'saveDataErrorExecution')):
        raise ValueError('Binary execution data must not persist')
    payload = json.dumps(workflows, ensure_ascii=False, separators=(',', ':'))
    block = START + '\nconst UNIVERSAL_WORKFLOWS = ' + payload + ';\n' + r'''
async function installUniversalWorkflows() {
  // Reuses existing workflow IDs/credential references and stock n8n CLI.
  // A failed import/publish aborts startup; the public child is not started.
  for (const workflow of UNIVERSAL_WORKFLOWS) {
    if (!['workUploadGrantPilot', 'workOwnerRepositoryUploadV1'].includes(workflow.id)) throw Error('WORKFLOW_ID');
    const filename = '/data/.n8n/owner-upload-import-' + workflow.id + '.json';
    try {
      fs.writeFileSync(filename, JSON.stringify(workflow), { mode: 0o600 });
      await cli(['import:workflow', '--input=' + filename]);
      await cli(['publish:workflow', '--id=' + workflow.id]);
    } finally { if (fs.existsSync(filename)) fs.unlinkSync(filename); }
  }
}
''' + END + '\n'
    anchor = 'function childExitCode('
    if source.count(anchor) != 1:
        raise ValueError('Bootstrap function anchor changed')
    source = source.replace(anchor, block + anchor)
    anchor = "  console.log('UPLOAD_OPS_OBSERVATION_V1'"
    if source.count(anchor) != 1:
        raise ValueError('Bootstrap startup anchor changed')
    source = source.replace(anchor, CALL + anchor)
    if len(source.encode()) > 100_000:
        raise ValueError('Bootstrap exceeds existing reviewed source limit')
    path.write_text(source)


if __name__ == '__main__':
    build()
