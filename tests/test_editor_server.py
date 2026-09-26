from __future__ import annotations
import hashlib
import http.client
import json
import re
import threading
import unittest
from axm_character_editor import new_blueprint
from axm_character_editor.editor_server import create_server
from axm_character_editor.game_asset_verify import verify_bytes


class EditorServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server(0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port
        cls.token = json.loads(re.search(r'const SERVER=(\{[^;]+\});', cls.request('GET', '/')[1].decode()).group(1))['token']

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    @classmethod
    def request(cls, method, path, value=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=20)
        body = json.dumps(value) if value is not None else None
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        result = response.status, response.read(), dict(response.getheaders())
        connection.close()
        return result

    def headers(self):
        return {'Content-Type': 'application/json', 'X-AXM-Token': self.token}

    def test_live_preview_is_real_glb_with_independent_deformation(self):
        blueprint = new_blueprint('web-preview')
        status, body, headers = self.request('POST', '/api/preview', blueprint, self.headers())
        self.assertEqual(status, 200)
        self.assertEqual(headers['X-AXM-SHA256'], hashlib.sha256(body).hexdigest())
        self.assertEqual(verify_bytes(body)['status'], 'SOFTWARE_DEFORMATION_PASS')
        self.assertEqual(self.request('POST', '/api/preview', blueprint, self.headers())[1], body)

    def test_rejects_invalid_blueprints_and_untrusted_requests(self):
        blueprint = new_blueprint('invalid')
        blueprint['controls']['height'] = 900
        self.assertEqual(self.request('POST', '/api/preview', blueprint, self.headers())[0], 400)
        self.assertEqual(self.request('POST', '/api/preview', blueprint, {'Content-Type': 'application/json'})[0], 403)
        self.assertEqual(self.request('POST', '/api/preview', blueprint, {**self.headers(), 'Origin': 'https://example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/', headers={'Host': 'example.com'})[0], 403)
        self.assertEqual(self.request('GET', '/../../pyproject.toml')[0], 404)
        self.assertEqual(self.request('POST', '/api/preview', {'large': 'x'*66000}, self.headers())[0], 413)
