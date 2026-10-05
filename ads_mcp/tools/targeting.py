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

"""Tools for managing Campaign Targeting (Geo/Location, Ad Schedule, Device Modifiers) in Google Ads."""

from typing import Any, Dict, List, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    format_mutate_response,
    get_enum_class,
    get_enum_value,
)


@mcp.tool()
def add_campaign_geo_targets(
    customer_id: str,
    campaign_id: Union[str, int],
    geo_target_constant_ids: List[Union[int, str]],
    negative: bool = False,
    bid_modifier: Optional[float] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds geographic location targets (inclusions or exclusions) to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        geo_target_constant_ids: List of Geo Target Constant IDs (e.g. [2076] for Brazil, [1001773] for São Paulo City, [21008] for Rio de Janeiro State).
        negative: If True, excludes these locations; if False (default), targets/includes them.
        bid_modifier: Optional bid modifier (e.g. 1.2 for +20%, 0.8 for -20%). Only valid for positive targeting.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created criterion resource names.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        operations = []

        for geo_id in geo_target_constant_ids:
            clean_geo = str(geo_id).strip().removeprefix("geoTargetConstants/")
            op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.campaign = campaign_rn
            criterion.location.geo_target_constant = f"geoTargetConstants/{clean_geo}"
            criterion.negative = negative

            if bid_modifier is not None and not negative:
                criterion.bid_modifier = float(bid_modifier)

            operations.append(op)

        if not operations:
            raise ValueError("No geo target IDs provided.")

        if validate_only:
            response = campaign_criterion_service.mutate_campaign_criteria(
                request={
                    "customer_id": cid,
                    "operations": operations,
                    "validate_only": True,
                }
            )
        else:
            response = campaign_criterion_service.mutate_campaign_criteria(
                customer_id=cid,
                operations=operations,
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignCriteria/dry-run"} for _ in operations]
        return format_mutate_response(
            action="add_campaign_geo_targets",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "negative": negative,
                "geo_ids": [str(g) for g in geo_target_constant_ids],
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def remove_campaign_criterion(
    customer_id: str,
    campaign_id: Union[str, int],
    criterion_id: Union[str, int],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Removes a campaign-level criterion (e.g. geo target, ad schedule, device modifier, or negative keyword).

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID.
        criterion_id: The criterion ID to remove.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
    clean_crit_id = str(criterion_id).replace("-", "").strip()
    if "~" in clean_crit_id:
        clean_crit_id = clean_crit_id.split("~")[-1]

    resource_name = f"customers/{cid}/campaignCriteria/{clean_c_id}~{clean_crit_id}"

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
        op.remove = resource_name

        if validate_only:
            response = campaign_criterion_service.mutate_campaign_criteria(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_criterion_service.mutate_campaign_criteria(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="remove_campaign_criterion",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "removed_resource_name": resource_name,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def set_campaign_ad_schedule(
    customer_id: str,
    campaign_id: Union[str, int],
    schedules: List[Dict[str, Any]],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Sets Ad Schedule (dayparting) rules for a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        schedules: List of schedule dictionaries, each with:
                   - day_of_week: 'MONDAY', 'TUESDAY', 'WEDNESDAY', 'THURSDAY', 'FRIDAY', 'SATURDAY', or 'SUNDAY'.
                   - start_hour: Integer 0 to 23.
                   - start_minute: 'ZERO', 'FIFTEEN', 'THIRTY', or 'FORTY_FIVE' (default 'ZERO').
                   - end_hour: Integer 0 to 24.
                   - end_minute: 'ZERO', 'FIFTEEN', 'THIRTY', or 'FORTY_FIVE' (default 'ZERO').
                   - bid_modifier: Optional float (e.g. 1.2 for +20%, 0.8 for -20%).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and list of created ad schedule criteria.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        operations = []
        for s in schedules:
            op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.campaign = campaign_rn

            day_enum = getattr(
                get_enum_class(client, "DayOfWeekEnum"),
                s.get("day_of_week", "").upper(),
                None,
            )
            if not day_enum:
                raise ValueError(f"Invalid day_of_week: '{s.get('day_of_week')}'.")

            start_min_enum = getattr(
                get_enum_class(client, "MinuteOfHourEnum"),
                str(s.get("start_minute", "ZERO")).upper(),
                get_enum_value(client, "MinuteOfHourEnum", "ZERO"),
            )
            end_min_enum = getattr(
                get_enum_class(client, "MinuteOfHourEnum"),
                str(s.get("end_minute", "ZERO")).upper(),
                get_enum_value(client, "MinuteOfHourEnum", "ZERO"),
            )

            criterion.ad_schedule.day_of_week = day_enum
            criterion.ad_schedule.start_hour = int(s.get("start_hour", 0))
            criterion.ad_schedule.start_minute = start_min_enum
            criterion.ad_schedule.end_hour = int(s.get("end_hour", 24))
            criterion.ad_schedule.end_minute = end_min_enum

            if "bid_modifier" in s and s["bid_modifier"] is not None:
                criterion.bid_modifier = float(s["bid_modifier"])

            operations.append(op)

        if not operations:
            raise ValueError("No schedule items provided.")

        if validate_only:
            response = campaign_criterion_service.mutate_campaign_criteria(
                request={
                    "customer_id": cid,
                    "operations": operations,
                    "validate_only": True,
                }
            )
        else:
            response = campaign_criterion_service.mutate_campaign_criteria(
                customer_id=cid,
                operations=operations,
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignCriteria/dry-run"} for _ in operations]
        return format_mutate_response(
            action="set_campaign_ad_schedule",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "schedules_count": len(operations),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def set_campaign_device_bid_modifiers(
    customer_id: str,
    campaign_id: Union[str, int],
    desktop_modifier: Optional[float] = None,
    mobile_modifier: Optional[float] = None,
    tablet_modifier: Optional[float] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Sets bid modifiers for devices (Desktop, Mobile, Tablet) at campaign level.

    Values range from 0.0 (-100% disabled) to 10.0 (+900%).
    Examples: 1.0 = baseline (0%), 1.25 = +25%, 0.8 = -20%, 0.0 = -100% (disable traffic from device).

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        desktop_modifier: Bid modifier for DESKTOP (e.g. 1.2 or 0.0).
        mobile_modifier: Bid modifier for MOBILE (e.g. 1.1).
        tablet_modifier: Bid modifier for TABLET (e.g. 0.0 to disable tablets).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated device modifiers.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        bid_modifier_service = utils.get_googleads_service("CampaignBidModifierService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        operations = []
        device_configs = [
            ("DESKTOP", desktop_modifier),
            ("MOBILE", mobile_modifier),
            ("TABLET", tablet_modifier),
        ]

        for device_name, modifier in device_configs:
            if modifier is None:
                continue

            op = utils.get_googleads_type("CampaignBidModifierOperation", customer_id=cid)
            cbm = op.create
            cbm.campaign = campaign_rn
            device_enum = getattr(get_enum_class(client, "DeviceEnum"), device_name)
            cbm.device.type_ = device_enum
            cbm.bid_modifier = float(modifier)
            operations.append(op)

        if not operations:
            raise ValueError("At least one device modifier (desktop, mobile, or tablet) must be specified.")

        if validate_only:
            response = bid_modifier_service.mutate_campaign_bid_modifiers(
                request={
                    "customer_id": cid,
                    "operations": operations,
                    "validate_only": True,
                }
            )
        else:
            response = bid_modifier_service.mutate_campaign_bid_modifiers(
                customer_id=cid,
                operations=operations,
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignBidModifiers/dry-run"} for _ in operations]
        return format_mutate_response(
            action="set_campaign_device_bid_modifiers",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "desktop_modifier": desktop_modifier,
                "mobile_modifier": mobile_modifier,
                "tablet_modifier": tablet_modifier,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)
