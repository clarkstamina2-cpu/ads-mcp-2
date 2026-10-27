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

"""Tools for uploading offline conversions (Click and Call) to Google Ads."""

from typing import Any, Dict, List, Optional, Union
from fastmcp.exceptions import ToolError
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    format_mutate_response,
    get_enum_class,
    get_enum_value,
)


def _require_enum(client: Any, enum_name: str, value: str, field: str) -> Any:
    """Returns the enum member for `value`, or raises a ToolError listing the valid values."""
    cls = get_enum_class(client, enum_name)
    member = getattr(cls, str(value).strip().upper(), None) if cls is not None else None
    if member is None:
        valid = [m.name for m in cls if m.name not in ("UNSPECIFIED", "UNKNOWN")] if cls is not None else []
        raise ToolError(f"Invalid {field} '{value}'. Valid values: {', '.join(valid)}.")
    return member


@mcp.tool()
def upload_click_conversions(
    customer_id: str,
    conversions: List[Dict[str, Any]],
    partial_failure: bool = True,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Uploads offline click conversions using Google Click IDs (GCLID, GBRAID, or WBRAID).

    Useful for syncing offline sales, CRM deals, or backend qualification events with Google Ads.

    Args:
        customer_id: The Google Ads customer ID.
        conversions: List of conversion dictionaries. Each dict should have:
                     - gclid (or gbraid, wbraid): The Google Click Identifier.
                     - conversion_action: The conversion action ID or full resource name ('customers/.../conversionActions/...').
                     - conversion_date_time: Timestamp string in 'yyyy-mm-dd hh:mm:ss+|-hh:mm' (e.g. '2026-09-18 15:30:00-03:00').
                     - conversion_value: Optional revenue/value amount as float (e.g. 250.00).
                     - currency_code: Optional ISO currency code (e.g. 'BRL', 'USD', default 'BRL').
                     - order_id: Optional unique transaction/order ID for deduplication.
        partial_failure: Whether to allow partial failure (default True).
        validate_only: If True, only validates without recording conversions.

    Returns:
        Dict with upload status and results.
    """
    cid = clean_customer_id(customer_id)

    try:
        conversion_upload_service = utils.get_googleads_service("ConversionUploadService", customer_id=cid)
        click_conversions = []

        for item in conversions:
            cc = utils.get_googleads_type("ClickConversion", customer_id=cid)
            
            # Action
            action_id = str(item.get("conversion_action", "")).strip()
            if action_id.startswith("customers/"):
                cc.conversion_action = action_id
            else:
                cc.conversion_action = f"customers/{cid}/conversionActions/{action_id}"

            # Timestamp
            cc.conversion_date_time = str(item.get("conversion_date_time", ""))

            # Click ID
            if "gclid" in item and item["gclid"]:
                cc.gclid = item["gclid"]
            elif "gbraid" in item and item["gbraid"]:
                cc.gbraid = item["gbraid"]
            elif "wbraid" in item and item["wbraid"]:
                cc.wbraid = item["wbraid"]

            # Value & Currency
            if "conversion_value" in item and item["conversion_value"] is not None:
                cc.conversion_value = float(item["conversion_value"])
            if "currency_code" in item and item["currency_code"]:
                cc.currency_code = item["currency_code"].upper()
            else:
                cc.currency_code = "BRL"

            # Order ID
            if "order_id" in item and item["order_id"]:
                cc.order_id = str(item["order_id"])

            click_conversions.append(cc)

        if not click_conversions:
            raise ValueError("No conversions provided to upload.")

        response = conversion_upload_service.upload_click_conversions(
            customer_id=cid,
            conversions=click_conversions,
            partial_failure=partial_failure,
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"gclid": "dry-run"} for _ in click_conversions]
        return format_mutate_response(
            action="upload_click_conversions",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "uploaded_count": len(click_conversions),
                "has_partial_failure_error": bool(response.partial_failure_error.message) if hasattr(response, "partial_failure_error") and response.partial_failure_error else False,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def upload_call_conversions(
    customer_id: str,
    conversions: List[Dict[str, Any]],
    partial_failure: bool = True,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Uploads offline call conversions to Google Ads.

    Args:
        customer_id: The Google Ads customer ID.
        conversions: List of call conversion dictionaries. Each dict should have:
                     - caller_id: The caller phone number (e.g. '+5511999998888').
                     - call_start_date_time: Call start timestamp ('yyyy-mm-dd hh:mm:ss+|-hh:mm').
                     - conversion_action: The conversion action ID or resource name.
                     - conversion_date_time: Conversion timestamp.
                     - conversion_value: Optional conversion value (e.g. 500.00).
                     - currency_code: Optional currency code ('BRL', 'USD').
        partial_failure: Whether to allow partial failure (default True).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with upload status and results.
    """
    cid = clean_customer_id(customer_id)

    try:
        conversion_upload_service = utils.get_googleads_service("ConversionUploadService", customer_id=cid)
        call_conversions = []

        for item in conversions:
            cc = utils.get_googleads_type("CallConversion", customer_id=cid)
            
            action_id = str(item.get("conversion_action", "")).strip()
            if action_id.startswith("customers/"):
                cc.conversion_action = action_id
            else:
                cc.conversion_action = f"customers/{cid}/conversionActions/{action_id}"

            cc.caller_id = str(item.get("caller_id", ""))
            cc.call_start_date_time = str(item.get("call_start_date_time", ""))
            cc.conversion_date_time = str(item.get("conversion_date_time", ""))

            if "conversion_value" in item and item["conversion_value"] is not None:
                cc.conversion_value = float(item["conversion_value"])
            if "currency_code" in item and item["currency_code"]:
                cc.currency_code = item["currency_code"].upper()
            else:
                cc.currency_code = "BRL"

            call_conversions.append(cc)

        if not call_conversions:
            raise ValueError("No call conversions provided.")

        response = conversion_upload_service.upload_call_conversions(
            customer_id=cid,
            conversions=call_conversions,
            partial_failure=partial_failure,
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"caller_id": "dry-run"} for _ in call_conversions]
        return format_mutate_response(
            action="upload_call_conversions",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "uploaded_count": len(call_conversions),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_conversion_action(
    customer_id: str,
    conversion_action_id: Union[str, int],
    primary_for_goal: Optional[bool] = None,
    status: Optional[str] = None,
    name: Optional[str] = None,
    click_through_lookback_window_days: Optional[int] = None,
    view_through_lookback_window_days: Optional[int] = None,
    counting_type: Optional[str] = None,
    attribution_model: Optional[str] = None,
    default_value: Optional[float] = None,
    always_use_default_value: Optional[bool] = None,
    default_currency_code: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates a conversion action: primary/secondary, status, name, conversion windows, counting, attribution and value rules.

    Only the parameters you pass are changed. Some fields cannot be changed for certain conversion types
    (for example conversions created and managed by Google); the API error is returned in that case.
    Google-managed types such as ANDROID_INSTALLS_ALL_OTHER_APPS reject any mutate (MUTATE_NOT_ALLOWED);
    to stop them from being used for bidding, use update_conversion_goal on their category and origin.

    Args:
        customer_id: The Google Ads customer ID.
        conversion_action_id: The Conversion Action ID or resource name ('customers/.../conversionActions/...').
        primary_for_goal: If True, marks as primary (used for bidding/optimization); if False, marks as secondary (observation only).
        status: Conversion action status ('ENABLED', 'PAUSED', 'HIDDEN').
        name: Optional new name for the conversion action.
        click_through_lookback_window_days: Click-through conversion window in days (1 to 90).
        view_through_lookback_window_days: View-through conversion window in days (1 to 30).
        counting_type: 'ONE_PER_CLICK' or 'MANY_PER_CLICK'.
        attribution_model: e.g. 'GOOGLE_ADS_LAST_CLICK', 'GOOGLE_SEARCH_ATTRIBUTION_FIRST_CLICK', 'GOOGLE_SEARCH_ATTRIBUTION_LINEAR',
                           'GOOGLE_SEARCH_ATTRIBUTION_TIME_DECAY', 'GOOGLE_SEARCH_ATTRIBUTION_POSITION_BASED',
                           'GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN' (data-driven requires account eligibility).
        default_value: Default conversion value (e.g. 1.0 or 50.0).
        always_use_default_value: If True, always uses default_value instead of the value sent by the tag.
        default_currency_code: Currency of the default value (e.g. 'BRL').
        validate_only: If True, only validates without applying changes.

    Returns:
        Dict with success status and updated conversion action details.
    """
    cid = clean_customer_id(customer_id)
    if click_through_lookback_window_days is not None and not 1 <= int(click_through_lookback_window_days) <= 90:
        raise ToolError("click_through_lookback_window_days must be between 1 and 90.")
    if view_through_lookback_window_days is not None and not 1 <= int(view_through_lookback_window_days) <= 30:
        raise ToolError("view_through_lookback_window_days must be between 1 and 30.")
    clean_id = str(conversion_action_id).replace("-", "").strip()
    if clean_id.startswith("customers/"):
        resource_name = clean_id
    else:
        resource_name = f"customers/{cid}/conversionActions/{clean_id}"

    try:
        conversion_action_service = utils.get_googleads_service("ConversionActionService", customer_id=cid)
        op = utils.get_googleads_type("ConversionActionOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        action = op.update
        action.resource_name = resource_name

        updated = {}
        if primary_for_goal is not None:
            action.primary_for_goal = primary_for_goal
            op.update_mask.paths.append("primary_for_goal")
            updated["primary_for_goal"] = primary_for_goal

        if status is not None:
            status_enum = getattr(
                get_enum_class(client, "ConversionActionStatusEnum"),
                status.upper().strip(),
                None,
            )
            if not status_enum:
                raise ValueError(f"Invalid status '{status}'. Valid statuses: ENABLED, PAUSED, HIDDEN.")
            action.status = status_enum
            op.update_mask.paths.append("status")
            updated["status"] = status.upper().strip()

        if name is not None:
            action.name = name.strip()
            op.update_mask.paths.append("name")
            updated["name"] = name.strip()

        if click_through_lookback_window_days is not None:
            action.click_through_lookback_window_days = int(click_through_lookback_window_days)
            op.update_mask.paths.append("click_through_lookback_window_days")
            updated["click_through_lookback_window_days"] = int(click_through_lookback_window_days)

        if view_through_lookback_window_days is not None:
            action.view_through_lookback_window_days = int(view_through_lookback_window_days)
            op.update_mask.paths.append("view_through_lookback_window_days")
            updated["view_through_lookback_window_days"] = int(view_through_lookback_window_days)

        if counting_type is not None:
            action.counting_type = _require_enum(client, "ConversionActionCountingTypeEnum", counting_type, "counting_type")
            op.update_mask.paths.append("counting_type")
            updated["counting_type"] = counting_type.strip().upper()

        if attribution_model is not None:
            action.attribution_model_settings.attribution_model = _require_enum(
                client, "AttributionModelEnum", attribution_model, "attribution_model"
            )
            op.update_mask.paths.append("attribution_model_settings.attribution_model")
            updated["attribution_model"] = attribution_model.strip().upper()

        if default_value is not None:
            action.value_settings.default_value = float(default_value)
            op.update_mask.paths.append("value_settings.default_value")
            updated["default_value"] = float(default_value)

        if always_use_default_value is not None:
            action.value_settings.always_use_default_value = bool(always_use_default_value)
            op.update_mask.paths.append("value_settings.always_use_default_value")
            updated["always_use_default_value"] = bool(always_use_default_value)

        if default_currency_code is not None:
            action.value_settings.default_currency_code = default_currency_code.strip().upper()
            op.update_mask.paths.append("value_settings.default_currency_code")
            updated["default_currency_code"] = default_currency_code.strip().upper()

        if not op.update_mask.paths:
            raise ValueError(
                "At least one parameter (primary_for_goal, status, name, click_through_lookback_window_days, "
                "view_through_lookback_window_days, counting_type, attribution_model, default_value, "
                "always_use_default_value, default_currency_code) must be provided for update."
            )

        if validate_only:
            response = conversion_action_service.mutate_conversion_actions(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = conversion_action_service.mutate_conversion_actions(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_conversion_action",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "updated_fields": updated,
            },
        )
    except ToolError:
        raise
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_conversion_goal(
    customer_id: str,
    category: str,
    origin: str,
    biddable: bool,
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Turns a conversion goal (category + origin) on or off for bidding, for the whole account or one campaign.

    A goal groups every conversion action with the same category and origin (e.g. DOWNLOAD + APP).
    biddable=False makes the whole goal secondary (observation only). Use this when the conversion action
    itself cannot be changed (e.g. Google-managed ANDROID_INSTALLS_ALL_OTHER_APPS returns MUTATE_NOT_ALLOWED).
    Read the current goals with search on customer_conversion_goal or campaign_conversion_goal.

    Args:
        customer_id: The Google Ads customer ID.
        category: Conversion category, e.g. 'DOWNLOAD', 'SUBMIT_LEAD_FORM', 'CONTACT', 'PURCHASE', 'PAGE_VIEW'.
        origin: Conversion origin, e.g. 'WEBSITE', 'APP', 'CALL_FROM_ADS', 'STORE', 'YOUTUBE_HOSTED', 'GOOGLE_HOSTED'.
        biddable: True uses the goal for bidding (primary); False makes it observation only (secondary).
        campaign_id: Optional campaign ID. If given, changes only that campaign's goal; otherwise the account default.
        validate_only: If True, only validates without applying changes.

    Returns:
        Dict with success status and the updated goal resource name.
    """
    cid = clean_customer_id(customer_id)
    try:
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        category_name = _require_enum(client, "ConversionActionCategoryEnum", category, "category").name
        origin_name = _require_enum(client, "ConversionOriginEnum", origin, "origin").name

        if campaign_id is not None:
            clean_campaign_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
            resource_name = f"customers/{cid}/campaignConversionGoals/{clean_campaign_id}~{category_name}~{origin_name}"
            service = utils.get_googleads_service("CampaignConversionGoalService", customer_id=cid)
            op = utils.get_googleads_type("CampaignConversionGoalOperation", customer_id=cid)
        else:
            resource_name = f"customers/{cid}/customerConversionGoals/{category_name}~{origin_name}"
            service = utils.get_googleads_service("CustomerConversionGoalService", customer_id=cid)
            op = utils.get_googleads_type("CustomerConversionGoalOperation", customer_id=cid)

        goal = op.update
        goal.resource_name = resource_name
        goal.biddable = bool(biddable)
        op.update_mask.paths.append("biddable")

        request = {"customer_id": cid, "operations": [op], "validate_only": validate_only}
        if campaign_id is not None:
            response = service.mutate_campaign_conversion_goals(request=request)
        else:
            response = service.mutate_customer_conversion_goals(request=request)

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_conversion_goal",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "level": "campaign" if campaign_id is not None else "account",
                "biddable": bool(biddable),
            },
        )
    except ToolError:
        raise
    except Exception as ex:
        raise handle_googleads_exception(ex)

