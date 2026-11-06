"""Live pilot verification. Secret loaded locally, never printed or committed."""
import argparse
import hashlib
import json
import pathlib
import time
import urllib.error
import urllib.request
from probe_work import NoRedirect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('file', type=pathlib.Path)
    parser.add_argument('--label', required=True)
    parser.add_argument('--url', required=True)
    args = parser.parse_args()
    if not args.url.startswith('https://') or '?' in args.url:
        raise SystemExit('HTTPS URL without query required')
    root = pathlib.Path(__file__).parent
    token = json.loads((root / '.pilot-secrets.json').read_text())['PILOT_UPLOAD_TOKEN']
    payload = args.file.read_bytes()
    opener = urllib.request.build_opener(NoRedirect)
    checks = []
    for kind, auth in [('missing', None), ('wrong', 'invalid-pilot-token'), ('correct', token)]:
        headers = {'Content-Type': 'application/octet-stream'}
        if auth is not None:
            headers['X-Work-Upload-Token'] = auth
        started = time.perf_counter()
        try:
            with opener.open(urllib.request.Request(args.url, data=payload if kind == 'correct' else b'test', headers=headers, method='POST'), timeout=120) as response:
                status = response.status
                returned = response.read(len(payload) + 1)
        except urllib.error.HTTPError as exc:
            status = exc.code
            returned = b''
        check = {'auth': kind, 'status': status, 'total_seconds': round(time.perf_counter() - started, 6)}
        if kind == 'correct':
            check.update({'bytes': len(payload), 'returned_bytes': len(returned), 'source_sha256': hashlib.sha256(payload).hexdigest(), 'returned_sha256': hashlib.sha256(returned).hexdigest(), 'match': returned == payload})
            check['passed'] = status == 200 and returned == payload
        else:
            check['passed'] = status in (401, 403)
        checks.append(check)
    report = {'test': args.label, 'file_name': args.file.name, 'url': args.url, 'checks': checks, 'all_passed': all(c['passed'] for c in checks), 'github_tested': False, 'timing_note': 'Client roundtrip only. Upload, server processing and network return are not separated.'}
    out = root / (args.label + '.json')
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(report, ensure_ascii=False))
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
