"""Fault-injection boundary: drop successful body once, never hide HTTP errors."""
import http.client
import unittest
from unittest.mock import Mock, patch
from native_binary_probe import DropFirstResponseConnection

class ResponseLossAdapterTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(dropCount=0, headersStatus=None, bodyNotRead=False)
        self.conn = DropFirstResponseConnection('127.0.0.1', 1, fault_state=self.state)
        self.addCleanup(self.conn.close)
    def test_successful_headers_drop_before_any_body_read(self):
        response = Mock(status=200)
        with patch.object(http.client.HTTPConnection, 'getresponse', return_value=response):
            with self.assertRaises(ConnectionResetError):
                self.conn.getresponse()
        response.read.assert_not_called()
        response.close.assert_called_once()
        self.assertEqual(self.state, dict(dropCount=1, headersStatus=200, bodyNotRead=True))
    def test_http_error_is_returned_without_fault_or_body_read(self):
        response = Mock(status=503)
        with patch.object(http.client.HTTPConnection, 'getresponse', return_value=response):
            self.assertIs(self.conn.getresponse(), response)
        response.read.assert_not_called()
        response.close.assert_not_called()
        self.assertEqual(self.state['dropCount'], 0)
    def test_fault_is_not_injected_twice(self):
        response = Mock(status=200)
        with patch.object(http.client.HTTPConnection, 'getresponse', return_value=response):
            with self.assertRaises(ConnectionResetError):
                self.conn.getresponse()
            self.assertIs(self.conn.getresponse(), response)
        self.assertEqual(self.state['dropCount'], 1)
        response.read.assert_not_called()
        response.close.assert_called_once()
