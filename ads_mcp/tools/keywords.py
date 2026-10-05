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

"""Tools for managing positive and negative keywords and shared sets in Google Ads."""

from typing import Any, Dict, List, Optional, Union
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
def add_keywords(
    customer_id: str,
    ad_group_id: Union[str, int],
    keywords: List[Union[str, Dict[str, Any]]],
    default_match_type: str = "BROAD",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds positive keywords to an ad group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        keywords: A list of keyword strings (e.g. ['plano de saude', 'convenio medico']) 
                  or dictionaries (e.g. [{'text': 'plano de saude', 'match_type': 'EXACT', 'cpc_bid': 4.50, 'final_url': 'https://...'}]).
        default_match_type: Default match type ('EXACT', 'PHRASE', 'BROAD') if not specified per keyword.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and list of created keyword resource names.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        ad_group_rn = clean_ag_id
    else:
        ad_group_rn = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        criterion_service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        operations = []
        for kw in keywords:
            op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.ad_group = ad_group_rn
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED

            if isinstance(kw, str):
                text = kw
                match_type_str = default_match_type
                cpc_bid = None
                final_url = None
            elif isinstance(kw, dict):
                text = kw.get("text", "")
                match_type_str = kw.get("match_type", default_match_type)
                cpc_bid = kw.get("cpc_bid")
                final_url = kw.get("final_url")
            else:
                continue

            match_enum = getattr(
                client.enums.KeywordMatchTypeEnum,
                match_type_str.upper(),
                client.enums.KeywordMatchTypeEnum.BROAD,
            )
            criterion.keyword.text = text
            criterion.keyword.match_type = match_enum

            if cpc_bid is not None:
                criterion.cpc_bid_micros = parse_money_to_micros(cpc_bid)
            if final_url:
                criterion.final_urls.append(final_url)

            operations.append(op)

        if not operations:
            raise ValueError("No valid keywords provided to add.")

        if validate_only:
            response = criterion_service.mutate_ad_group_criteria(
                request={
                    "customer_id": cid,
                    "operations": operations,
                    "validate_only": True,
                }
            )
        else:
            response = criterion_service.mutate_ad_group_criteria(
                customer_id=cid,
                operations=operations,
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroupCriteria/dry-run"} for _ in operations]
        return format_mutate_response(
            action="add_keywords",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group": ad_group_rn,
                "keywords_count": len(operations),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_keyword_status(
    customer_id: str,
    ad_group_id: Union[str, int],
    criterion_id: Union[str, int],
    status: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the status of a keyword criterion (PAUSED, ENABLED, or REMOVED).

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID.
        criterion_id: The criterion (keyword) ID.
        status: New status ('PAUSED', 'ENABLED', or 'REMOVED').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and details.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
    clean_crit_id = str(criterion_id).replace("-", "").strip()
    if "~" in clean_crit_id:
        clean_crit_id = clean_crit_id.split("~")[-1]
    
    resource_name = f"customers/{cid}/adGroupCriteria/{clean_ag_id}~{clean_crit_id}"

    try:
        criterion_service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        status_enum = getattr(
            client.enums.AdGroupCriterionStatusEnum,
            status.upper(),
            None,
        )
        if not status_enum:
            raise ValueError(f"Invalid keyword status: '{status}'. Choose PAUSED, ENABLED, or REMOVED.")

        criterion = op.update
        criterion.resource_name = resource_name
        criterion.status = status_enum
        op.update_mask.paths.append("status")

        if validate_only:
            response = criterion_service.mutate_ad_group_criteria(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = criterion_service.mutate_ad_group_criteria(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_keyword_status",
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
def update_keyword_cpc_bid(
    customer_id: str,
    ad_group_id: Union[str, int],
    criterion_id: Union[str, int],
    cpc_bid: Union[float, int, str],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the max CPC bid of a specific keyword criterion.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID.
        criterion_id: The criterion (keyword) ID.
        cpc_bid: New max CPC bid in currency units (e.g. 3.50). Converted to micros.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and details.
    """
    cid = clean_customer_id(customer_id)
    cpc_micros = parse_money_to_micros(cpc_bid)
    clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
    clean_crit_id = str(criterion_id).replace("-", "").strip()
    if "~" in clean_crit_id:
        clean_crit_id = clean_crit_id.split("~")[-1]

    resource_name = f"customers/{cid}/adGroupCriteria/{clean_ag_id}~{clean_crit_id}"

    try:
        criterion_service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)

        criterion = op.update
        criterion.resource_name = resource_name
        criterion.cpc_bid_micros = cpc_micros
        op.update_mask.paths.append("cpc_bid_micros")

        if validate_only:
            response = criterion_service.mutate_ad_group_criteria(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = criterion_service.mutate_ad_group_criteria(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_keyword_cpc_bid",
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
def add_negative_keywords_to_campaign(
    customer_id: str,
    campaign_id: Union[str, int],
    keywords: List[Union[str, Dict[str, Any]]],
    default_match_type: str = "BROAD",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds negative keywords directly to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        keywords: A list of keyword strings (e.g. ['gratis', 'gratuito', 'download']) 
                  or dictionaries (e.g. [{'text': 'gratis', 'match_type': 'EXACT'}]).
        default_match_type: Default match type ('EXACT', 'PHRASE', 'BROAD', default 'BROAD').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and list of created negative criteria resource names.
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
        for kw in keywords:
            op = utils.get_googleads_type("CampaignCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.campaign = campaign_rn
            criterion.negative = True

            if isinstance(kw, str):
                text = kw
                match_type_str = default_match_type
            elif isinstance(kw, dict):
                text = kw.get("text", "")
                match_type_str = kw.get("match_type", default_match_type)
            else:
                continue

            match_enum = getattr(
                client.enums.KeywordMatchTypeEnum,
                match_type_str.upper(),
                client.enums.KeywordMatchTypeEnum.BROAD,
            )
            criterion.keyword.text = text
            criterion.keyword.match_type = match_enum
            operations.append(op)

        if not operations:
            raise ValueError("No valid negative keywords provided.")

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
            action="add_negative_keywords_to_campaign",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "negative_keywords_count": len(operations),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def add_negative_keywords_to_ad_group(
    customer_id: str,
    ad_group_id: Union[str, int],
    keywords: List[Union[str, Dict[str, Any]]],
    default_match_type: str = "BROAD",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Adds negative keywords to a specific ad group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        keywords: A list of keyword strings or dictionaries with 'text' and 'match_type'.
        default_match_type: Default match type ('EXACT', 'PHRASE', 'BROAD').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and list of created negative criteria resource names.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        ad_group_rn = clean_ag_id
    else:
        ad_group_rn = f"customers/{cid}/adGroups/{clean_ag_id}"

    try:
        criterion_service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        operations = []
        for kw in keywords:
            op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)
            criterion = op.create
            criterion.ad_group = ad_group_rn
            criterion.negative = True

            if isinstance(kw, str):
                text = kw
                match_type_str = default_match_type
            elif isinstance(kw, dict):
                text = kw.get("text", "")
                match_type_str = kw.get("match_type", default_match_type)
            else:
                continue

            match_enum = getattr(
                client.enums.KeywordMatchTypeEnum,
                match_type_str.upper(),
                client.enums.KeywordMatchTypeEnum.BROAD,
            )
            criterion.keyword.text = text
            criterion.keyword.match_type = match_enum
            operations.append(op)

        if not operations:
            raise ValueError("No valid negative keywords provided.")

        if validate_only:
            response = criterion_service.mutate_ad_group_criteria(
                request={
                    "customer_id": cid,
                    "operations": operations,
                    "validate_only": True,
                }
            )
        else:
            response = criterion_service.mutate_ad_group_criteria(
                customer_id=cid,
                operations=operations,
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroupCriteria/dry-run"} for _ in operations]
        return format_mutate_response(
            action="add_negative_keywords_to_ad_group",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group": ad_group_rn,
                "negative_keywords_count": len(operations),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_negative_keyword_shared_set(
    customer_id: str,
    name: str,
    keywords: Optional[List[Union[str, Dict[str, Any]]]] = None,
    default_match_type: str = "BROAD",
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a shared list (SharedSet) of negative keywords for reuse across multiple campaigns.

    Args:
        customer_id: The Google Ads customer ID.
        name: Name of the negative keyword list (e.g. 'Termos Gerais Negativados').
        keywords: Optional list of initial negative keywords to add to the list.
        default_match_type: Default match type ('EXACT', 'PHRASE', 'BROAD').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created shared set resource name.
    """
    cid = clean_customer_id(customer_id)

    try:
        shared_set_service = utils.get_googleads_service("SharedSetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        # 1. Create Shared Set
        set_op = utils.get_googleads_type("SharedSetOperation", customer_id=cid)
        shared_set = set_op.create
        shared_set.name = name
        shared_set.type_ = client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS

        set_response = shared_set_service.mutate_shared_sets(
            customer_id=cid,
            operations=[set_op],
            validate_only=validate_only,
        )

        if validate_only:
            return format_mutate_response(
                action="create_negative_keyword_shared_set",
                results=[{"resource_name": f"customers/{cid}/sharedSets/dry-run"}],
                validate_only=True,
                extra={"name": name},
            )

        shared_set_rn = set_response.results[0].resource_name

        # 2. Add keywords to shared set if provided
        added_keywords_count = 0
        if keywords:
            shared_criterion_service = utils.get_googleads_service("SharedCriterionService", customer_id=cid)
            crit_ops = []
            for kw in keywords:
                crit_op = utils.get_googleads_type("SharedCriterionOperation", customer_id=cid)
                crit = crit_op.create
                crit.shared_set = shared_set_rn

                if isinstance(kw, str):
                    text = kw
                    match_type_str = default_match_type
                elif isinstance(kw, dict):
                    text = kw.get("text", "")
                    match_type_str = kw.get("match_type", default_match_type)
                else:
                    continue

                match_enum = getattr(
                    client.enums.KeywordMatchTypeEnum,
                    match_type_str.upper(),
                    client.enums.KeywordMatchTypeEnum.BROAD,
                )
                crit.keyword.text = text
                crit.keyword.match_type = match_enum
                crit_ops.append(crit_op)

            if crit_ops:
                crit_response = shared_criterion_service.mutate_shared_criteria(
                    customer_id=cid,
                    operations=crit_ops,
                )
                added_keywords_count = len(crit_response.results)

        return format_mutate_response(
            action="create_negative_keyword_shared_set",
            results=set_response.results,
            validate_only=False,
            extra={
                "customer_id": cid,
                "shared_set_resource_name": shared_set_rn,
                "name": name,
                "keywords_added": added_keywords_count,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def apply_negative_keyword_shared_set_to_campaign(
    customer_id: str,
    campaign_id: Union[str, int],
    shared_set_id: Union[str, int],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Attaches an existing negative keyword shared list (SharedSet) to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        shared_set_id: The SharedSet ID or resource name ('customers/.../sharedSets/...').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and campaign shared set link details.
    """
    cid = clean_customer_id(customer_id)

    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    clean_s_id = str(shared_set_id).strip()
    if clean_s_id.startswith("customers/"):
        shared_set_rn = clean_s_id
    else:
        shared_set_rn = f"customers/{cid}/sharedSets/{clean_s_id}"

    try:
        campaign_shared_set_service = utils.get_googleads_service("CampaignSharedSetService", customer_id=cid)
        op = utils.get_googleads_type("CampaignSharedSetOperation", customer_id=cid)
        
        css = op.create
        css.campaign = campaign_rn
        css.shared_set = shared_set_rn

        if validate_only:
            response = campaign_shared_set_service.mutate_campaign_shared_sets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_shared_set_service.mutate_campaign_shared_sets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignSharedSets/dry-run"}]
        return format_mutate_response(
            action="apply_negative_keyword_shared_set_to_campaign",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "shared_set": shared_set_rn,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)
