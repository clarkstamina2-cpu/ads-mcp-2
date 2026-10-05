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

"""Module declaring the singleton MCP instance.

The singleton allows other modules to register their tools with the same MCP
server using `@mcp.tool` annotations, thereby 'coordinating' the bootstrapping
of the server.
"""

import os
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

_CLIENT_ID = os.environ.get("GOOGLE_ADS_MCP_OAUTH_CLIENT_ID")
_CLIENT_SECRET = os.environ.get("GOOGLE_ADS_MCP_OAUTH_CLIENT_SECRET")
_BASE_URL = os.environ.get("GOOGLE_ADS_MCP_BASE_URL", "http://localhost:8080")
_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN") or os.environ.get("GOOGLE_ADS_MCP_AUTH_TOKEN")

if _AUTH_TOKEN:
    from fastmcp.server.auth import AuthProvider, AccessToken
    from starlette.middleware import Middleware
    from urllib.parse import parse_qs

    class QueryTokenToHeaderMiddleware:
        """Allows passing bearer token via ?token=... or ?api_key=... in URLs (e.g. Claude Web)."""

        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope.get("type") == "http":
                query_string = scope.get("query_string", b"").decode("utf-8")
                if query_string:
                    params = parse_qs(query_string)
                    token = params.get("token", [None])[0] or params.get("api_key", [None])[0] or params.get("auth", [None])[0]
                    if token:
                        headers = dict(scope.get("headers", []))
                        if b"authorization" not in headers:
                            scope["headers"] = list(scope.get("headers", [])) + [
                                (b"authorization", f"Bearer {token}".encode("utf-8"))
                            ]
            await self.app(scope, receive, send)

    class StaticBearerAuthProvider(AuthProvider):
        """Simple and secure static bearer token authentication for remote MCP deployments."""

        def __init__(self, token: str):
            super().__init__()
            self.expected_token = token

        async def verify_token(self, token: str) -> AccessToken | None:
            if token == self.expected_token:
                return AccessToken(token=token, client_id="authorized-client", scopes=[])
            return None

        def get_middleware(self) -> list:
            return [
                Middleware(QueryTokenToHeaderMiddleware),
                *super().get_middleware(),
            ]

    mcp = FastMCP("Google Ads Server", auth=StaticBearerAuthProvider(_AUTH_TOKEN))
elif _CLIENT_ID and _CLIENT_SECRET:
    auth = GoogleProvider(
        client_id=_CLIENT_ID,
        client_secret=_CLIENT_SECRET,
        base_url=_BASE_URL,
        required_scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/adwords",
        ],
    )
    mcp = FastMCP("Google Ads Server", auth=auth)
else:
    mcp = FastMCP("Google Ads Server")
