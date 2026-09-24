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
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    format_mutate_response,
)


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
