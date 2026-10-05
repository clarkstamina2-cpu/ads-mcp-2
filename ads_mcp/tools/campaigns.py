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

"""Tools for managing Campaigns in Google Ads (Search, PMax, Display, Video, Demand Gen, Shopping)."""

from typing import Any, Dict, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    parse_money_to_micros,
    micros_to_currency,
    handle_googleads_exception,
    format_mutate_response,
    get_enum_class,
    get_enum_value,
)


@mcp.tool()
def create_campaign(
    customer_id: str,
    name: str,
    budget_id: Union[str, int],
    advertising_channel_type: str = "SEARCH",
    status: str = "PAUSED",
    bidding_strategy_type: str = "MAXIMIZE_CONVERSIONS",
    target_cpa: Optional[Union[float, int, str]] = None,
    target_roas: Optional[float] = None,
    cpc_bid_ceiling: Optional[Union[float, int, str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    target_google_search: bool = True,
    target_search_network: bool = True,
    target_content_network: bool = False,
    target_partner_search_network: bool = False,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a new campaign in Google Ads.

    Supports SEARCH, PERFORMANCE_MAX, DISPLAY, VIDEO, DEMAND_GEN, and SHOPPING campaign types.

    Args:
        customer_id: The Google Ads customer ID.
        name: Name of the campaign.
        budget_id: The campaign budget ID or resource name ('customers/.../campaignBudgets/...').
        advertising_channel_type: Channel type ('SEARCH', 'PERFORMANCE_MAX', 'DISPLAY', 'VIDEO', 'DEMAND_GEN', 'SHOPPING').
        status: Initial status ('PAUSED' or 'ENABLED', default 'PAUSED').
        bidding_strategy_type: Strategy ('MAXIMIZE_CONVERSIONS', 'MAXIMIZE_CONVERSION_VALUE', 'TARGET_CPA', 'TARGET_ROAS', 'MANUAL_CPC', 'TARGET_SPEND').
        target_cpa: Target CPA in currency units (e.g. 25.00 for $25/R$25).
        target_roas: Target ROAS (e.g. 3.5 for 350%).
        cpc_bid_ceiling: Maximum CPC bid ceiling in currency units for Maximize Clicks / Target Spend.
        start_date: Start date in format YYYY-MM-DD (e.g. '2026-10-01').
        end_date: End date in format YYYY-MM-DD (e.g. '2026-12-31').
        target_google_search: Target Google Search network (default True).
        target_search_network: Target Search Partners network (default True).
        target_content_network: Target Google Display Network expansion (default False).
        target_partner_search_network: Target partner search network (default False).
        validate_only: If True, only validates the request without executing.

    Returns:
        Dict with status and resource name of the created campaign.
    """
    cid = clean_customer_id(customer_id)
    
    clean_b_id = str(budget_id).strip()
    if clean_b_id.startswith("customers/"):
        budget_resource_name = clean_b_id
    else:
        budget_resource_name = f"customers/{cid}/campaignBudgets/{clean_b_id}"

    try:
        campaign_service = utils.get_googleads_service("CampaignService", customer_id=cid)
        campaign_op = utils.get_googleads_type("CampaignOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        campaign = campaign_op.create
        campaign.name = name
        campaign.campaign_budget = budget_resource_name

        # Channel type
        channel_enum = getattr(
            get_enum_class(client, "AdvertisingChannelTypeEnum"),
            advertising_channel_type.upper(),
            get_enum_value(client, "AdvertisingChannelTypeEnum", "SEARCH"),
        )
        campaign.advertising_channel_type = channel_enum

        # Status
        status_enum = getattr(
            get_enum_class(client, "CampaignStatusEnum"),
            status.upper(),
            get_enum_value(client, "CampaignStatusEnum", "PAUSED"),
        )
        campaign.status = status_enum

        # Network Settings (only applicable for SEARCH / DISPLAY)
        if advertising_channel_type.upper() in ("SEARCH", "DISPLAY"):
            campaign.network_settings.target_google_search = target_google_search
            campaign.network_settings.target_search_network = target_search_network
            campaign.network_settings.target_content_network = target_content_network
            campaign.network_settings.target_partner_search_network = target_partner_search_network

        # Dates
        if start_date:
            campaign.start_date = start_date.replace("-", "")
        if end_date:
            campaign.end_date = end_date.replace("-", "")

        # Bidding Strategy
        strat_upper = bidding_strategy_type.upper()
        if strat_upper == "TARGET_CPA" or (strat_upper == "MAXIMIZE_CONVERSIONS" and target_cpa is not None):
            cpa_micros = parse_money_to_micros(target_cpa)
            if strat_upper == "TARGET_CPA":
                campaign.target_cpa.target_cpa_micros = cpa_micros
            else:
                campaign.maximize_conversions.target_cpa_micros = cpa_micros
        elif strat_upper == "TARGET_ROAS" or (strat_upper == "MAXIMIZE_CONVERSION_VALUE" and target_roas is not None):
            if strat_upper == "TARGET_ROAS":
                campaign.target_roas.target_roas = float(target_roas)
            else:
                campaign.maximize_conversion_value.target_roas = float(target_roas)
        elif strat_upper == "MAXIMIZE_CONVERSIONS":
            campaign.maximize_conversions._pb.SetInParent()
        elif strat_upper == "MAXIMIZE_CONVERSION_VALUE":
            campaign.maximize_conversion_value._pb.SetInParent()
        elif strat_upper == "MANUAL_CPC":
            campaign.manual_cpc.enhanced_cpc_enabled = True
        elif strat_upper in ("TARGET_SPEND", "MAXIMIZE_CLICKS"):
            if cpc_bid_ceiling:
                campaign.target_spend.cpc_bid_ceiling_micros = parse_money_to_micros(cpc_bid_ceiling)
            else:
                campaign.target_spend._pb.SetInParent()

        if validate_only:
            response = campaign_service.mutate_campaigns(
                request={
                    "customer_id": cid,
                    "operations": [campaign_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_service.mutate_campaigns(
                customer_id=cid,
                operations=[campaign_op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaigns/dry-run"}]
        return format_mutate_response(
            action="create_campaign",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "name": name,
                "advertising_channel_type": advertising_channel_type,
                "bidding_strategy": bidding_strategy_type,
                "status": status,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_campaign_status(
    customer_id: str,
    campaign_id: Union[str, int],
    status: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the status of a campaign (PAUSED, ENABLED, or REMOVED).

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        status: New status ('PAUSED', 'ENABLED', or 'REMOVED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated campaign details.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        resource_name = clean_c_id
    else:
        resource_name = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_service = utils.get_googleads_service("CampaignService", customer_id=cid)
        campaign_op = utils.get_googleads_type("CampaignOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        status_enum = getattr(
            get_enum_class(client, "CampaignStatusEnum"),
            status.upper(),
            None,
        )
        if not status_enum:
            raise ValueError(f"Invalid campaign status: '{status}'. Choose PAUSED, ENABLED, or REMOVED.")

        campaign = campaign_op.update
        campaign.resource_name = resource_name
        campaign.status = status_enum
        campaign_op.update_mask.paths.append("status")

        if validate_only:
            response = campaign_service.mutate_campaigns(
                request={
                    "customer_id": cid,
                    "operations": [campaign_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_service.mutate_campaigns(
                customer_id=cid,
                operations=[campaign_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_campaign_status",
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
def update_campaign_bidding_strategy(
    customer_id: str,
    campaign_id: Union[str, int],
    bidding_strategy_type: str,
    target_cpa: Optional[Union[float, int, str]] = None,
    target_roas: Optional[float] = None,
    cpc_bid_ceiling: Optional[Union[float, int, str]] = None,
    enhanced_cpc_enabled: Optional[bool] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the bidding strategy and targets of an existing campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        bidding_strategy_type: 'MAXIMIZE_CONVERSIONS', 'MAXIMIZE_CONVERSION_VALUE', 'TARGET_CPA', 'TARGET_ROAS', 'MANUAL_CPC', 'TARGET_SPEND'.
        target_cpa: Target CPA in currency units (e.g. 30.00).
        target_roas: Target ROAS (e.g. 4.0 for 400%).
        cpc_bid_ceiling: Maximum CPC bid ceiling in currency units for Maximize Clicks / Target Spend.
        enhanced_cpc_enabled: Whether to enable eCPC when using MANUAL_CPC.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated bidding strategy details.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        resource_name = clean_c_id
    else:
        resource_name = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_service = utils.get_googleads_service("CampaignService", customer_id=cid)
        campaign_op = utils.get_googleads_type("CampaignOperation", customer_id=cid)
        campaign = campaign_op.update
        campaign.resource_name = resource_name

        strat_upper = bidding_strategy_type.upper()
        if strat_upper == "TARGET_CPA" or (strat_upper == "MAXIMIZE_CONVERSIONS" and target_cpa is not None):
            cpa_micros = parse_money_to_micros(target_cpa)
            if strat_upper == "TARGET_CPA":
                campaign.target_cpa.target_cpa_micros = cpa_micros
                campaign_op.update_mask.paths.append("target_cpa.target_cpa_micros")
            else:
                campaign.maximize_conversions.target_cpa_micros = cpa_micros
                campaign_op.update_mask.paths.append("maximize_conversions.target_cpa_micros")
        elif strat_upper == "TARGET_ROAS" or (strat_upper == "MAXIMIZE_CONVERSION_VALUE" and target_roas is not None):
            if strat_upper == "TARGET_ROAS":
                campaign.target_roas.target_roas = float(target_roas)
                campaign_op.update_mask.paths.append("target_roas.target_roas")
            else:
                campaign.maximize_conversion_value.target_roas = float(target_roas)
                campaign_op.update_mask.paths.append("maximize_conversion_value.target_roas")
        elif strat_upper == "MAXIMIZE_CONVERSIONS":
            campaign.maximize_conversions._pb.SetInParent()
            campaign_op.update_mask.paths.append("maximize_conversions")
        elif strat_upper == "MAXIMIZE_CONVERSION_VALUE":
            campaign.maximize_conversion_value._pb.SetInParent()
            campaign_op.update_mask.paths.append("maximize_conversion_value")
        elif strat_upper == "MANUAL_CPC":
            if enhanced_cpc_enabled is not None:
                campaign.manual_cpc.enhanced_cpc_enabled = enhanced_cpc_enabled
            else:
                campaign.manual_cpc._pb.SetInParent()
            campaign_op.update_mask.paths.append("manual_cpc")
        elif strat_upper in ("TARGET_SPEND", "MAXIMIZE_CLICKS"):
            if cpc_bid_ceiling is not None:
                campaign.target_spend.cpc_bid_ceiling_micros = parse_money_to_micros(cpc_bid_ceiling)
                campaign_op.update_mask.paths.append("target_spend.cpc_bid_ceiling_micros")
            else:
                campaign.target_spend._pb.SetInParent()
                campaign_op.update_mask.paths.append("target_spend")

        if validate_only:
            response = campaign_service.mutate_campaigns(
                request={
                    "customer_id": cid,
                    "operations": [campaign_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_service.mutate_campaigns(
                customer_id=cid,
                operations=[campaign_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_campaign_bidding_strategy",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "strategy": bidding_strategy_type,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_campaign_dates(
    customer_id: str,
    campaign_id: Union[str, int],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the start and/or end dates of a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        start_date: Start date formatted as YYYY-MM-DD.
        end_date: End date formatted as YYYY-MM-DD.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated date details.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        resource_name = clean_c_id
    else:
        resource_name = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_service = utils.get_googleads_service("CampaignService", customer_id=cid)
        campaign_op = utils.get_googleads_type("CampaignOperation", customer_id=cid)
        campaign = campaign_op.update
        campaign.resource_name = resource_name

        if start_date:
            campaign.start_date = start_date.replace("-", "")
            campaign_op.update_mask.paths.append("start_date")
        if end_date:
            campaign.end_date = end_date.replace("-", "")
            campaign_op.update_mask.paths.append("end_date")

        if validate_only:
            response = campaign_service.mutate_campaigns(
                request={
                    "customer_id": cid,
                    "operations": [campaign_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_service.mutate_campaigns(
                customer_id=cid,
                operations=[campaign_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_campaign_dates",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_campaign_name(
    customer_id: str,
    campaign_id: Union[str, int],
    name: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Renames an existing campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        name: The new campaign name.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated name details.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        resource_name = clean_c_id
    else:
        resource_name = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_service = utils.get_googleads_service("CampaignService", customer_id=cid)
        campaign_op = utils.get_googleads_type("CampaignOperation", customer_id=cid)
        campaign = campaign_op.update
        campaign.resource_name = resource_name
        campaign.name = name
        campaign_op.update_mask.paths.append("name")

        if validate_only:
            response = campaign_service.mutate_campaigns(
                request={
                    "customer_id": cid,
                    "operations": [campaign_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_service.mutate_campaigns(
                customer_id=cid,
                operations=[campaign_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_campaign_name",
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
