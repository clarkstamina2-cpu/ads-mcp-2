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

"""Utility helpers for mutation tools in Google Ads MCP."""

from typing import Any, Dict, List, Optional, Union
import re
from google.ads.googleads.errors import GoogleAdsException
from fastmcp.exceptions import ToolError
import ads_mcp.utils as utils


def clean_customer_id(customer_id: Union[str, int]) -> str:
    """Removes hyphens, spaces and leading 'customers/' from customer ID."""
    cid_str = str(customer_id).strip()
    if cid_str.startswith("customers/"):
        cid_str = cid_str.removeprefix("customers/")
    return cid_str.replace("-", "").replace(" ", "")


def parse_money_to_micros(value: Union[float, int, str, None]) -> Optional[int]:
    """Converts a monetary value (in currency, e.g. BRL/USD) to micros (1 currency unit = 1,000,000 micros).
    
    If the value is already in micros (e.g. >= 10,000,000 and integer), it preserves it.
    Supports float (50.50), int (50), or string ("50.50", "R$ 50,50", "50,00").
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float)):
        if isinstance(value, int) and value >= 10_000_000:
            return value
        return int(round(float(value) * 1_000_000))
    
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d,\.]", "", value).strip()
        if "," in cleaned and "." in cleaned:
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        
        try:
            val_float = float(cleaned)
            if val_float >= 10_000_000 and val_float.is_integer():
                return int(val_float)
            return int(round(val_float * 1_000_000))
        except ValueError:
            raise ToolError(f"Could not parse monetary amount from string: '{value}'")
            
    raise ToolError(f"Invalid monetary value type: {type(value)}")


def micros_to_currency(micros: Optional[int]) -> Optional[float]:
    """Converts micros back to currency units."""
    if micros is None:
        return None
    return round(micros / 1_000_000.0, 2)


def handle_googleads_exception(ex: Exception) -> ToolError:
    """Parses GoogleAdsException into a clean, human/LLM-readable ToolError."""
    if isinstance(ex, GoogleAdsException):
        error_lines = []
        for i, error in enumerate(ex.failure.errors, 1):
            msg = error.message
            code = getattr(error.error_code, error.error_code._pb.WhichOneof("error_code") or "", "")
            trigger = error.trigger.string_value if hasattr(error.trigger, "string_value") and error.trigger.string_value else ""
            
            field_path = ""
            if error.location and error.location.field_path_elements:
                field_path = " -> ".join(
                    f"{elem.field_name}{f'[{elem.index}]' if elem.index is not None else ''}"
                    for elem in error.location.field_path_elements
                )
            
            details = [f"Error #{i}: {msg}"]
            if code:
                details.append(f"Code: {code}")
            if trigger:
                details.append(f"Trigger: '{trigger}'")
            if field_path:
                details.append(f"Field Path: {field_path}")
                
            error_lines.append(" | ".join(details))
            
        full_msg = (
            f"Google Ads API Error (Request ID: {ex.request_id}):\n"
            + "\n".join(error_lines)
        )
        utils.logger.error(full_msg)
        return ToolError(full_msg)
    
    utils.logger.error(f"Unexpected error: {ex}", exc_info=True)
    return ToolError(f"Google Ads Operation Error: {str(ex)}")


def format_mutate_response(
    action: str,
    results: List[Any],
    validate_only: bool = False,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Standardizes response format for mutate tools."""
    resource_names = []
    for r in results:
        if hasattr(r, "resource_name") and r.resource_name:
            resource_names.append(r.resource_name)
        elif isinstance(r, str):
            resource_names.append(r)
        elif isinstance(r, dict) and "resource_name" in r:
            resource_names.append(r["resource_name"])

    resp: Dict[str, Any] = {
        "success": True,
        "action": action,
        "validate_only": validate_only,
        "count": len(results),
        "resource_names": resource_names,
    }
    if extra:
        resp.update(extra)
    return resp


def get_enum_class(client: Any, enum_name: str) -> Any:
    """Safely retrieves an enum class from client.enums regardless of proto-plus unwrapping."""
    raw = getattr(client.enums, enum_name, None)
    if raw is None:
        return None
    inner = enum_name.removesuffix("Enum")
    return getattr(raw, inner, raw)


def get_enum_value(client: Any, enum_name: str, value_name: str, default: Any = None) -> Any:
    """Safely retrieves an enum value from client.enums regardless of proto-plus unwrapping."""
    enum_cls = get_enum_class(client, enum_name)
    if enum_cls is None:
        return default
    return getattr(enum_cls, value_name, default)

