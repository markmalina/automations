"""One multipart HTTP request, individual files, no ZIP or model-visible bytes."""
import argparse
import hashlib
import http.client
import json
import mimetypes
import pathlib
import secrets
import time
import urllib.error
import urllib.request
from probe_work import NoRedirect

root = pathlib.Path(__file__).parent
parser = argparse.ArgumentParser()
parser.add_argument('--fixture-root', type=pathlib.Path, default=pathlib.Path('/tmp/n8n-upload-fixtures/mixed'))
fixture_root = parser.parse_args().fixture_root
manifest = json.loads((fixture_root.parent / 'mixed-manifest.json').read_text())
token = json.loads((root / '.pilot-secrets.json').read_text())['PILOT_UPLOAD_TOKEN']
boundary = 'WorkProbe' + secrets.token_hex(16)
parts = []
def part(headers, value):
    parts.extend([('--' + boundary + '\r\n' + headers + '\r\n\r\n').encode(), value, b'\r\n'])
part('Content-Disposition: form-data; name="manifest"', json.dumps(manifest, ensure_ascii=False).encode())
for entry in manifest['files']:
    path = fixture_root / entry['path']
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise SystemExit('Source fixture changed')
    part('Content-Disposition: form-data; name="' + entry['field'] + '"; filename="' + path.name + '"\r\nContent-Type: ' + (mimetypes.guess_type(path.name)[0] or 'application/octet-stream'), data)
parts.append(('--' + boundary + '--\r\n').encode())
body = b''.join(parts)
timing = {}
original_send = http.client.HTTPConnection.send
def measured_send(connection, data):
    if data is body:
        timing['send_start'] = time.perf_counter()
        result = original_send(connection, data)
        timing['send_finished'] = time.perf_counter()
        return result
    return original_send(connection, data)
http.client.HTTPConnection.send = measured_send
started = time.perf_counter()
try:
    req = urllib.request.Request('https://n8n-upload-pilot.up.railway.app/webhook/work-multipart-hash-probe-v1', data=body, method='POST', headers={'Content-Type': 'multipart/form-data; boundary=' + boundary, 'X-Work-Upload-Token': token})
    with urllib.request.build_opener(NoRedirect).open(req, timeout=180) as response:
        headers_at = time.perf_counter()
        returned = json.load(response)
        status = response.status
except urllib.error.HTTPError as exc:
    print(json.dumps({'status': exc.code, 'result': 'failed', 'body_suppressed': True}))
    raise SystemExit(1)
finally:
    http.client.HTTPConnection.send = original_send
received = {f['path']: f for f in returned.get('files', [])}
match = len(received) == len(manifest['files']) and all(received.get(f['path'], {}).get('sha256') == f['sha256'] for f in manifest['files'])
report = {'test': 'work-n8n-100-files-multipart', 'http_status': status, 'fileCount': len(received), 'totalFileBytes': manifest['totalBytes'], 'multipartBytes': len(body), 'allPathHashesMatch': match, 'n8nReceipt': returned, 'total_seconds': round(time.perf_counter()-started, 6), 'github_tested': False, 'request_count': 1, 'zip_used': False, 'timing_note': 'client_body_send_seconds measures socket sendall, not confirmed receipt at n8n. processingMs starts after multipart parsing. Remaining waits include network/proxy and scheduling.'}
if 'send_finished' in timing:
    report['client_body_send_seconds'] = round(timing['send_finished']-timing['send_start'], 6)
    report['wait_after_send_until_headers_seconds'] = round(headers_at-timing['send_finished'], 6)
(root / 'live-multipart-100-files.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='n8nReceipt'}, ensure_ascii=False))
if not match or not returned.get('allMatch'):
    raise SystemExit(1)
