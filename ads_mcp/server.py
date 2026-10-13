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

"""Entry point for the MCP server (Streamable HTTP, token in the URL)."""

import hmac
import logging
import os
import sys
from urllib.parse import parse_qs

import uvicorn
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from ads_mcp.coordinator import mcp

# The following imports are necessary to register the tools with the `mcp`
# object, even though they are not directly used in this file.
# The `# noqa: F401` comment tells the linter to ignore the "unused import"
# warning.
from ads_mcp.tools import (
    search,
    core,
    get_resource_metadata,
    budgets,
    campaigns,
    ad_groups,
    keywords,
    ads,
    targeting,
    assets,
    conversions,
    planner,
    reporting,
    recommendations,
    conversion_actions,
)  # noqa: F401
from ads_mcp.resources import (
    discovery,
    metrics,
    release_notes,
    segments,
)  # noqa: F401

logger = logging.getLogger("ads_mcp.server")

# Variáveis obrigatórias (configurar no Easypanel). O servidor não sobe sem elas.
REQUIRED_ENV = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
)
PUBLIC_PATHS = {"/health"}


def get_mcp_token() -> str:
    """Token da URL. `MCP_TOKEN` é o padrão; `MCP_AUTH_TOKEN` segue aceito por compatibilidade."""
    return (os.environ.get("MCP_TOKEN") or os.environ.get("MCP_AUTH_TOKEN") or "").strip()


def validate_environment() -> str:
    """Encerra com mensagem clara se faltar variável obrigatória. Devolve o token do MCP."""
    missing = [name for name in REQUIRED_ENV if not os.environ.get(name, "").strip()]
    token = get_mcp_token()
    if not token:
        missing.insert(0, "MCP_TOKEN")
    if missing:
        sys.exit(
            "ERRO: variável(is) de ambiente obrigatória(s) ausente(s): "
            + ", ".join(missing)
            + " (configure no Easypanel)."
        )
    return token


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "transport": "streamable-http", "endpoint": "/mcp"})


class TokenNaURL:
    """Middleware ASGI puro (não interfere no streaming) que valida o token na URL: /mcp?token=<MCP_TOKEN>.

    /health fica público para o healthcheck do Easypanel. O token nunca é logado.
    """

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["path"] not in PUBLIC_PATHS:
            qs = parse_qs(scope.get("query_string", b"").decode())
            provided = (qs.get("token") or [""])[0]
            if not hmac.compare_digest(provided.encode(), self.token):
                client = scope.get("client") or ("desconhecido",)
                logger.warning(
                    "[401] Acesso bloqueado em %s (IP: %s) - token ausente ou invalido",
                    scope["path"],
                    client[0],
                )
                await JSONResponse({"error": "unauthorized"}, status_code=401)(scope, receive, send)
                return
        await self.app(scope, receive, send)


def build_app(token: str):
    """Cria o app ASGI (Streamable HTTP em /mcp, stateless, protegido por token)."""
    return mcp.http_app(
        path="/mcp",
        middleware=[Middleware(TokenNaURL, token=token)],
        stateless_http=True,
    )


def run_server() -> None:
    token = validate_environment()
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    logger.info("Iniciando Google Ads MCP (Streamable HTTP) em http://%s:%s/mcp", host, port)
    uvicorn.run(
        build_app(token),
        host=host,
        port=port,
        proxy_headers=True,
        forwarded_allow_ips="*",
        access_log=False,
    )


if __name__ == "__main__":
    run_server()
