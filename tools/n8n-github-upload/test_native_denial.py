"""Prevent false positive native-denial acceptance from an HTTP error alone."""
import unittest
from native_binary_probe import negative_evidence_valid

class NativeDenialEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.metadata = [dict(status='error', versionId='expected')]
        self.counters = dict(requests=0, commitWrites=0, refWrites=0, protocolErrors=0)
        self.ledger = dict(uploadRows=0, commits=0, receipts=0, states={})
    def valid(self, **changes):
        args = dict(metadata=self.metadata, version='expected', counters=self.counters,
                    before=self.ledger, after=self.ledger, native_code='GRANT_DENIED', client_code='E_UPLOAD_HTTP_500')
        args.update(changes)
        return negative_evidence_valid(**args)
    def test_complete_expected_denial_evidence(self):
        self.assertTrue(self.valid())
    def test_http_500_alone_is_not_native_denial(self):
        self.assertFalse(self.valid(native_code=None))
        self.assertFalse(self.valid(metadata=[]))
    def test_installation_token_request_invalidates_zero_write_claim(self):
        self.assertFalse(self.valid(counters=dict(self.counters, requests=1)))
    def test_wrong_execution_version_rejected(self):
        self.assertFalse(self.valid(metadata=[dict(status='error', versionId='stale')]))
    def test_upload_claim_or_receipt_change_rejected(self):
        self.assertFalse(self.valid(after=dict(self.ledger, uploadRows=1)))
        changed=dict(self.ledger, receipts=1)
        self.assertFalse(self.valid(before=changed, after=changed))
