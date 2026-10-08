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


@mcp.tool()
def add_campaign_proximity_target(
    customer_id: str,
    campaign_id: Union[str, int],
    latitude: float,
    longitude: float,
    radius: float,
    radius_units: str = "KILOMETERS",
    street_address: Optional[str] = None,
    city_name: Optional[str] = None,
    postal_code: Optional[str] = None,
    negative: bool = False,
    bid_modifier: Optional[float] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds a proximity (pin radius by coordinates) location target to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        latitude: Latitude in degrees (e.g. -23.55052).
        longitude: Longitude in degrees (e.g. -46.633308).
        radius: Radius distance (e.g. 5.0, 10.0, 25.0).
        radius_units: 'KILOMETERS' (default) or 'MILES'.
        street_address: Optional street address for reference.
        city_name: Optional city name for reference.
        postal_code: Optional postal code (CEP).
        negative: If True, excludes this radius; if False (default), includes/targets it.
        bid_modifier: Optional bid modifier (e.g. 1.2 for +20%). Only valid for positive targeting.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created proximity criterion resource name.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        criterion = op.create
        criterion.campaign = campaign_rn
        criterion.negative = negative

        # Micro-degrees conversion (1 degree = 1,000,000 micro-degrees)
        criterion.proximity.geo_point.latitude_in_micro_degrees = int(float(latitude) * 1_000_000)
        criterion.proximity.geo_point.longitude_in_micro_degrees = int(float(longitude) * 1_000_000)
        criterion.proximity.radius = float(radius)

        units_upper = radius_units.upper().strip()
        units_enum = getattr(
            get_enum_class(client, "ProximityRadiusUnitsEnum"),
            units_upper,
            get_enum_value(client, "ProximityRadiusUnitsEnum", "KILOMETERS"),
        )
        criterion.proximity.radius_units = units_enum

        if street_address:
            criterion.proximity.address.street_address = street_address
        if city_name:
            criterion.proximity.address.city_name = city_name
        if postal_code:
            criterion.proximity.address.postal_code = postal_code

        if bid_modifier is not None and not negative:
            criterion.bid_modifier = float(bid_modifier)

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

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignCriteria/dry-run"}]
        return format_mutate_response(
            action="add_campaign_proximity_target",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "latitude": latitude,
                "longitude": longitude,
                "radius": radius,
                "radius_units": units_upper,
                "negative": negative,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def add_campaign_languages(
    customer_id: str,
    campaign_id: Union[str, int],
    languages: List[Union[str, int]],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds language targeting to a campaign.

    Common language codes:
    - 'pt' or 'portuguese' -> 1014
    - 'en' or 'english'    -> 1000
    - 'es' or 'spanish'    -> 1003
    - 'fr' or 'french'     -> 1002
    - 'de' or 'german'     -> 1001
    - 'it' or 'italian'    -> 1004
    Direct integer constant IDs are also accepted.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        languages: List of language codes ('pt', 'en', 'es') or criterion IDs (1014, 1000).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created language criteria resource names.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    lang_map = {
        "pt": 1014,
        "por": 1014,
        "portuguese": 1014,
        "portugues": 1014,
        "en": 1000,
        "eng": 1000,
        "english": 1000,
        "ingles": 1000,
        "es": 1003,
        "spa": 1003,
        "spanish": 1003,
        "espanhol": 1003,
        "fr": 1002,
        "french": 1002,
        "frances": 1002,
        "de": 1001,
        "german": 1001,
        "alemao": 1001,
        "it": 1004,
        "italian": 1004,
        "italiano": 1004,
    }

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        operations = []

        for lang in languages:
            clean_l = str(lang).strip().lower()
            if clean_l.startswith("languageconstants/"):
                lang_id = clean_l.split("/")[-1]
            elif clean_l in lang_map:
                lang_id = lang_map[clean_l]
            elif clean_l.isdigit():
                lang_id = int(clean_l)
            else:
                raise ValueError(f"Unrecognized language '{lang}'. Pass standard codes (e.g. 'pt', 'en', 'es') or constant IDs (1014, 1000).")

            op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.campaign = campaign_rn
            criterion.language.language_constant = f"languageConstants/{lang_id}"
            operations.append(op)

        if not operations:
            raise ValueError("No languages provided.")

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
            action="add_campaign_languages",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "languages": [str(l) for l in languages],
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_campaign_criterion_bid_modifier(
    customer_id: str,
    campaign_id: Union[str, int],
    criterion_id: Union[str, int],
    bid_modifier: float,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the bid modifier on an existing campaign criterion (e.g. location/city or device).

    Avoids duplicate criterion errors when adjusting bid modifiers on locations already added.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID.
        criterion_id: The criterion ID (e.g. 20088 for Bahia, or the full resource ID).
        bid_modifier: The new bid modifier (e.g. 0.7 for -30%, 1.2 for +20%, 1.0 for neutral).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated criterion details.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
    clean_crit_id = str(criterion_id).replace("-", "").strip()
    if "~" in clean_crit_id:
        clean_crit_id = clean_crit_id.split("~")[-1]

    criterion_rn = f"customers/{cid}/campaignCriteria/{clean_c_id}~{clean_crit_id}"

    try:
        campaign_criterion_service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)

        criterion = op.update
        criterion.resource_name = criterion_rn
        criterion.bid_modifier = float(bid_modifier)
        op.update_mask.paths.append("bid_modifier")

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

        results = response.results if not validate_only else [{"resource_name": criterion_rn}]
        return format_mutate_response(
            action="update_campaign_criterion_bid_modifier",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign_id": clean_c_id,
                "criterion_id": clean_crit_id,
                "new_bid_modifier": float(bid_modifier),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def add_placement_exclusion(
    customer_id: str,
    placement_urls: List[str],
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Excludes specific placements (websites like 'glance.com', mobile apps, or YouTube channels).

    Can be applied at campaign level (preferred for PMax/Search) or customer account level.

    Args:
        customer_id: The Google Ads customer ID.
        placement_urls: List of placement URLs, app package names, or YouTube channels to exclude (e.g. ['glance.com', 'youtube.com/channel/...']).
        campaign_id: Optional campaign ID to exclude on a specific campaign. If omitted, excludes at customer account level.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created negative placement criteria.
    """
    cid = clean_customer_id(customer_id)

    try:
        if campaign_id:
            clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
            campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"
            service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
            operations = []

            for url in placement_urls:
                clean_url = str(url).strip()
                op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
                crit = op.create
                crit.campaign = campaign_rn
                crit.negative = True
                crit.placement.url = clean_url
                operations.append(op)

            if validate_only:
                response = service.mutate_campaign_criteria(
                    request={
                        "customer_id": cid,
                        "operations": operations,
                        "validate_only": True,
                    }
                )
            else:
                response = service.mutate_campaign_criteria(
                    customer_id=cid,
                    operations=operations,
                )
        else:
            service = utils.get_googleads_service("CustomerNegativeCriterionService", customer_id=cid)
            operations = []

            for url in placement_urls:
                clean_url = str(url).strip()
                op = utils.get_googleads_type("CustomerNegativeCriterionOperation", customer_id=cid)
                crit = op.create
                crit.placement.url = clean_url
                operations.append(op)

            if validate_only:
                response = service.mutate_customer_negative_criteria(
                    request={
                        "customer_id": cid,
                        "operations": operations,
                        "validate_only": True,
                    }
                )
            else:
                response = service.mutate_customer_negative_criteria(
                    customer_id=cid,
                    operations=operations,
                )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/negativePlacements/dry-run"} for _ in placement_urls]
        return format_mutate_response(
            action="add_placement_exclusion",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign_id": campaign_id,
                "placements_excluded": [str(u) for u in placement_urls],
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def add_ad_group_demographic_exclusion(
    customer_id: str,
    ad_group_id: Union[str, int],
    demographic_type: str,
    value: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Excludes a demographic segment (gender, age range, parental status) at the Ad Group level.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        demographic_type: 'GENDER', 'AGE_RANGE', 'PARENTAL_STATUS', or 'INCOME_RANGE'.
        value: The enum value to exclude:
               - For GENDER: 'MALE', 'FEMALE', 'UNDETERMINED'
               - For AGE_RANGE: 'AGE_RANGE_18_24', 'AGE_RANGE_25_34', 'AGE_RANGE_35_44', 'AGE_RANGE_45_54', 'AGE_RANGE_55_64', 'AGE_RANGE_65_UP', 'AGE_RANGE_UNDETERMINED'
               - For PARENTAL_STATUS: 'PARENT', 'NOT_A_PARENT', 'UNDETERMINED'
               - For INCOME_RANGE: 'INCOME_RANGE_0_50', 'INCOME_RANGE_50_60', 'INCOME_RANGE_60_70', 'INCOME_RANGE_70_80', 'INCOME_RANGE_80_90', 'INCOME_RANGE_90_UP', 'INCOME_RANGE_UNDETERMINED'
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created negative demographic criterion.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
    ad_group_rn = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)

        crit = op.create
        crit.ad_group = ad_group_rn
        crit.negative = True

        dt_upper = demographic_type.upper().strip()
        val_upper = value.upper().strip()

        if dt_upper == "GENDER":
            crit.gender.type = get_enum_value(client, "GenderTypeEnum", val_upper)
        elif dt_upper == "AGE_RANGE":
            crit.age_range.type = get_enum_value(client, "AgeRangeTypeEnum", val_upper)
        elif dt_upper == "PARENTAL_STATUS":
            crit.parental_status.type = get_enum_value(client, "ParentalStatusTypeEnum", val_upper)
        elif dt_upper == "INCOME_RANGE":
            crit.income_range.type = get_enum_value(client, "IncomeRangeTypeEnum", val_upper)
        else:
            raise ValueError(f"Invalid demographic_type: '{demographic_type}'. Must be GENDER, AGE_RANGE, PARENTAL_STATUS, or INCOME_RANGE.")

        if validate_only:
            response = service.mutate_ad_group_criteria(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = service.mutate_ad_group_criteria(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroupCriteria/dry-run"}]
        return format_mutate_response(
            action="add_ad_group_demographic_exclusion",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group": ad_group_rn,
                "demographic_type": dt_upper,
                "value": val_upper,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def add_campaign_audience_criterion(
    customer_id: str,
    campaign_id: Union[str, int],
    user_interest_id: Optional[Union[int, str]] = None,
    user_list_id: Optional[Union[int, str]] = None,
    negative: bool = False,
    bid_modifier: Optional[float] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds or excludes an audience segment (user interest / in-market or remarketing user list) to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID.
        user_interest_id: Category ID for User Interest (Affinity or In-Market segment, e.g. 92901 for Shoppers).
        user_list_id: ID for Remarketing User List (Customer Match or website visitors).
        negative: If True, excludes this audience from the campaign; if False (default), targets/observes it.
        bid_modifier: Optional bid modifier (e.g. 1.2 for +20%). Only valid when negative=False.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created audience criterion.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
    campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    if not user_interest_id and not user_list_id:
        raise ValueError("Must specify either user_interest_id or user_list_id.")

    try:
        service = utils.get_googleads_service("CampaignCriterionService", customer_id=cid)
        op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)

        crit = op.create
        crit.campaign = campaign_rn
        crit.negative = negative

        if user_interest_id:
            clean_ui = str(user_interest_id).strip().removeprefix(f"customers/{cid}/userInterests/")
            crit.user_interest.user_interest_category = f"customers/{cid}/userInterests/{clean_ui}"

        if user_list_id:
            clean_ul = str(user_list_id).strip().removeprefix(f"customers/{cid}/userLists/")
            crit.user_list.user_list = f"customers/{cid}/userLists/{clean_ul}"

        if bid_modifier is not None and not negative:
            crit.bid_modifier = float(bid_modifier)

        if validate_only:
            response = service.mutate_campaign_criteria(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = service.mutate_campaign_criteria(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignCriteria/dry-run"}]
        return format_mutate_response(
            action="add_campaign_audience_criterion",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "negative": negative,
                "user_interest_id": user_interest_id,
                "user_list_id": user_list_id,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


