"""Contract checks on bytes emitted by upload(), not a hand-written MIME fixture."""
import datetime as dt
from email import policy
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import work_upload as w
import test_work_upload as fixtures


def capture_packet(client=w):
    payloads = {'текст.txt': 'Текст UTF-8\n'.encode(), 'binary.bin': bytes(range(256)) + b'\x00\xff'}
    with tempfile.TemporaryDirectory() as directory:
        files = []
        for name, raw in payloads.items():
            path = Path(directory) / name
            path.write_bytes(raw)
            files.append(dict(source=str(path), path=name))
        target = dict(repositoryId=1448151721, repository='markmalina/automations', branch='test/upload', prefix='данные')
        bundle = client.prepare(target, files, '71717171-1717-4171-8171-171717171717')
        grant = dict(uploadId=bundle['manifest']['uploadId'], manifestDigest=bundle['digest'], target=target,
                     uploadUrl=client.URL, headerName='X-Work-Upload-Grant', token='f' * 64,
                     expiresAt=dt.datetime.fromtimestamp(fixtures.NOW + 600, dt.timezone.utc).isoformat())
        receipt = dict(success=True, uploadId=grant['uploadId'], repository=target['repository'],
                       repositoryId=target['repositoryId'], branch=target['branch'], fileCount=2,
                       totalBytes=sum(map(len, payloads.values())), commitSha='a' * 40,
                       url='https://github.com/markmalina/automations/commit/' + 'a' * 40,
                       files=[dict(path=target['prefix'] + '/' + f['path'], sha256=f['sha256'], bytes=f['bytes']) for f in bundle['manifest']['files']])
        conn = fixtures.Connection(fixtures.Response(json.dumps(receipt).encode()))
        client.upload(bundle, grant, lambda *args, **kwargs: conn, fixtures.NOW)
        # Never forward the origin grant header to the parser bridge or its argv.
        headers = {k: conn.headers[k] for k in ('Content-Type', 'Content-Length')}
        return bytes(conn.body), headers, bundle, payloads


class MultipartTests(unittest.TestCase):
    def setUp(self):
        self.body, self.headers, self.bundle, self.payloads = capture_packet()
        raw = ('Content-Type: ' + self.headers['Content-Type'] + '\r\nMIME-Version: 1.0\r\n\r\n').encode() + self.body
        self.parts = list(BytesParser(policy=policy.default).parsebytes(raw).iter_parts())

    def test_manifest_is_a_text_field_with_exact_canonical_unicode_json(self):
        part = self.parts[0]
        self.assertEqual(part.get_param('name', header='Content-Disposition'), 'manifest')
        self.assertIsNone(part.get_filename())
        self.assertIsNone(part['Content-Type'])
        self.assertEqual(part.get_payload(decode=True), w.canonical(self.bundle['manifest']))
        self.assertEqual(json.loads(part.get_payload(decode=True)), self.bundle['manifest'])

    def test_binary_fields_and_length_match_the_real_emitted_packet(self):
        self.assertEqual(int(self.headers['Content-Length']), len(self.body))
        self.assertEqual(len(self.parts), 3)
        for part, f in zip(self.parts[1:], self.bundle['manifest']['files']):
            raw = part.get_payload(decode=True)
            self.assertEqual(part.get_param('name', header='Content-Disposition'), f['field'])
            self.assertEqual(part.get_content_type(), 'application/octet-stream')
            self.assertEqual(raw, self.payloads[f['path']])
            self.assertEqual(len(raw), f['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), f['sha256'])


if __name__ == '__main__':
    unittest.main()
