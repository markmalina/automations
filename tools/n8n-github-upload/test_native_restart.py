"""Reject stale snapshots and missing durable receipts before native replay."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from native_binary_probe import published_snapshot, ledger_evidence

class NativeRestartGuards(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.sqlite'
        with sqlite3.connect(self.path) as db:
            db.executescript('CREATE TABLE workflow_entity(id TEXT,activeVersionId TEXT); CREATE TABLE workflow_published_version(workflowId TEXT,publishedVersionId TEXT); CREATE TABLE workflow_history(versionId TEXT,nodes TEXT); CREATE TABLE uploads(id TEXT,state TEXT,commit_sha TEXT,receipt TEXT);')
            db.execute('INSERT INTO workflow_entity VALUES (?,?)', ('workOwnerRepositoryUploadV1','v1'))
            db.execute('INSERT INTO workflow_published_version VALUES (?,?)', ('workOwnerRepositoryUploadV1','v1'))
            db.execute('INSERT INTO workflow_history VALUES (?,?)', ('v1','[]'))

    def test_restart_rejects_changed_version(self):
        with self.assertRaisesRegex(AssertionError, 'E_RESTART_VERSION'):
            published_snapshot(self.path, {'nodes': []}, 'previous-version')

    def test_same_version_does_not_excuse_changed_nodes(self):
        with self.assertRaisesRegex(AssertionError, 'E_SNAPSHOT_BYTES'):
            published_snapshot(self.path, {'nodes': [{'name':'unexpected'}]}, 'v1')

    def test_missing_receipt_cannot_be_reported_as_persisted(self):
        with self.assertRaisesRegex(AssertionError, 'E_LEDGER_RECEIPT'):
            ledger_evidence(self.path, 'fixture')

    def test_receipt_fingerprint_detects_changed_durable_receipt(self):
        with sqlite3.connect(self.path) as db:
            db.execute('INSERT INTO uploads VALUES (?,?,?,?)', ('fixture','confirmed','a'*40,'{"first":1}'))
        before = ledger_evidence(self.path, 'fixture')
        with sqlite3.connect(self.path) as db:
            db.execute('UPDATE uploads SET receipt=?', ('{"different":1}',))
        after = ledger_evidence(self.path, 'fixture')
        self.assertNotEqual(before['receiptSha256'], after['receiptSha256'])
        self.assertEqual(before['inode'], after['inode'])
