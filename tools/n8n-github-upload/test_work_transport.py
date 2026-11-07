"""Offline transport tests: stdlib CONNECT and origin HTTP use separate phases."""
import base64
import datetime as dt
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest import mock

import work_upload as w
import test_work_upload as fixtures


class Socket:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.wire = bytearray()
        self.closed = False

    def sendall(self, data):
        self.wire.extend(data)

    def makefile(self, mode):
        return io.BytesIO(next(self.responses))

    def setsockopt(self, *args):
        pass

    def close(self):
        self.closed = True


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.context = ssl.create_default_context()

    def connection(self):
        return w.upload_connection(w.HOST, timeout=3, context=self.context)

    def test_direct_uses_verified_origin_context(self):
        conn = self.connection()
        self.assertEqual((conn.host, conn.port), (w.HOST, 443))
        self.assertIsNone(conn._tunnel_host)
        self.assertIs(conn._context, self.context)
        self.assertTrue(conn._context.check_hostname)
        self.assertEqual(conn._context.verify_mode, ssl.CERT_REQUIRED)

    def test_insecure_context_and_other_origin_rejected(self):
        self.context.check_hostname = False
        with self.assertRaisesRegex(w.UploadError, '^E_TLS_CONFIG$'):
            self.connection()
        with self.assertRaisesRegex(w.UploadError, '^E_TLS_CONFIG$'):
            w.upload_connection('other.invalid', timeout=3, context=ssl.create_default_context())

    def test_lowercase_proxy_wins_and_default_port_is_http_80(self):
        os.environ.update(HTTPS_PROXY='http://upper.invalid:3128', https_proxy='http://lower.invalid')
        conn = self.connection()
        self.assertEqual((conn.host, conn.port, conn._tunnel_host, conn._tunnel_port),
                         ('lower.invalid', 80, w.HOST, 443))

    def test_all_proxy_fallback_and_http_proxy_is_not_https_proxy(self):
        os.environ['HTTP_PROXY'] = 'http://http-only.invalid:80'
        self.assertIsNone(self.connection()._tunnel_host)
        os.environ['ALL_PROXY'] = 'http://all.invalid:8080'
        self.assertEqual(self.connection().host, 'all.invalid')

    def test_ipv6_proxy_authority(self):
        os.environ['HTTPS_PROXY'] = 'http://[::1]:8080'
        conn = self.connection()
        self.assertEqual((conn.host, conn.port, conn._tunnel_host), ('::1', 8080, w.HOST))

    def test_no_proxy_suffix_port_wildcard_and_boundary(self):
        os.environ['HTTPS_PROXY'] = 'http://proxy.invalid:8080'
        for value in (w.HOST, w.HOST + ':443', '.railway.app', '*'):
            with self.subTest(value=value):
                os.environ['NO_PROXY'] = value
                self.assertIsNone(self.connection()._tunnel_host)
        for value in ('evilrailway.app', w.HOST + ':444', 'other.invalid'):
            with self.subTest(value=value):
                os.environ['NO_PROXY'] = value
                self.assertEqual(self.connection()._tunnel_host, w.HOST)

    def test_lowercase_no_proxy_wins(self):
        os.environ.update(HTTPS_PROXY='http://proxy.invalid', NO_PROXY='*', no_proxy='other.invalid')
        self.assertEqual(self.connection()._tunnel_host, w.HOST)

    def test_unsupported_and_malformed_proxy_fail_closed_without_echo(self):
        canary = 'transport-canary-never-echo'
        for value in ('https://' + canary, 'socks5h://' + canary, canary,
                      'http://', 'http://[broken', 'http://proxy.invalid:0',
                      'http://proxy.invalid:99999', 'http://proxy.invalid:',
                      'http://proxy.invalid/path', 'http://proxy.invalid?secret=' + canary,
                      'http://proxy.invalid#' + canary, 'http://proxy.invalid\n' + canary,
                      'http://u%0d%0a:pw@proxy.invalid', 'http://u%3afoo:pw@proxy.invalid',
                      'http://u%FF:pw@proxy.invalid'):
            with self.subTest(index=len(value)):
                os.environ['HTTPS_PROXY'] = value
                with mock.patch.object(http.client, 'HTTPSConnection') as constructor:
                    with self.assertRaises(w.UploadError) as caught:
                        self.connection()
                    self.assertIn(caught.exception.code, ('E_PROXY_SCHEME', 'E_PROXY_CONFIG'))
                    self.assertNotIn(canary, str(caught.exception))
                    constructor.assert_not_called()

    def test_connect_and_upload_keep_auth_grant_sni_and_binary_separate(self):
        os.environ['HTTPS_PROXY'] = 'http://proxy-user:proxy%3Asecret@proxy.invalid:8080'
        payload = bytes(range(256)) + b'\x00\xff'
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'binary.bin'
            source.write_bytes(payload)
            target = dict(repositoryId=1448151721, repository='markmalina/automations',
                          branch='test/upload', prefix='')
            bundle = w.prepare(target, [dict(source=str(source), path='binary.bin')])
            now = 1800000000
            grant = dict(uploadId=bundle['manifest']['uploadId'], manifestDigest=bundle['digest'],
                         target=target, uploadUrl=w.URL, headerName='X-Work-Upload-Grant',
                         token='f' * 64, expiresAt=dt.datetime.fromtimestamp(now + 600, dt.timezone.utc).isoformat())
            receipt = dict(success=True, uploadId=grant['uploadId'], repositoryId=target['repositoryId'],
                           repository=target['repository'], branch=target['branch'], fileCount=1,
                           totalBytes=len(payload), commitSha='a' * 40,
                           url='https://github.com/markmalina/automations/commit/' + 'a' * 40,
                           files=[dict(path='binary.bin', bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())])
            body = json.dumps(receipt).encode()
            raw = Socket([b'HTTP/1.0 200 Connection established\r\n\r\n',
                          b'HTTP/1.1 200 OK\r\nContent-Length: ' + str(len(body)).encode() + b'\r\n\r\n' + body])
            tls_boundary = []
            def wrap(sock, *, server_hostname):
                self.assertEqual(server_hostname, w.HOST)
                tls_boundary.append(len(raw.wire))
                return sock
            real_default = ssl.create_default_context
            context = real_default()
            with mock.patch.object(w.ssl, 'create_default_context', return_value=context), \
                 mock.patch.object(context, 'wrap_socket', side_effect=wrap), \
                 mock.patch('socket.create_connection', return_value=raw) as dial:
                self.assertEqual(w.upload(bundle, grant, now=now)['commitSha'], 'a' * 40)
            self.assertEqual(dial.call_args.args[0], ('proxy.invalid', 8080))
            connect, origin = bytes(raw.wire[:tls_boundary[0]]), bytes(raw.wire[tls_boundary[0]:])
            self.assertIn(('CONNECT ' + w.HOST + ':443 HTTP/1.').encode(), connect)
            auth = base64.b64encode(b'proxy-user:proxy:secret')
            self.assertIn(b'Proxy-Authorization: Basic ' + auth, connect)
            self.assertNotIn(grant['token'].encode(), connect)
            self.assertNotIn(b'Proxy-Authorization', origin)
            self.assertNotIn(auth, origin)
            self.assertIn(('POST ' + w.ENDPOINT + ' HTTP/1.1').encode(), origin)
            self.assertIn(('Host: ' + w.HOST).encode(), origin)
            self.assertIn(payload, origin)
            self.assertTrue(raw.closed)

    def test_connect_failure_has_no_direct_fallback(self):
        os.environ['HTTPS_PROXY'] = 'http://proxy.invalid:8080'
        conn = self.connection()
        with mock.patch.object(conn, '_create_connection', side_effect=OSError('proxy-canary')) as dial:
            with self.assertRaises(OSError):
                conn.connect()
            self.assertEqual(dial.call_count, 1)
            self.assertEqual(dial.call_args.args[0], ('proxy.invalid', 8080))
        conn.close()

    def test_tls_certificate_failure_propagates_before_origin_request(self):
        os.environ['HTTPS_PROXY'] = 'http://proxy.invalid:8080'
        conn = self.connection()
        raw = Socket([b'HTTP/1.0 200 Connection established\r\n\r\n'])
        with mock.patch.object(conn, '_create_connection', return_value=raw), \
             mock.patch.object(self.context, 'wrap_socket', side_effect=ssl.SSLCertVerificationError('untrusted')):
            with self.assertRaises(ssl.SSLCertVerificationError):
                conn.connect()
        self.assertNotIn(b'POST', raw.wire)
        conn.close()

    def test_upload_config_and_tls_errors_do_not_echo_canaries(self):
        fixture = fixtures.ClientTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        canary = 'proxy-secret-canary-never-echo'
        os.environ['HTTPS_PROXY'] = 'http://proxy.invalid/path?' + canary
        with self.assertRaisesRegex(w.UploadError, '^E_PROXY_CONFIG$'):
            w.upload(fixture.bundle, fixture.grant, now=fixtures.NOW)
        with mock.patch.object(w.ssl, 'create_default_context', side_effect=OSError(canary)), \
             mock.patch.object(w, 'upload_connection') as factory:
            with self.assertRaisesRegex(w.UploadError, '^E_TLS_CONFIG$'):
                w.upload(fixture.bundle, fixture.grant, now=fixtures.NOW)
            factory.assert_not_called()
        connection = mock.Mock()
        connection.endheaders.side_effect = ssl.SSLCertVerificationError(canary)
        with mock.patch.object(w, 'upload_connection', return_value=connection):
            with self.assertRaisesRegex(w.UploadError, '^E_UPLOAD_OUTCOME_UNKNOWN$'):
                w.upload(fixture.bundle, fixture.grant, now=fixtures.NOW)
            connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
