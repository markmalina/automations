"""Synthetic mass fixture constraints; never opens an external connection."""
import hashlib
import unittest
from native_binary_probe import Fixture, fixture_payloads, git_sha

class NativeMassFixtureTests(unittest.TestCase):
    def test_mass_packet_exact_boundary_and_distinct_binary_files(self):
        payloads = fixture_payloads('mass-100-30mb')
        self.assertEqual((len(payloads), sum(map(len, payloads.values()))), (100, 30000000))
        self.assertTrue(all(len(raw) == 300000 for raw in payloads.values()))
        self.assertEqual(len({hashlib.sha256(raw).hexdigest() for raw in payloads.values()}), 100)
        self.assertTrue(any(not path.isascii() for path in payloads))
        self.assertTrue(all(b'\x00' in raw and b'\xff' in raw for raw in payloads.values()))
        self.assertEqual(Fixture(payloads).payloads, payloads)

    def test_small_fixture_keeps_original_bytes(self):
        expected = {'binary.bin': b'\x00\xff\x80' + bytes(range(256)), 'текст.txt': 'Тест native binary\n'.encode()}
        self.assertEqual(fixture_payloads('small'), expected)
        self.assertEqual(Fixture().payloads, expected)
        for raw in expected.values():
            self.assertEqual(git_sha('blob', raw), hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest())

    def test_unknown_case_cannot_silently_use_small_fixture(self):
        with self.assertRaises(ValueError):
            fixture_payloads('unknown')
