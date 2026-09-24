#!/usr/bin/env python

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

"""Common utilities used by the MCP server."""

from typing import Any, Dict, List, Optional
import proto
from google.protobuf.message import Message as PbMessage
from google.protobuf.json_format import MessageToDict
import logging
from google.ads.googleads.client import GoogleAdsClient
try:
    from google.ads.googleads.v25.services.services.google_ads_service import (
        GoogleAdsServiceClient,
    )
except ImportError:
    from google.ads.googleads.v24.services.services.google_ads_service import (
        GoogleAdsServiceClient,
    )
from google.ads.googleads.util import get_nested_attr
import google.auth
from ads_mcp.mcp_header_interceptor import MCPHeaderInterceptor
import os
import importlib.resources

_GAQL_FILENAME = "gaql_resources.txt"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)

_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"

# In-memory mapping of child customer ID -> managing MCC ID
_account_mcc_cache: Dict[str, str] = {}


def _create_credentials() -> google.auth.credentials.Credentials:
    """Returns credentials from env vars, FastMCP token, or ADC."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=[_ADS_SCOPE],
        )
        creds.refresh(Request())
        return creds

    try:
        from fastmcp.server.dependencies import get_access_token
        token_obj = get_access_token()
        if token_obj and token_obj.token:
            return Credentials(token=token_obj.token)
    except Exception:
        pass

    credentials, _ = google.auth.default(scopes=[_ADS_SCOPE])
    return credentials


def _get_developer_token() -> str:
    dev_token = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN")
    if dev_token is None:
        raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable not set.")
    return dev_token


def _get_login_customer_id() -> str | None:
    return os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")


def get_login_customer_id_for_customer(target_customer_id: str | None = None) -> str | None:
    """Resolves the correct MCC login-customer-id for a target customer ID."""
    if not target_customer_id:
        return _get_login_customer_id()

    clean_target = str(target_customer_id).replace("-", "").strip()

    # Check cache first
    if clean_target in _account_mcc_cache:
        return _account_mcc_cache[clean_target]

    default_login_cid = _get_login_customer_id()
    if default_login_cid:
        clean_default = str(default_login_cid).replace("-", "").strip()
        if clean_target == clean_default:
            return clean_default

    # Auto-discover MCC hierarchy
    try:
        discovered_mcc = _discover_mcc_for_account(clean_target)
        if discovered_mcc:
            _account_mcc_cache[clean_target] = discovered_mcc
            return discovered_mcc
    except Exception as e:
        logger.warning(f"Could not auto-discover MCC for customer {clean_target}: {e}")

    return default_login_cid or clean_target


def _discover_mcc_for_account(target_cid: str) -> str | None:
    """Discovers which accessible MCC owns the given customer ID."""
    try:
        base_client = GoogleAdsClient(
            credentials=_create_credentials(),
            developer_token=_get_developer_token(),
            use_proto_plus=True,
        )
        customer_service = base_client.get_service("CustomerService")
        accessible = customer_service.list_accessible_customers()

        for res_name in accessible.resource_names:
            mcc_id = res_name.removeprefix("customers/")
            try:
                mcc_client = GoogleAdsClient(
                    credentials=_create_credentials(),
                    developer_token=_get_developer_token(),
                    login_customer_id=mcc_id,
                    use_proto_plus=True,
                )
                ga_service = mcc_client.get_service("GoogleAdsService")
                query = (
                    "SELECT customer_client.client_customer, "
                    "customer_client.descriptive_name, "
                    "customer_client.manager "
                    "FROM customer_client WHERE customer_client.status = 'ENABLED'"
                )
                response = ga_service.search(customer_id=mcc_id, query=query)
                for row in response:
                    child_id = row.customer_client.client_customer.removeprefix("customers/")
                    _account_mcc_cache[child_id] = mcc_id
                    if child_id == target_cid:
                        return mcc_id
            except Exception:
                continue
    except Exception as e:
        logger.warning(f"Error during MCC discovery: {e}")

    return None


def _get_googleads_client(login_customer_id: str | None = None) -> GoogleAdsClient:
    args = {
        "credentials": _create_credentials(),
        "developer_token": _get_developer_token(),
        "use_proto_plus": True,
    }
    if login_customer_id:
        args["login_customer_id"] = str(login_customer_id).replace("-", "").strip()
    client = GoogleAdsClient(**args)
    return client


def get_googleads_service(
    serviceName: str, customer_id: str | None = None, login_customer_id: str | None = None
) -> Any:
    effective_login_cid = login_customer_id or get_login_customer_id_for_customer(customer_id)
    client = _get_googleads_client(login_customer_id=effective_login_cid)
    return client.get_service(serviceName, interceptors=[MCPHeaderInterceptor()])


def get_googleads_type(typeName: str, customer_id: str | None = None):
    effective_login_cid = get_login_customer_id_for_customer(customer_id)
    return _get_googleads_client(login_customer_id=effective_login_cid).get_type(typeName)


def get_googleads_client(login_customer_id: str | None = None):
    return _get_googleads_client(login_customer_id=login_customer_id)


def format_output_value(value: Any) -> Any:
    if isinstance(value, proto.Enum):
        return value.name
    elif isinstance(value, proto.Message):
        return proto.Message.to_dict(value)
    elif isinstance(value, PbMessage):
        return MessageToDict(value, preserving_proto_field_name=True)
    elif hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        return [format_output_value(v) for v in value]
    else:
        return value


def format_output_row(row: proto.Message, attributes):
    return {
        attr: format_output_value(get_nested_attr(row, attr))
        for attr in attributes
    }


def get_gaql_resources_filepath():
    package_root = importlib.resources.files("ads_mcp")
    file_path = package_root.joinpath(_GAQL_FILENAME)
    return file_path
