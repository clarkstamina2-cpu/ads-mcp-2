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

"""Entry point for the MCP server."""

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
)  # noqa: F401
from ads_mcp.resources import (
    discovery,
    metrics,
    release_notes,
    segments,
)  # noqa: F401


import os


def run_server() -> None:
    _CLIENT_ID = os.environ.get("GOOGLE_ADS_MCP_OAUTH_CLIENT_ID")
    _CLIENT_SECRET = os.environ.get("GOOGLE_ADS_MCP_OAUTH_CLIENT_SECRET")
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    transport = os.environ.get("MCP_TRANSPORT", "").lower().strip()

    if _CLIENT_ID and _CLIENT_SECRET:
        mcp.run(
            transport="streamable-http",
            port=port,
            host=host,
            uvicorn_config={"access_log": False},
        )
    elif transport == "sse":
        mcp.run(transport="sse", port=port, host=host)
    elif transport in ("http", "streamable-http", "streamable_http"):
        mcp.run(transport="streamable-http", port=port, host=host)
    elif os.environ.get("PORT"):
        # Default for container deployments (EasyPanel / Cloud Run / Docker)
        mcp.run(transport="sse", port=port, host=host)
    else:
        # Local stdio
        mcp.run()


if __name__ == "__main__":
    run_server()
