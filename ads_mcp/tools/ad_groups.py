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

"""Tools for managing Ad Groups in Google Ads."""

from typing import Any, Dict, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    parse_money_to_micros,
    micros_to_currency,
    handle_googleads_exception,
    format_mutate_response,
)


@mcp.tool()
def create_ad_group(
    customer_id: str,
    campaign_id: Union[str, int],
    name: str,
    status: str = "ENABLED",
    ad_group_type: str = "SEARCH_STANDARD",
    cpc_bid: Optional[Union[float, int, str]] = None,
    target_cpa: Optional[Union[float, int, str]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a new Ad Group under a specific campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or full resource name.
        name: Name of the ad group.
        status: Initial status ('ENABLED' or 'PAUSED', default 'ENABLED').
        ad_group_type: Type of ad group ('SEARCH_STANDARD', 'DISPLAY_STANDARD', etc.).
        cpc_bid: Default maximum CPC bid in currency units (e.g. 2.50). Converted to micros.
        target_cpa: Target CPA at ad group level in currency units (optional).
        validate_only: If True, only validates without creating.

    Returns:
        Dict with status and resource name of the created ad group.
    """
    cid = clean_customer_id(customer_id)
    
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_resource_name = clean_c_id
    else:
        campaign_resource_name = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        ad_group_service = utils.get_googleads_service("AdGroupService", customer_id=cid)
        ad_group_op = utils.get_googleads_type("AdGroupOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        ad_group = ad_group_op.create
        ad_group.name = name
        ad_group.campaign = campaign_resource_name

        # Type
        type_enum = getattr(
            client.enums.AdGroupTypeEnum.AdGroupType,
            ad_group_type.upper(),
            client.enums.AdGroupTypeEnum.AdGroupType.SEARCH_STANDARD,
        )
        ad_group.type_ = type_enum

        # Status
        status_enum = getattr(
            client.enums.AdGroupStatusEnum.AdGroupStatus,
            status.upper(),
            client.enums.AdGroupStatusEnum.AdGroupStatus.ENABLED,
        )
        ad_group.status = status_enum

        # Bids
        if cpc_bid is not None:
            ad_group.cpc_bid_micros = parse_money_to_micros(cpc_bid)
        if target_cpa is not None:
            ad_group.target_cpa_micros = parse_money_to_micros(target_cpa)

        response = ad_group_service.mutate_ad_groups(
            customer_id=cid,
            operations=[ad_group_op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroups/dry-run"}]
        return format_mutate_response(
            action="create_ad_group",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_resource_name,
                "name": name,
                "status": status.upper(),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_ad_group_status(
    customer_id: str,
    ad_group_id: Union[str, int],
    status: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the status of an ad group (PAUSED, ENABLED, or REMOVED).

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        status: New status ('PAUSED', 'ENABLED', or 'REMOVED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated details.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        resource_name = clean_ag_id
    else:
        resource_name = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        ad_group_service = utils.get_googleads_service("AdGroupService", customer_id=cid)
        ad_group_op = utils.get_googleads_type("AdGroupOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        status_enum = getattr(
            client.enums.AdGroupStatusEnum.AdGroupStatus,
            status.upper(),
            None,
        )
        if not status_enum:
            raise ValueError(f"Invalid ad group status: '{status}'. Choose PAUSED, ENABLED, or REMOVED.")

        ad_group = ad_group_op.update
        ad_group.resource_name = resource_name
        ad_group.status = status_enum
        ad_group_op.update_mask.paths.append("status")

        response = ad_group_service.mutate_ad_groups(
            customer_id=cid,
            operations=[ad_group_op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_ad_group_status",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "new_status": status.upper(),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_ad_group_cpc_bid(
    customer_id: str,
    ad_group_id: Union[str, int],
    cpc_bid: Union[float, int, str],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the default maximum CPC bid of an ad group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        cpc_bid: New max CPC bid in currency units (e.g. 3.50). Converted to micros.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated bid details.
    """
    cid = clean_customer_id(customer_id)
    cpc_micros = parse_money_to_micros(cpc_bid)
    
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        resource_name = clean_ag_id
    else:
        resource_name = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        ad_group_service = utils.get_googleads_service("AdGroupService", customer_id=cid)
        ad_group_op = utils.get_googleads_type("AdGroupOperation", customer_id=cid)

        ad_group = ad_group_op.update
        ad_group.resource_name = resource_name
        ad_group.cpc_bid_micros = cpc_micros
        ad_group_op.update_mask.paths.append("cpc_bid_micros")

        response = ad_group_service.mutate_ad_groups(
            customer_id=cid,
            operations=[ad_group_op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_ad_group_cpc_bid",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "new_cpc_bid": micros_to_currency(cpc_micros),
                "new_cpc_bid_micros": cpc_micros,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_ad_group_name(
    customer_id: str,
    ad_group_id: Union[str, int],
    name: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Renames an existing ad group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        name: The new ad group name.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated details.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        resource_name = clean_ag_id
    else:
        resource_name = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        ad_group_service = utils.get_googleads_service("AdGroupService", customer_id=cid)
        ad_group_op = utils.get_googleads_type("AdGroupOperation", customer_id=cid)

        ad_group = ad_group_op.update
        ad_group.resource_name = resource_name
        ad_group.name = name
        ad_group_op.update_mask.paths.append("name")

        response = ad_group_service.mutate_ad_groups(
            customer_id=cid,
            operations=[ad_group_op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_ad_group_name",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "new_name": name,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)
