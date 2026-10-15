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

"""Tool for creating conversion actions (e.g. website conversions) in Google Ads."""

import re
from typing import Any, Dict, List, Optional
from fastmcp.exceptions import ToolError
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.search import search
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    get_enum_class,
)

# The tool description accepts 'LEAD' because it is the common name; the API calls it SUBMIT_LEAD_FORM.
_CATEGORY_ALIASES = {"LEAD": "SUBMIT_LEAD_FORM"}
_SEND_TO_RE = re.compile(r"AW-(\d+)/([A-Za-z0-9_-]+)")


def extract_send_to(tag_snippets: Any) -> Optional[Dict[str, str]]:
    """Finds the Google Ads conversion ID and label in the tag snippets returned by the API.

    The event snippet contains `'send_to': 'AW-<conversion id>/<conversion label>'`.
    """
    for snippet in tag_snippets or []:
        text = ""
        if isinstance(snippet, dict):
            text = " ".join(str(v) for v in snippet.values() if isinstance(v, str))
        else:
            text = str(snippet)
        match = _SEND_TO_RE.search(text)
        if match:
            return {
                "conversion_id": match.group(1),
                "conversion_label": match.group(2),
                "send_to": f"AW-{match.group(1)}/{match.group(2)}",
            }
    return None


def _enum_value(client: Any, enum_name: str, value: str, field: str) -> Any:
    cls = get_enum_class(client, enum_name)
    member = getattr(cls, str(value).strip().upper(), None) if cls is not None else None
    if member is None:
        valid = [m.name for m in cls if m.name not in ("UNSPECIFIED", "UNKNOWN")] if cls is not None else []
        raise ToolError(f"Invalid {field} '{value}'. Valid values: {', '.join(valid)}.")
    return member


@mcp.tool()
def create_conversion_action(
    customer_id: str,
    name: str,
    type: str = "WEBPAGE",
    category: str = "DEFAULT",
    counting_type: str = "ONE_PER_CLICK",
    primary_for_goal: bool = False,
    click_through_lookback_window_days: int = 30,
    view_through_lookback_window_days: Optional[int] = None,
    default_value: Optional[float] = None,
    currency_code: str = "BRL",
    always_use_default_value: bool = False,
    attribution_model: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a new conversion action (e.g. a website conversion) and returns its ID and label for the Google tag / GTM.

    The new conversion is SECONDARY by default (primary_for_goal=False), so it is observed but not used for bidding.
    The response includes 'conversion_id' and 'conversion_label' (the 'AW-<id>/<label>' used in the conversion tag).

    Args:
        customer_id: The Google Ads customer ID.
        name: Name of the conversion action (must be unique in the account).
        type: Conversion type. 'WEBPAGE' for website conversions (default).
        category: 'CONTACT', 'LEAD' (same as SUBMIT_LEAD_FORM), 'SUBMIT_LEAD_FORM', 'PURCHASE', 'SIGNUP',
                  'BOOK_APPOINTMENT', 'REQUEST_QUOTE', 'GET_DIRECTIONS', 'OUTBOUND_CLICK', 'PAGE_VIEW' or 'DEFAULT'.
        counting_type: 'ONE_PER_CLICK' (one per ad click, typical for leads) or 'MANY_PER_CLICK' (typical for purchases).
        primary_for_goal: False (default) = secondary; True = primary (used for bidding/optimization).
        click_through_lookback_window_days: Click-through conversion window in days (1 to 90, default 30).
        view_through_lookback_window_days: Optional view-through conversion window in days (1 to 30). Omit to keep Google's default.
        default_value: Optional default conversion value (e.g. 50.0). Omit for no value.
        currency_code: Currency of the default value (default 'BRL').
        always_use_default_value: If True, always uses default_value instead of the value sent by the tag.
        attribution_model: Optional, e.g. 'GOOGLE_ADS_LAST_CLICK' or 'GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN'.
        validate_only: If True, only validates the request without creating anything (dry-run).

    Returns:
        Dict with the created conversion_action_id, resource_name, conversion_id, conversion_label and send_to.
        With validate_only=True returns what would be created.
    """
    cid = clean_customer_id(customer_id)
    clean_name = name.strip()
    if not clean_name:
        raise ToolError("name is required.")
    if not 1 <= int(click_through_lookback_window_days) <= 90:
        raise ToolError("click_through_lookback_window_days must be between 1 and 90.")
    if view_through_lookback_window_days is not None and not 1 <= int(view_through_lookback_window_days) <= 30:
        raise ToolError("view_through_lookback_window_days must be between 1 and 30.")

    category_name = str(category).strip().upper()
    category_name = _CATEGORY_ALIASES.get(category_name, category_name)

    try:
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        service = utils.get_googleads_service("ConversionActionService", customer_id=cid)
        op = utils.get_googleads_type("ConversionActionOperation", customer_id=cid)

        action = op.create
        action.name = clean_name
        action.type_ = _enum_value(client, "ConversionActionTypeEnum", type, "type")
        action.category = _enum_value(client, "ConversionActionCategoryEnum", category_name, "category")
        action.status = _enum_value(client, "ConversionActionStatusEnum", "ENABLED", "status")
        action.counting_type = _enum_value(client, "ConversionActionCountingTypeEnum", counting_type, "counting_type")
        action.primary_for_goal = bool(primary_for_goal)
        action.click_through_lookback_window_days = int(click_through_lookback_window_days)
        if view_through_lookback_window_days is not None:
            action.view_through_lookback_window_days = int(view_through_lookback_window_days)

        if default_value is not None:
            action.value_settings.default_value = float(default_value)
            action.value_settings.default_currency_code = str(currency_code).strip().upper()
            action.value_settings.always_use_default_value = bool(always_use_default_value)
        if attribution_model:
            action.attribution_model_settings.attribution_model = _enum_value(
                client, "AttributionModelEnum", attribution_model, "attribution_model"
            )

        planned = {
            "customer_id": cid,
            "name": clean_name,
            "type": str(type).strip().upper(),
            "category": category_name,
            "counting_type": str(counting_type).strip().upper(),
            "primary_for_goal": bool(primary_for_goal),
            "click_through_lookback_window_days": int(click_through_lookback_window_days),
            "view_through_lookback_window_days": view_through_lookback_window_days,
            "default_value": default_value,
            "currency_code": str(currency_code).strip().upper() if default_value is not None else None,
            "attribution_model": attribution_model,
        }

        if validate_only:
            service.mutate_conversion_actions(
                request={"customer_id": cid, "operations": [op], "validate_only": True}
            )
            return {"success": True, "action": "create_conversion_action", "validate_only": True, "would_create": planned}

        response = service.mutate_conversion_actions(customer_id=cid, operations=[op])
        resource_name = response.results[0].resource_name
        conversion_action_id = resource_name.rsplit("/", 1)[-1]

        rows: List[Dict[str, Any]] = search(
            customer_id=cid,
            fields=["conversion_action.id", "conversion_action.tag_snippets"],
            resource="conversion_action",
            conditions=[f"conversion_action.id = {conversion_action_id}"],
        )
        tag = extract_send_to(rows[0].get("conversion_action.tag_snippets") if rows else None)

        result: Dict[str, Any] = {
            "success": True,
            "action": "create_conversion_action",
            "validate_only": False,
            "conversion_action_id": conversion_action_id,
            "resource_name": resource_name,
            "created": planned,
            "conversion_id": tag["conversion_id"] if tag else None,
            "conversion_label": tag["conversion_label"] if tag else None,
            "send_to": tag["send_to"] if tag else None,
        }
        if not tag:
            result["note"] = (
                "The conversion was created, but the ID/label were not found in the tag snippets yet. "
                "Read them with search on conversion_action.tag_snippets for this conversion action."
            )
        return result
    except ToolError:
        raise
    except Exception as ex:
        raise handle_googleads_exception(ex)
