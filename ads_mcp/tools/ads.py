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

"""Tools for managing Ads (Responsive Search Ads, PMax Asset Groups) in Google Ads."""

from typing import Any, Dict, List, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    format_mutate_response,
)


@mcp.tool()
def create_responsive_search_ad(
    customer_id: str,
    ad_group_id: Union[str, int],
    headlines: List[Union[str, Dict[str, Any]]],
    descriptions: List[Union[str, Dict[str, Any]]],
    final_urls: List[str],
    path1: Optional[str] = None,
    path2: Optional[str] = None,
    status: str = "ENABLED",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Responsive Search Ad (RSA) in an ad group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        headlines: List of 3 to 15 headlines. Can be strings (e.g. ['Compre Online', 'Melhor Preço'])
                   or dicts with pinning (e.g. [{'text': 'Marca Oficial', 'pinned_field': 'HEADLINE_1'}]).
        descriptions: List of 2 to 4 descriptions. Can be strings or dicts with pinning (e.g. [{'text': '...', 'pinned_field': 'DESCRIPTION_1'}]).
        final_urls: List of destination URLs (e.g. ['https://www.exemplo.com.br/produto']).
        path1: Optional display URL path 1 (up to 15 characters, e.g. 'calcados').
        path2: Optional display URL path 2 (up to 15 characters, e.g. 'oferta').
        status: Initial ad status ('ENABLED' or 'PAUSED', default 'ENABLED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created Ad Group Ad resource name.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        ad_group_rn = clean_ag_id
    else:
        ad_group_rn = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        ad_group_ad_service = utils.get_googleads_service("AdGroupAdService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupAdOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        ad_group_ad = op.create
        ad_group_ad.ad_group = ad_group_rn

        # Status
        status_enum = getattr(
            client.enums.AdGroupAdStatusEnum.AdGroupAdStatus,
            status.upper(),
            client.enums.AdGroupAdStatusEnum.AdGroupAdStatus.ENABLED,
        )
        ad_group_ad.status = status_enum

        # Final URLs
        ad_group_ad.ad.final_urls.extend(final_urls)

        # Paths
        if path1:
            ad_group_ad.ad.responsive_search_ad.path1 = path1[:15]
        if path2:
            ad_group_ad.ad.responsive_search_ad.path2 = path2[:15]

        # Headlines
        for h in headlines:
            headline_asset = utils.get_googleads_type("AdTextAsset", customer_id=cid)
            if isinstance(h, str):
                headline_asset.text = h[:30]
            elif isinstance(h, dict):
                headline_asset.text = str(h.get("text", ""))[:30]
                pin_str = h.get("pinned_field")
                if pin_str:
                    pin_enum = getattr(
                        client.enums.ServedAssetFieldTypeEnum.ServedAssetFieldType,
                        pin_str.upper(),
                        None,
                    )
                    if pin_enum:
                        headline_asset.pinned_field = pin_enum
            ad_group_ad.ad.responsive_search_ad.headlines.append(headline_asset)

        # Descriptions
        for d in descriptions:
            desc_asset = utils.get_googleads_type("AdTextAsset", customer_id=cid)
            if isinstance(d, str):
                desc_asset.text = d[:90]
            elif isinstance(d, dict):
                desc_asset.text = str(d.get("text", ""))[:90]
                pin_str = d.get("pinned_field")
                if pin_str:
                    pin_enum = getattr(
                        client.enums.ServedAssetFieldTypeEnum.ServedAssetFieldType,
                        pin_str.upper(),
                        None,
                    )
                    if pin_enum:
                        desc_asset.pinned_field = pin_enum
            ad_group_ad.ad.responsive_search_ad.descriptions.append(desc_asset)

        response = ad_group_ad_service.mutate_ad_group_ads(
            customer_id=cid,
            operations=[op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroupAds/dry-run"}]
        return format_mutate_response(
            action="create_responsive_search_ad",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group": ad_group_rn,
                "headlines_count": len(ad_group_ad.ad.responsive_search_ad.headlines),
                "descriptions_count": len(ad_group_ad.ad.responsive_search_ad.descriptions),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_ad_status(
    customer_id: str,
    ad_group_id: Union[str, int],
    ad_id: Union[str, int],
    status: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the status of an Ad (PAUSED, ENABLED, or REMOVED).

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID.
        ad_id: The ad ID.
        status: New status ('PAUSED', 'ENABLED', or 'REMOVED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and details.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
    clean_ad_id = str(ad_id).replace("-", "").strip()
    if "~" in clean_ad_id:
        clean_ad_id = clean_ad_id.split("~")[-1]

    resource_name = f"customers/{cid}/adGroupAds/{clean_ag_id}~{clean_ad_id}"

    try:
        ad_group_ad_service = utils.get_googleads_service("AdGroupAdService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupAdOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        enum_class = getattr(client.enums.AdGroupAdStatusEnum, "AdGroupAdStatus", client.enums.AdGroupAdStatusEnum)
        status_enum = getattr(enum_class, status.upper(), None)
        if not status_enum:
            raise ValueError(f"Invalid ad status: '{status}'. Choose PAUSED, ENABLED, or REMOVED.")

        ad_group_ad = op.update
        ad_group_ad.resource_name = resource_name
        ad_group_ad.status = status_enum
        op.update_mask.paths.append("status")

        request = utils.get_googleads_type("MutateAdGroupAdsRequest", customer_id=cid)
        request.customer_id = cid
        request.operations.append(op)
        request.validate_only = validate_only

        response = ad_group_ad_service.mutate_ad_group_ads(request=request)

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_ad_status",
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
def create_pmax_asset_group(
    customer_id: str,
    campaign_id: Union[str, int],
    name: str,
    final_urls: List[str],
    business_name: str,
    headlines: List[str],
    long_headlines: List[str],
    descriptions: List[str],
    call_to_action: Optional[str] = None,
    status: str = "ENABLED",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a basic Asset Group for Performance Max campaigns with text assets.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The Performance Max campaign ID or resource name.
        name: Name of the asset group.
        final_urls: Final destination URLs.
        business_name: Name of the business/brand (e.g. 'Stamina Digital').
        headlines: List of short headlines (up to 30 chars).
        long_headlines: List of long headlines (up to 90 chars).
        descriptions: List of descriptions (up to 90 chars).
        call_to_action: Optional Call To Action ('LEARN_MORE', 'SHOP_NOW', 'SIGN_UP', 'CONTACT_US', 'GET_QUOTE', etc.).
        status: Initial status ('ENABLED' or 'PAUSED', default 'ENABLED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset group resource name.
    """
    cid = clean_customer_id(customer_id)
    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    try:
        asset_group_service = utils.get_googleads_service("AssetGroupService", customer_id=cid)
        op = utils.get_googleads_type("AssetGroupOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        asset_group = op.create
        asset_group.campaign = campaign_rn
        asset_group.name = name
        asset_group.final_urls.extend(final_urls)

        status_enum = getattr(
            client.enums.AssetGroupStatusEnum.AssetGroupStatus,
            status.upper(),
            client.enums.AssetGroupStatusEnum.AssetGroupStatus.ENABLED,
        )
        asset_group.status = status_enum

        # Text assets directly or via AssetGroupAsset
        # We create the AssetGroup container first
        response = asset_group_service.mutate_asset_groups(
            customer_id=cid,
            operations=[op],
            validate_only=validate_only,
        )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/assetGroups/dry-run"}]
        return format_mutate_response(
            action="create_pmax_asset_group",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "name": name,
                "business_name": business_name,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)
