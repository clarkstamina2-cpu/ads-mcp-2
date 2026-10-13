# Copyright 2026 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for the token-in-URL authentication, startup validation and error hints."""

import os
import unittest
from unittest import mock

from starlette.testclient import TestClient

from ads_mcp import server
from ads_mcp.tools import mutate_utils

TOKEN = "token-de-teste"
INIT_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


class TokenAuthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client = TestClient(server.build_app(TOKEN))
        cls._client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client.__exit__(None, None, None)

    def test_health_is_public(self):
        r = self._client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_no_token_is_401(self):
        r = self._client.post("/mcp", json=INIT_BODY, headers=MCP_HEADERS)
        self.assertEqual(r.status_code, 401)

    def test_wrong_token_is_401(self):
        r = self._client.post("/mcp?token=errado", json=INIT_BODY, headers=MCP_HEADERS)
        self.assertEqual(r.status_code, 401)

    def test_token_only_in_header_is_401(self):
        headers = {**MCP_HEADERS, "Authorization": f"Bearer {TOKEN}"}
        r = self._client.post("/mcp", json=INIT_BODY, headers=headers)
        self.assertEqual(r.status_code, 401)

    def test_other_query_param_names_are_401(self):
        for name in ("api_key", "auth"):
            r = self._client.post(f"/mcp?{name}={TOKEN}", json=INIT_BODY, headers=MCP_HEADERS)
            self.assertEqual(r.status_code, 401, name)

    def test_right_token_is_accepted(self):
        r = self._client.post(f"/mcp?token={TOKEN}", json=INIT_BODY, headers=MCP_HEADERS)
        self.assertEqual(r.status_code, 200)
        self.assertIn("serverInfo", r.text)


class StartupValidationTest(unittest.TestCase):
    FULL_ENV = {
        "MCP_TOKEN": "t",
        "GOOGLE_ADS_DEVELOPER_TOKEN": "d",
        "GOOGLE_ADS_CLIENT_ID": "i",
        "GOOGLE_ADS_CLIENT_SECRET": "s",
        "GOOGLE_ADS_REFRESH_TOKEN": "r",
    }

    def _run(self, env):
        with mock.patch.dict(os.environ, env, clear=True):
            return server.validate_environment()

    def test_full_environment_passes(self):
        self.assertEqual(self._run(self.FULL_ENV), "t")

    def test_missing_token_exits_with_clear_message(self):
        env = {k: v for k, v in self.FULL_ENV.items() if k != "MCP_TOKEN"}
        with self.assertRaises(SystemExit) as ctx:
            self._run(env)
        self.assertIn("MCP_TOKEN", str(ctx.exception))

    def test_missing_google_credentials_exits(self):
        env = {k: v for k, v in self.FULL_ENV.items() if k != "GOOGLE_ADS_REFRESH_TOKEN"}
        with self.assertRaises(SystemExit) as ctx:
            self._run(env)
        self.assertIn("GOOGLE_ADS_REFRESH_TOKEN", str(ctx.exception))

    def test_legacy_mcp_auth_token_is_still_accepted(self):
        env = {k: v for k, v in self.FULL_ENV.items() if k != "MCP_TOKEN"}
        env["MCP_AUTH_TOKEN"] = "legado"
        self.assertEqual(self._run(env), "legado")

    def test_blank_token_is_treated_as_missing(self):
        env = {**self.FULL_ENV, "MCP_TOKEN": "   "}
        with self.assertRaises(SystemExit):
            self._run(env)


class MutateNotAllowedHintTest(unittest.TestCase):
    @staticmethod
    def _fake_error(which, value):
        error_code = mock.Mock()
        error_code._pb.WhichOneof.return_value = which
        setattr(error_code, which or "none", value)
        error = mock.Mock()
        error.error_code = error_code
        return error

    def test_detects_mutate_not_allowed_by_code(self):
        self.assertTrue(mutate_utils._is_mutate_not_allowed(self._fake_error("mutate_error", 9)))

    def test_ignores_other_mutate_errors(self):
        self.assertFalse(mutate_utils._is_mutate_not_allowed(self._fake_error("mutate_error", 3)))

    def test_ignores_other_error_families(self):
        self.assertFalse(mutate_utils._is_mutate_not_allowed(self._fake_error("request_error", 9)))

    def test_hint_text_mentions_painel(self):
        self.assertIn("painel", mutate_utils._MUTATE_NOT_ALLOWED_HINT)


if __name__ == "__main__":
    unittest.main()
