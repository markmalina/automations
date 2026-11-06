import argparse
import hashlib
import json
import os
import pathlib
import secrets
import time
import urllib.error
import urllib.request
import uuid

ROOT = pathlib.Path(__file__).resolve().parent
HOST = 'https://n8n-upload-pilot.up.railway.app'
ENDPOINT = HOST + '/webhook/work-fresh-token-upload-pilot-v1'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Unexpected redirect; upload stopped')

def prepare(label, count):
    corpus = json.loads((ROOT / 'benchmark-corpus/corpus.json').read_text())
    source_rows = corpus['files'][:count]
    files = []
    sources = []
    for index, row in enumerate(source_rows):
        source = ROOT / 'benchmark-corpus' / row['path']
        data = source.read_bytes()
        relative = row['path'] if count > 1 else 'Новый Work/Проверка 001.bin'
        files.append({'field': f'f{index:03}', 'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        sources.append(str(source))
    manifest = {'uploadId': str(uuid.uuid4()), 'files': files}
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    binding = {'id': manifest['uploadId'], 'digest': hashlib.sha256(canonical).hexdigest(), 'fileCount': len(files), 'totalBytes': sum(row['bytes'] for row in files)}
    state = {'label': label, 'manifest': manifest, 'binding': binding, 'sources': sources, 'endpoint': ENDPOINT}
    (ROOT / f'{label}-prepared.json').write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'label': label, 'binding': binding, 'endpoint': ENDPOINT}, ensure_ascii=False))

def upload(label, suffix):
    state = json.loads((ROOT / f'{label}-prepared.json').read_text())
    private = json.loads((ROOT / f'.{label}-grant.json').read_text())
    grant = private['grant']
    binding = state['binding']
    assert grant['uploadId'] == binding['id']
    assert grant['manifestDigest'] == binding['digest']
    assert grant['repository'] == 'markmalina/freelance' and grant['branch'] == 'test/n8n-upload-20261106'
    assert grant['headerName'] == 'X-Work-Upload-Grant'
    assert len(grant['token']) == 64 and all(c in '0123456789abcdef' for c in grant['token'])
    boundary = 'NewWorkProbe' + secrets.token_hex(12)
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="manifest"\r\n\r\n'.encode(), json.dumps(state['manifest'], ensure_ascii=False).encode(), b'\r\n']
    for row, source_name in zip(state['manifest']['files'], state['sources']):
        data = pathlib.Path(source_name).read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        parts.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="{row["field"]}"; filename="part.bin"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode(), data, b'\r\n'])
    parts.append(f'--{boundary}--\r\n'.encode())
    body = b''.join(parts)
    request = urllib.request.Request(ENDPOINT, data=body, method='POST', headers={'Content-Type': f'multipart/form-data; boundary={boundary}', grant['headerName']: grant['token']})
    start = time.perf_counter()
    report = {'label': label, 'uploadId': binding['id'], 'manifestDigest': binding['digest'], 'fileCount': binding['fileCount'], 'totalBytes': binding['totalBytes'], 'mcpExecutionId': private['executionId'], 'endpoint': ENDPOINT}
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=180) as response:
            report['httpStatus'] = response.status
            receipt = json.load(response)
        allowed = ['success', 'repository', 'branch', 'commitSha', 'url', 'uploadId', 'fileCount', 'totalBytes', 'files', 'replayed', 'githubTokenExpiresAt', 'processingMs', 'gitPushWindowMs', 'productionReady', 'manifestDigest']
        report['receipt'] = {key: receipt[key] for key in allowed if key in receipt}
        report['validReceipt'] = receipt.get('success') is True and receipt.get('uploadId') == binding['id'] and receipt.get('fileCount') == binding['fileCount'] and receipt.get('totalBytes') == binding['totalBytes'] and len(receipt.get('commitSha', '')) == 40 and receipt.get('repository') == 'markmalina/freelance' and receipt.get('branch') == 'test/n8n-upload-20261106'
    except urllib.error.HTTPError as error:
        report.update({'httpStatus': error.code, 'validReceipt': False, 'errorType': 'HTTPError', 'outcome': 'unconfirmed; inspect remote before retry'})
    except Exception as error:
        report.update({'httpStatus': None, 'validReceipt': False, 'errorType': type(error).__name__, 'outcome': 'unconfirmed; inspect remote before retry'})
    report['httpSeconds'] = round(time.perf_counter() - start, 6)
    if private.get('flowStartMs'):
        report['oauthGrantToReceiptSeconds'] = round(time.time() - private['flowStartMs'] / 1000, 6)
    (ROOT / f'{label}-{suffix}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({**{key: value for key, value in report.items() if key != 'receipt'}, 'receipt': {key: value for key, value in report.get('receipt', {}).items() if key != 'files'}}, ensure_ascii=False))

parser = argparse.ArgumentParser()
parser.add_argument('mode', choices=['prepare', 'upload'])
parser.add_argument('--label', required=True)
parser.add_argument('--count', type=int, default=1)
parser.add_argument('--suffix', default='upload')
args = parser.parse_args()
if args.mode == 'prepare':
    prepare(args.label, args.count)
else:
    upload(args.label, args.suffix)
