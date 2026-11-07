"""Task17 synthetic native integration. No real GitHub client or credentials.

Run with --root pointing at an isolated installation containing node_modules,
source/{work_upload.py,upload-ledger.cjs,owner-repository-upload.workflow.json}.
Only loopback HTTP is used by the test. Runtime data is private and temporary.
"""
import argparse
import base64
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time

REPO = 'markmalina/native-fixture-not-a-repository'
RID = 91717001
BRANCH = 'test/native-binary'
TOKEN = 'synthetic-installation-token-not-a-real-credential'


def git_sha(kind, raw):
    return hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


class Fixture:
    def __init__(self):
        self.blobs, self.tree = {}, []
        self.head, self.tree_sha = 'a' * 40, 'b' * 40
        self.commit_writes = self.ref_writes = self.errors = 0

    def handler(self):
        fixture = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def run_request(self):
                try:
                    from urllib.parse import unquote
                    path = unquote(self.path)
                    body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
                    if path == '/app/installations/179245428/access_tokens':
                        assert self.command == 'POST'
                        assert body == dict(repository_ids=[RID], permissions=dict(contents='write'))
                        jwt = self.headers.get('Authorization', '').removeprefix('Bearer ')
                        assert jwt.count('.') == 2
                        encoded = jwt.split('.')[1]
                        claims = json.loads(base64.urlsafe_b64decode(encoded + '=' * (-len(encoded) % 4)))
                        assert claims['iss'] == '5641721' and claims['exp'] > time.time()
                        result = dict(token=TOKEN, repositories=[dict(id=RID, full_name=REPO)], permissions=dict(contents='write', metadata='read'))
                    else:
                        assert self.headers.get('Authorization') == 'Bearer ' + TOKEN
                        assert path.startswith('/repos/' + REPO)
                        suffix = path[len('/repos/' + REPO):]
                        if self.command == 'GET' and suffix == '':
                            result = dict(id=RID, full_name=REPO, owner=dict(id=23397294, login='markmalina'))
                        elif self.command == 'GET' and suffix == '/git/ref/heads/' + BRANCH:
                            result = dict(ref='refs/heads/' + BRANCH, object=dict(type='commit', sha=fixture.head))
                        elif self.command == 'GET' and suffix == '/git/commits/' + 'a' * 40:
                            result = dict(sha='a' * 40, tree=dict(sha='b' * 40))
                        elif self.command == 'POST' and suffix == '/git/blobs':
                            assert body['encoding'] == 'base64'
                            raw = base64.b64decode(body['content'], validate=True)
                            assert len(raw) <= 16384
                            sha = git_sha('blob', raw)
                            fixture.blobs[sha] = raw
                            result = dict(sha=sha)
                        elif self.command == 'POST' and suffix == '/git/trees':
                            assert body['base_tree'] == 'b' * 40
                            tree = body['tree']
                            assert len(tree) == 2
                            assert {x['path'] for x in tree} == {'fixtures/текст.txt', 'fixtures/binary.bin'}
                            assert all(x['mode'] == '100644' and x['type'] == 'blob' and x['sha'] in fixture.blobs for x in tree)
                            fixture.tree = tree
                            # Stub object IDs for tree/commit; only blob IDs reproduce real Git objects.
                            fixture.tree_sha = git_sha('tree', json.dumps(tree, sort_keys=True).encode())
                            result = dict(sha=fixture.tree_sha)
                        elif self.command == 'POST' and suffix == '/git/commits':
                            assert body['parents'] == ['a' * 40] and body['tree'] == fixture.tree_sha
                            assert body['message'].startswith('work-upload:')
                            fixture.commit_writes += 1
                            sha = git_sha('commit', json.dumps(body, sort_keys=True).encode())
                            result = dict(sha=sha, parents=[dict(sha='a' * 40)], tree=dict(sha=fixture.tree_sha))
                        elif self.command == 'PATCH' and suffix == '/git/refs/heads/' + BRANCH:
                            assert body['force'] is False and len(body['sha']) == 40
                            fixture.head = body['sha']
                            fixture.ref_writes += 1
                            result = dict(ref='refs/heads/' + BRANCH, object=dict(type='commit', sha=fixture.head))
                        elif self.command == 'GET' and suffix == '/compare/' + fixture.head + '...' + BRANCH:
                            result = dict(status='identical', merge_base_commit=dict(sha=fixture.head))
                        else:
                            raise ValueError('unexpected fixture route')
                    raw = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                except Exception:
                    fixture.errors += 1
                    self.send_error(400, 'fixture protocol mismatch')
            do_GET = do_POST = do_PATCH = run_request
        return Handler


def run(root):
    source, runtime = root / 'source', root / 'runtime'
    runtime.mkdir(mode=0o700)
    sys.path.insert(0, str(source))
    import work_upload as w
    cli = root / 'node_modules/n8n/bin/n8n'
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {k: os.environ[k] for k in ('PATH', 'HOME', 'LANG', 'TMPDIR') if k in os.environ}
    env.update(N8N_USER_FOLDER=str(runtime), N8N_HOST='127.0.0.1', N8N_LISTEN_ADDRESS='127.0.0.1',
               N8N_PORT=str(port), N8N_PROTOCOL='http', N8N_ENCRYPTION_KEY=secrets.token_hex(32),
               N8N_DIAGNOSTICS_ENABLED='false', N8N_VERSION_NOTIFICATIONS_ENABLED='false',
               N8N_TEMPLATES_ENABLED='false', N8N_DISABLED_MODULES='mcp-registry,community-packages',
               N8N_COMMUNITY_PACKAGES_ENABLED='false', NODES_EXCLUDE='[]', N8N_RUNNERS_ENABLED='true',
               N8N_RUNNERS_MODE='internal', N8N_SECURE_COOKIE='false', N8N_LOG_LEVEL='warn',
               UPLOAD_LEDGER_DIR=str(runtime / 'ledger'))
    proc = log = server = thread = fixture = None
    result = dict(outcome='UNAVAILABLE', phase='setup')
    def local_http(method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            conn.request(method, path, json.dumps(body).encode() if body is not None else None, {'Content-Type': 'application/json'})
            res = conn.getresponse()
            return res.status, res.read(1048576)
        finally:
            conn.close()
    def command(*args):
        c = subprocess.run(['node', str(cli), *args], env=env, capture_output=True, timeout=45)
        if c.returncode:
            (runtime / 'command-failure.log').write_bytes(c.stdout + c.stderr)
            raise RuntimeError('E_NATIVE_COMMAND')
        return c.stdout
    def stop():
        nonlocal proc, log
        if proc is not None:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(8)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(5)
            proc = None
        if log:
            log.close()
            log = None
    def start():
        nonlocal proc, log
        log = (runtime / 'n8n.log').open('ab')
        proc = subprocess.Popen(['node', str(cli), 'start'], env=env, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                raise RuntimeError('E_NATIVE_START')
            try:
                if local_http('GET', '/healthz/readiness')[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.3)
        raise RuntimeError('E_NATIVE_READINESS')
    def interrupted(*args):
        raise TimeoutError('bounded probe interrupted')
    signal.signal(signal.SIGTERM, interrupted)
    try:
        version = command('--version').decode().strip()
        assert version == '2.46.6', 'E_NATIVE_VERSION'
        result['nativeVersion'] = version
        start()
        status, _ = local_http('POST', '/rest/owner/setup', dict(email='fixture@example.invalid', firstName='Native', lastName='Fixture', password='Native-fixture-' + secrets.token_hex(12)))
        assert status == 200, 'E_OWNER_SETUP'
        stop()
        fixture = Fixture()
        server = ThreadingHTTPServer(('127.0.0.1', 0), fixture.handler())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        workflow = json.loads((source / 'owner-repository-upload.workflow.json').read_text())
        changes = []
        for index, node in enumerate(workflow['nodes']):
            if 'jwtAuth' in node.get('credentials', {}):
                node['credentials']['jwtAuth']['name'] = 'Native fixture signing key'
                changes.append('/nodes/' + str(index) + '/credentials/jwtAuth/name')
            for key in ('command', 'jsCode', 'url'):
                if key in node['parameters']:
                    old = node['parameters'][key]
                    new = old.replace('/data/work/control/upload-ledger.cjs', str(source / 'upload-ledger.cjs')).replace('https://api.github.com', origin)
                    if new != old:
                        changes.append('/nodes/' + str(index) + '/parameters/' + key)
                        node['parameters'][key] = new
        result['testOnlyChangedPaths'] = changes
        (runtime / 'workflow.json').write_text(json.dumps(workflow))
        key = runtime / 'fixture.pem'
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(key)], check=True, capture_output=True, timeout=10)
        credentials = [dict(id='workPilotGithubJwt', name='Native fixture signing key', type='jwtAuth', data=dict(keyType='pemKey', privateKey=key.read_text(), algorithm='RS256'))]
        (runtime / 'credentials.json').write_text(json.dumps(credentials))
        command('import:credentials', '--input=' + str(runtime / 'credentials.json'))
        command('import:workflow', '--input=' + str(runtime / 'workflow.json'))
        command('publish:workflow', '--id=workOwnerRepositoryUploadV1')
        start()
        db_path = next(runtime.rglob('database.sqlite'))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with sqlite3.connect(db_path) as db:
                row = db.execute('SELECT e.activeVersionId,p.publishedVersionId FROM workflow_entity e JOIN workflow_published_version p ON e.id=p.workflowId WHERE e.id=?', ('workOwnerRepositoryUploadV1',)).fetchone()
                if row and row[0] == row[1]:
                    result['publishedVersion'] = row[0]
                    snapshot = db.execute('SELECT nodes FROM workflow_history WHERE versionId=?', (row[0],)).fetchone()
                    assert snapshot and json.loads(snapshot[0]) == workflow['nodes'], 'E_SNAPSHOT_BYTES'
                    result['publishedNodesExact'] = True
                    break
            time.sleep(0.3)
        else:
            raise RuntimeError('E_PUBLISHED_SNAPSHOT')
        result['phase'] = 'native-binary'
        payloads = {'binary.bin': b'\x00\xff\x80' + bytes(range(256)), 'текст.txt': 'Тест native binary\n'.encode()}
        mappings = []
        for name, payload in payloads.items():
            path = runtime / name
            path.write_bytes(payload)
            mappings.append(dict(source=str(path), path=name))
        bundle = w.prepare(dict(repositoryId=RID, repository=REPO, branch=BRANCH, prefix='fixtures'), mappings)
        c = subprocess.run(['node', str(source / 'upload-ledger.cjs'), 'grant', json.dumps(bundle['grantRequest'])], env=env, capture_output=True, timeout=10)
        assert c.returncode == 0, 'E_FIXTURE_GRANT'
        grant = json.loads(c.stdout)
        def factory(host, **options):
            assert host == w.HOST
            return http.client.HTTPConnection('127.0.0.1', port, timeout=40)
        receipt = w.upload(bundle, grant, connection_factory=factory)
        replay = w.upload(bundle, grant, connection_factory=factory)
        assert receipt['commitSha'] == replay['commitSha'] == fixture.head and replay.get('replayed') is True, 'E_REPLAY'
        assert fixture.commit_writes == fixture.ref_writes == 1 and fixture.errors == 0, 'E_STUB_COUNTS'
        for name, payload in payloads.items():
            entry = next(x for x in fixture.tree if x['path'] == 'fixtures/' + name)
            raw = fixture.blobs[entry['sha']]
            manifest = next(x for x in bundle['manifest']['files'] if x['path'] == name)
            assert raw == payload and git_sha('blob', raw) == entry['sha'], 'E_REMOTE_BLOB'
            assert len(raw) == manifest['bytes'] and hashlib.sha256(raw).hexdigest() == manifest['sha256'], 'E_REMOTE_BYTES'
        result.update(outcome='PASS', filesVerified=2, commitWrites=1, refWrites=1, replayed=True)
    except Exception as exc:
        import traceback
        (runtime / 'probe-exception.log').write_text(traceback.format_exc())
        result['errorType'] = type(exc).__name__
        if isinstance(exc, w.UploadError):
            result['errorCode'] = exc.code
        elif isinstance(exc, (AssertionError, RuntimeError)) and str(exc).startswith('E_'):
            result['errorCode'] = str(exc)
    finally:
        if fixture is not None:
            result['stubCounters'] = dict(commitWrites=fixture.commit_writes, refWrites=fixture.ref_writes, protocolErrors=fixture.errors)
        # Read execution/version evidence while the DB writer is still alive;
        # stopped-DB reads were inconsistent in #21/R1. Never relax PASS checks.
        result['executionMetadataPhase'] = 'before-stop'
        db_files = list(runtime.rglob('database.sqlite'))
        if db_files:
            try:
                with sqlite3.connect(db_files[0]) as db:
                    rows = db.execute('SELECT id,status,workflowVersionId FROM execution_entity WHERE workflowId=? ORDER BY id', ('workOwnerRepositoryUploadV1',)).fetchall()
                metadata = []
                node_names = [n['name'] for n in json.loads((runtime / 'workflow.json').read_text())['nodes']]
                for execution_id, status, executed_version in rows:
                    detail = {}
                    try:
                        with sqlite3.connect(db_files[0]) as db:
                            data = db.execute('SELECT data FROM execution_data WHERE executionId=?', (execution_id,)).fetchone()[0]
                    except sqlite3.DatabaseError:
                        result['executionPayloadReadback'] = 'UNAVAILABLE_SQLITE_ERROR'
                        metadata.append(dict(id=execution_id, status=status, versionId=executed_version, lastNode=None, errorCode=None))
                        continue
                    # Parse execution data in memory; stdout contains only approved metadata.
                    extract = "const fs=require('node:fs');const {parse}=require(process.argv[1]);const d=parse(fs.readFileSync(0,'utf8'));const r=d.resultData||{};console.log(JSON.stringify({lastNode:r.lastNodeExecuted||null,errorCode:(String(r.error?.message||'').match(/\\b(?:E_[A-Z0-9_]+|GRANT_DENIED)\\b/)||[])[0]||null}));"
                    c = subprocess.run(['node', '-e', extract, str(root / 'node_modules/flatted')], input=data.encode(), capture_output=True, timeout=5)
                    detail = json.loads(c.stdout) if c.returncode == 0 else {}
                    metadata.append(dict(id=execution_id, status=status, versionId=executed_version, lastNode=detail.get('lastNode') if detail.get('lastNode') in node_names else None, errorCode=detail.get('errorCode')))
                result['executions'] = metadata
                if result['outcome'] == 'PASS':
                    if len(metadata) != 2 or any(e['status'] != 'success' or e['versionId'] != result['publishedVersion'] for e in metadata):
                        result.update(outcome='FAIL', errorCode='E_EXECUTED_VERSION')
                elif result['phase'] == 'native-binary' and any(e['status'] == 'error' for e in metadata):
                    result['outcome'] = 'FAIL'
            except Exception as exc:
                result['executionMetadataError'] = type(exc).__name__
                if result['outcome'] == 'PASS':
                    result.update(outcome='UNAVAILABLE', errorCode='E_EXECUTION_METADATA')
        stop()
        if server:
            server.shutdown()
            server.server_close()
        if thread:
            thread.join(5)
        result['processesStopped'] = proc is None and (thread is None or not thread.is_alive())
        (root / 'result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    run(parser.parse_args().root.resolve())
