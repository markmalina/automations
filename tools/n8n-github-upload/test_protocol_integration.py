"""Cross-component tests with actual Python client, SQLite CLI and n8n Code.

All files and grants are disposable local fixtures. No network/provider call.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import work_upload

ROOT = Path(__file__).resolve().parent
FLOW_PROBE = r'''
const fs=require('node:fs');
const w=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const v=JSON.parse(fs.readFileSync(0,'utf8'));
const names=Object.fromEntries(w.nodes.map(n=>[n.name,n]));
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
const input={json:{body:{manifest:JSON.stringify(v.manifest)},headers:{'x-work-upload-grant':'a'.repeat(64)}},
 binary:Object.fromEntries(v.manifest.files.map(f=>[f.field,{id:'fixture:'+f.field}]))};
async function run(name,json,refs={}) {
 const fn=new AsyncFunction('$input','$','$json','$execution',names[name].parameters.jsCode);
 return fn.call({helpers:{}},{first:()=>input,all:()=>[input]},n=>({first:()=>refs[n][0],all:()=>refs[n]}),json,{id:'fixture-owner'});
}
(async()=>{
 const prepared=await run('Prepare upload');
 if(v.claim) await run('Parse claim',{stdout:JSON.stringify(v.claim)},{'Prepare upload':prepared});
 process.stdout.write(JSON.stringify({target:prepared[0].json.target,prefix:prepared[0].json.prefix,
 fields:prepared[0].json.manifest.files.map(f=>f.field)}));
})().catch(()=>{process.stderr.write('E_PROTOCOL_FIXTURE');process.exitCode=1;});
'''


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, UPLOAD_LEDGER_DIR=str(self.root / 'journal'),
                        UPLOAD_GIT_ROOT=str(self.root / 'git'))
        self.target = {'repositoryId': 1448151721, 'repository': 'markmalina/automations',
                       'branch': 'test/universal', 'prefix': 'папка'}

    def ledger(self, action, value):
        result = subprocess.run(['node', str(ROOT / 'upload-ledger.cjs'), action,
                                 json.dumps(value, ensure_ascii=False)], env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)

    def bundle(self, count=2):
        mappings = []
        for i in range(count):
            source = self.root / f'source-{i}.bin'
            source.write_bytes(bytes((0, 255, i, 13, 10)))
            mappings.append({'source': str(source), 'path': f'sub/файл {i}.bin'})
        return work_upload.prepare(self.target, mappings,
                                   upload_id='11111111-1111-4111-8111-111111111111')

    def flow(self, manifest, claim=None):
        result = subprocess.run(['node', '-e', FLOW_PROBE,
                                 str(ROOT / 'owner-repository-upload.workflow.json')],
                                input=json.dumps({'manifest': manifest, 'claim': claim}, ensure_ascii=False),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_client_n8n_and_sqlite_agree_on_target_fields_digest_and_claim(self):
        bundle = self.bundle()
        self.assertTrue(self.ledger('validate-manifest', {'id': bundle['manifest']['uploadId'],
                                                       'manifest': bundle['manifest']})['valid'])
        prepared = self.flow(bundle['manifest'])
        self.assertEqual(prepared['target'], self.target)
        self.assertEqual(prepared['fields'], ['file0', 'file1'])
        grant = self.ledger('grant', bundle['grantRequest'])
        work_upload.grant_valid(grant, bundle)
        claim = self.ledger('claim-granted-hash', {'id': bundle['manifest']['uploadId'],
                            'manifest': bundle['manifest'], 'owner': 'fixture-owner',
                            'grantHash': hashlib.sha256(grant['token'].encode()).hexdigest()})
        self.assertEqual(claim['route'], 'new')
        self.assertEqual(claim['digest'], bundle['digest'])
        self.assertEqual(claim['target'], self.target)
        self.assertEqual(self.flow(bundle['manifest'], claim)['target'], self.target)

    def test_all_100_generated_field_names_are_admitted_by_server_and_workflow(self):
        bundle = self.bundle(100)
        result = self.ledger('validate-manifest', {'id': bundle['manifest']['uploadId'],
                                                  'manifest': bundle['manifest']})
        self.assertTrue(result['valid'])
        self.assertEqual(self.flow(bundle['manifest'])['fields'][-1], 'file99')

    def test_universal_commit_replay_returns_same_sha_and_stored_target(self):
        bundle = self.bundle(1)
        grant = self.ledger('grant', bundle['grantRequest'])
        data = {'id': bundle['manifest']['uploadId'], 'manifest': bundle['manifest'],
                'owner': 'fixture-owner', 'grantHash': hashlib.sha256(grant['token'].encode()).hexdigest()}
        self.assertEqual(self.ledger('claim-granted-hash', data)['route'], 'new')
        commit = 'b' * 40
        self.assertEqual(self.ledger('committed', {'id': data['id'], 'owner': data['owner'], 'sha': commit})['commitSha'], commit)
        self.assertEqual(self.ledger('claim-granted-hash', {**data, 'owner': 'another-execution'})['route'], 'verify')
        row = self.ledger('read', {'id': data['id']})
        self.assertEqual(row['commitSha'], commit)
        self.assertEqual(row['target'], self.target)
        self.assertEqual(self.flow(bundle['manifest'], {**row, 'route': 'verify'})['target'], self.target)


if __name__ == '__main__':
    unittest.main()
