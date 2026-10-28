"""Offline protocol and transport tests; never reaches Visual Paradigm."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import transport
from mcp_server import BY_NAME

ROOT = Path(__file__).resolve().parents[1]


class ProtocolTests(unittest.TestCase):
    def test_stdio_handshake_and_schema_errors(self):
        messages = [
            {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-03-26'}},
            {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
            {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
            {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'delete_relationship', 'arguments': {}}},
            {'jsonrpc': '2.0', 'id': 4, 'method': 'ping'},
        ]
        result = subprocess.run([sys.executable, str(ROOT / 'mcp_server.py')],
            input=''.join(json.dumps(m) + '\n' for m in messages), text=True, capture_output=True, timeout=5, check=True)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual([x['id'] for x in replies], [1, 2, 3, 4])
        self.assertEqual(replies[0]['result']['protocolVersion'], '2025-03-26')
        self.assertEqual({t['name'] for t in replies[1]['result']['tools']}, set(BY_NAME))
        self.assertTrue(replies[2]['result']['isError'])
        self.assertEqual(replies[3]['result'], {})

    def test_inflight_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(transport, 'IPC', Path(temp)):
            (Path(temp) / 'ready.json').write_text('{}')
            (Path(temp) / 'inflight.json').write_text('{"id":"pending"}')
            with self.assertRaisesRegex(RuntimeError, 'pending'):
                transport.request()
            self.assertFalse((Path(temp) / 'request.properties').exists())

    def test_properties_escape_values(self):
        value = transport.properties({'name': 'Строка\n x=1: \\next'})
        self.assertEqual(value.count('\n'), 1)
        self.assertIn('\\n', value)
        self.assertIn('\\=', value)


if __name__ == '__main__':
    unittest.main()
