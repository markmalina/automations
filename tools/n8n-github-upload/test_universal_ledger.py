"""Exercise target binding and additive migration using actual disposable SQLite databases."""
import concurrent.futures
import copy
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import tempfile
import time
import unittest
import uuid

HERE = pathlib.Path(__file__).parent
FAILED_ID = '9d94bcf3-9a28-4014-93d5-ce8e5d259c7d'
TARGET = {'repositoryId': 1448151721, 'repository': 'markmalina/automations', 'branch': 'main', 'prefix': 'Отчёты и файлы'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def manifest(identifier=None, target=None):
    return {'schemaVersion': 'work-upload/v2', 'uploadId': identifier or str(uuid.uuid4()),
            'target': copy.deepcopy(TARGET if target is None else target),
            'files': [{'field': 'file0', 'path': "Подпапка/бинарный ' файл.bin", 'bytes': 3, 'sha256': 'a' * 64}]}


class UniversalLedger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temp.name)
        self.env = {**os.environ, 'UPLOAD_LEDGER_DIR': str(self.root), 'UPLOAD_GIT_ROOT': str(self.root / 'git')}

    def tearDown(self):
        self.temp.cleanup()

    def call(self, action, payload):
        result = subprocess.run(['node', str(HERE / 'upload-ledger.cjs'), action, canonical(payload)],
                                env=self.env, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def grant(self, value, target=None):
        return self.call('grant', {'id': value['uploadId'], 'digest': digest(value), 'fileCount': len(value['files']),
                                  'totalBytes': sum(f['bytes'] for f in value['files']),
                                  'target': copy.deepcopy(value['target'] if target is None else target)})

    def claim(self, value, grant, owner='execution-one'):
        if value.get('schemaVersion') == 'work-upload/v2':
            return self.call('claim-granted-hash', {'id': value['uploadId'], 'manifest': value,
                             'grantHash': hashlib.sha256(grant['token'].encode()).hexdigest(), 'owner': owner})
        return self.call('claim-granted', {'id': value['uploadId'], 'manifest': value, 'grant': grant['token'], 'owner': owner})

    def validate(self, value):
        return self.call('validate-manifest', {'id': value['uploadId'], 'manifest': value})

    def test_migration_preserves_exact_old_rows_failed_id_and_old_grant(self):
        value = {'uploadId': FAILED_ID, 'files': [{'field': 'f000', 'path': 'old.bin', 'bytes': 3, 'sha256': 'a' * 64}]}
        old_token = 'e' * 64
        upload_row = (FAILED_ID, digest(value), canonical(value), 'old-failed-owner', 'claimed', None, None, 1, 2)
        grant_row = (hashlib.sha256(old_token.encode()).hexdigest(), FAILED_ID, digest(value), 1, 3, int(time.time() * 1000) + 600000)
        with sqlite3.connect(self.root / 'uploads.sqlite') as db:
            db.executescript('CREATE TABLE uploads(id TEXT PRIMARY KEY,digest TEXT NOT NULL,manifest TEXT NOT NULL,owner TEXT NOT NULL,state TEXT NOT NULL,commit_sha TEXT,receipt TEXT,created_at INTEGER NOT NULL,updated_at INTEGER NOT NULL); CREATE TABLE grants(token_hash TEXT PRIMARY KEY,upload_id TEXT NOT NULL,digest TEXT NOT NULL,file_count INTEGER NOT NULL,total_bytes INTEGER NOT NULL,expires_at INTEGER NOT NULL);')
            db.execute('INSERT INTO uploads VALUES (?,?,?,?,?,?,?,?,?)', upload_row)
            db.execute('INSERT INTO grants VALUES (?,?,?,?,?,?)', grant_row)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.call('read', {'id': FAILED_ID}), range(8)))
        self.assertTrue(all(r['found'] and r['state'] == 'claimed' for r in results))
        with sqlite3.connect(self.root / 'uploads.sqlite') as db:
            self.assertEqual(db.execute('SELECT * FROM uploads').fetchone(), upload_row)
            stored = db.execute('SELECT * FROM grants').fetchone()
            self.assertEqual(stored[:6], grant_row)
            self.assertIsNone(stored[6])
            self.assertEqual([r[1] for r in db.execute('PRAGMA table_info(grants)')].count('target_json'), 1)
        accepted = self.claim(value, {'token': old_token}, 'new-execution')
        self.assertEqual(accepted['route'], 'uncertain')
        self.assertEqual(accepted['target']['repository'], 'markmalina/freelance')
        with sqlite3.connect(self.root / 'uploads.sqlite') as db:
            self.assertEqual(db.execute('SELECT * FROM uploads').fetchone(), upload_row)

    def test_universal_grant_claim_commit_confirmation_and_replay_bind_same_target(self):
        value = manifest()
        grant = self.grant(value)
        self.assertEqual(grant['target'], TARGET)
        self.assertTrue(grant['uploadUrl'].endswith('/webhook/work-owner-repository-upload-v1'))
        first = self.claim(value, grant)
        self.assertEqual(first['route'], 'new')
        self.assertEqual(first['target'], TARGET)
        self.assertEqual(first['prefix'], TARGET['prefix'] + '/')
        self.assertEqual(self.claim(value, grant, 'another-execution')['route'], 'uncertain')
        committed = self.call('committed', {'id': value['uploadId'], 'owner': 'execution-one', 'sha': 'b' * 40})
        self.assertEqual(committed['target'], TARGET)
        receipt = {'uploadId': value['uploadId'], 'commitSha': 'b' * 40, 'success': True,
                   'repository': TARGET['repository'], 'branch': TARGET['branch'], 'repositoryId': TARGET['repositoryId']}
        self.assertEqual(self.call('confirmed', {'id': value['uploadId'], 'receipt': receipt})['receipt'], receipt)
        replay = self.claim(value, self.grant(value), 'fresh-work')
        self.assertEqual(replay['route'], 'verify')
        self.assertEqual(replay['commitSha'], 'b' * 40)
        self.assertEqual(replay['target'], TARGET)
        self.assertEqual(replay['receipt'], receipt)
        self.assertEqual(self.call('read', {'id': value['uploadId']})['target'], TARGET)

    def test_digest_alone_cannot_substitute_a_different_target(self):
        value = manifest(target={**TARGET, 'repository': 'markmalina/second', 'repositoryId': 100})
        grant = self.grant(value, target=TARGET)  # digest/count match, requested grant target does not.
        self.assertEqual(self.claim(value, grant)['error'], 'GRANT_DENIED')
        self.assertFalse(self.call('read', {'id': value['uploadId']})['found'])

    def test_legacy_null_target_grant_cannot_claim_universal_manifest(self):
        value = manifest()
        grant = self.call('grant', {'id': value['uploadId'], 'digest': digest(value), 'fileCount': 1, 'totalBytes': 3})
        self.assertEqual(self.claim(value, grant)['error'], 'GRANT_DENIED')

    def test_universal_grant_cannot_be_used_for_a_legacy_manifest(self):
        value = {'uploadId': str(uuid.uuid4()), 'files': [{'field': 'f000', 'path': 'old.bin', 'bytes': 3, 'sha256': 'a' * 64}]}
        grant = self.call('grant', {'id': value['uploadId'], 'digest': digest(value), 'fileCount': 1, 'totalBytes': 3, 'target': TARGET})
        self.assertEqual(self.claim(value, grant)['error'], 'GRANT_DENIED')

    def test_expired_grant_does_not_claim_or_reset_state(self):
        value = manifest()
        grant = self.grant(value)
        with sqlite3.connect(self.root / 'uploads.sqlite') as db:
            db.execute('UPDATE grants SET expires_at=0')
        self.assertEqual(self.claim(value, grant)['error'], 'GRANT_DENIED')
        self.assertFalse(self.call('read', {'id': value['uploadId']})['found'])

    def test_internal_hashed_claim_requires_v2_and_hash_is_not_external_bearer(self):
        value = manifest()
        grant = self.grant(value)
        hashed = hashlib.sha256(grant['token'].encode()).hexdigest()
        payload = {'id': value['uploadId'], 'manifest': value, 'owner': 'execution-one'}
        self.assertEqual(self.call('claim-granted-hash', {**payload, 'grantHash': '0' * 64})['error'], 'GRANT_DENIED')
        self.assertEqual(self.call('claim-granted', {**payload, 'grant': hashed})['error'], 'GRANT_DENIED')
        self.assertFalse(self.call('read', {'id': value['uploadId']})['found'])
        self.assertEqual(self.call('claim-granted-hash', {**payload, 'grantHash': hashed})['route'], 'new')
        legacy = {'uploadId': str(uuid.uuid4()), 'files': [{'field': 'f000', 'path': 'old.bin', 'bytes': 3, 'sha256': 'a' * 64}]}
        old_grant = self.call('grant', {'id': legacy['uploadId'], 'digest': digest(legacy), 'fileCount': 1, 'totalBytes': 3})
        old_payload = {'id': legacy['uploadId'], 'manifest': legacy, 'owner': 'legacy-execution'}
        self.assertEqual(self.call('claim-granted-hash', {**old_payload, 'grantHash': hashlib.sha256(old_grant['token'].encode()).hexdigest()})['error'], 'GRANT_DENIED')
        self.assertEqual(self.call('claim-granted', {**old_payload, 'grant': old_grant['token']})['route'], 'new')

    def test_legacy_raw_action_cannot_consume_any_universal_grant(self):
        targets = [TARGET, {'repositoryId': 1378687935, 'repository': 'markmalina/freelance',
                           'branch': 'test/n8n-upload-20261106', 'prefix': 'different-bound-prefix'}]
        for target in targets:
            with self.subTest(target=target):
                value = manifest(target=target)
                grant = self.grant(value)
                payload = {'id': value['uploadId'], 'manifest': value, 'owner': 'old-endpoint-execution'}
                self.assertEqual(self.call('claim-granted', {**payload, 'grant': grant['token']})['error'], 'GRANT_DENIED')
                self.assertFalse(self.call('read', {'id': value['uploadId']})['found'])
                accepted = self.call('claim-granted-hash', {**payload, 'grantHash': hashlib.sha256(grant['token'].encode()).hexdigest()})
                self.assertEqual(accepted['route'], 'new')
                self.assertEqual(accepted['target'], target)

    def test_initialization_and_migration_errors_are_safe_json_with_zero_exit(self):
        for kind in ['directory-blocked', 'database-blocked', 'migration-blocked']:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                ledger_directory = root / 'control'
                if kind == 'directory-blocked':
                    ledger_directory.write_text('existing file')
                else:
                    ledger_directory.mkdir()
                    if kind == 'database-blocked':
                        (ledger_directory / 'uploads.sqlite').mkdir()
                    else:
                        with sqlite3.connect(ledger_directory / 'uploads.sqlite') as db:
                            db.execute("CREATE VIEW grants AS SELECT 'old' AS token_hash")
                env = {**self.env, 'UPLOAD_LEDGER_DIR': str(ledger_directory)}
                payload = {'id': str(uuid.uuid4()), 'grant': 'raw-transient-grant-canary-never-print'}
                result = subprocess.run(['node', str(HERE / 'upload-ledger.cjs'), 'read', canonical(payload)],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(json.loads(result.stdout), {'error': 'E_LEDGER_UNAVAILABLE'})
                self.assertEqual(result.stderr, '')
                self.assertNotIn(payload['grant'], result.stdout + result.stderr)

    def test_same_id_rejects_different_target_and_confirmation_cannot_relabel(self):
        value = manifest()
        self.claim(value, self.grant(value))
        changed = copy.deepcopy(value)
        changed['target']['branch'] = 'different'
        self.assertIn('ID_CONFLICT', self.call('claim', {'id': changed['uploadId'], 'owner': 'execution-one', 'manifest': changed})['error'])
        self.assertIn('ID_CONFLICT', self.grant(changed)['error'])
        self.assertIn('ID_CONFLICT', self.grant(value, {**TARGET, 'repository': 'markmalina/other'})['error'])
        self.call('committed', {'id': value['uploadId'], 'owner': 'execution-one', 'sha': 'b' * 40})
        receipt = {'uploadId': value['uploadId'], 'commitSha': 'b' * 40, 'repository': 'markmalina/other', 'branch': 'main'}
        self.assertEqual(self.call('confirmed', {'id': value['uploadId'], 'receipt': receipt})['error'], 'E_RECEIPT_TARGET')
        self.assertEqual(self.call('read', {'id': value['uploadId']})['state'], 'committed')

    def test_target_schema_owner_id_branch_and_prefix_fail_closed(self):
        cases = [('repository', 'another/repo'), ('repository', 'markmalina/../repo'),
                 ('repositoryId', 0), ('repositoryId', 9007199254740992), ('repositoryId', '12'),
                 ('branch', '../main'), ('branch', 'a//b'), ('branch', 'main.lock'), ('branch', '.main'),
                 ('branch', 'a/.hidden'), ('branch', 'main/'), ('branch', 'main.'), ('branch', 'HEAD'),
                 ('branch', 'a@{b'), ('branch', 'main\n'), ('prefix', '../outside'), ('prefix', '/absolute'),
                 ('prefix', '.git/config'), ('prefix', 'x\\y'), ('prefix', 'x, y')]
        for key, invalid in cases:
            with self.subTest(key=key, invalid=invalid):
                value = manifest(target={**TARGET, key: invalid})
                self.assertIn('error', self.validate(value))
        value = manifest(target={**TARGET, 'unexpected': 'ignored?'})
        self.assertEqual(self.validate(value)['error'], 'E_TARGET')

    def test_file_paths_fields_collisions_and_workflows_are_rejected(self):
        for invalid in ['/absolute', '../out', 'a/../b', './a', 'a//b', 'a/.git/config', 'a/.GIT/x', 'a\\b', 'a,b', 'a\nb', 'a\x00b', 'e\u0301.txt']:
            with self.subTest(path=repr(invalid)):
                value = manifest()
                value['files'][0]['path'] = invalid
                self.assertEqual(self.validate(value)['error'], 'E_PATH')
        for other in ["Подпапка/бинарный ' файл.bin", "подпапка/БИНАРНЫЙ ' ФАЙЛ.bin", 'Подпапка']:
            value = manifest()
            value['files'].append({**value['files'][0], 'field': 'file1', 'path': other})
            self.assertEqual(self.validate(value)['error'], 'E_PATH_COLLISION')
        for target, path in [({**TARGET, 'prefix': ''}, '.github/workflows/a.yml'),
                             ({**TARGET, 'prefix': '.github'}, 'workflows/a.yml'),
                             ({**TARGET, 'prefix': '.github/workflows'}, 'a.yml')]:
            value = manifest(target=target)
            value['files'][0]['path'] = path
            self.assertEqual(self.validate(value)['error'], 'E_WORKFLOWS_PERMISSION')
        value = manifest()
        value['files'][0]['unexpected'] = True
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')
        value = manifest()
        value['files'].append({**value['files'][0], 'path': 'different.bin'})
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')
        for invalid_field in ['f000', 'file00', 'file01', 'file-1', 'file100', 'file099', 'file0\n']:
            with self.subTest(field=repr(invalid_field)):
                value = manifest()
                value['files'][0]['field'] = invalid_field
                self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')
        value = manifest()
        value['files'][0]['field'] = 'file99'
        self.assertTrue(self.validate(value)['valid'])
        value = manifest()
        value['files'][0]['path'] = '\ud800.bin'
        raw = subprocess.run(['node', str(HERE / 'upload-ledger.cjs'), 'validate-manifest',
                              json.dumps({'id': value['uploadId'], 'manifest': value}, ensure_ascii=True)],
                             env=self.env, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(raw.stdout)['error'], 'E_PATH')

    def test_limits_exact_manifest_keys_and_empty_prefix(self):
        value = manifest(target={**TARGET, 'prefix': ''})
        value['files'] = [{'field': 'file%d' % n, 'path': 'file%03d.bin' % n, 'bytes': 320000, 'sha256': 'a' * 64} for n in range(100)]
        result = self.validate(value)
        self.assertTrue(result['valid'])
        self.assertEqual(result['totalBytes'], 32000000)
        self.assertEqual(result['prefix'], '')
        value['files'][0]['bytes'] += 1
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST_LIMIT')
        value['files'].append({**value['files'][0], 'field': 'file100', 'path': 'extra.bin'})
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')
        value = manifest(target={**TARGET, 'prefix': ''})
        value['files'] = [{'field': 'file%d' % n, 'path': ('a' * 200) + '/' + ('b' * 100) + str(n), 'bytes': 1, 'sha256': 'a' * 64} for n in range(100)]
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST_TOO_LARGE')
        value = manifest()
        value['testFault'] = 'not a production field'
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')
        value = manifest()
        value['schemaVersion'] = 'unknown'
        self.assertEqual(self.validate(value)['error'], 'E_MANIFEST')


if __name__ == '__main__':
    unittest.main()
