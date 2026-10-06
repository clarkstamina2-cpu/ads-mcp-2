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

"""Tools for managing Ad Assets & Extensions (Sitelinks, Callouts, Structured Snippets, Call Assets) in Google Ads."""

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
def create_sitelink_asset(
    customer_id: str,
    link_text: str,
    final_urls: List[str],
    description1: Optional[str] = None,
    description2: Optional[str] = None,
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Sitelink asset and optionally links it to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        link_text: The visible sitelink text (up to 25 characters).
        final_urls: Destination URLs for the sitelink.
        description1: Optional description line 1 (up to 35 characters).
        description2: Optional description line 2 (up to 35 characters).
        campaign_id: Optional campaign ID to automatically attach this sitelink to.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset resource name.
    """
    cid = clean_customer_id(customer_id)

    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        
        asset = op.create
        asset.sitelink_asset.link_text = link_text[:25]
        asset.final_urls.extend(final_urls)
        if description1:
            asset.sitelink_asset.description1 = description1[:35]
        if description2:
            asset.sitelink_asset.description2 = description2[:35]

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(
                customer_id=cid,
                operations=[op],
            )

        if validate_only:
            return format_mutate_response(
                action="create_sitelink_asset",
                results=[{"resource_name": f"customers/{cid}/assets/dry-run"}],
                validate_only=True,
                extra={"link_text": link_text},
            )

        asset_rn = response.results[0].resource_name

        # Link to campaign if provided
        campaign_asset_rn = None
        if campaign_id:
            link_res = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="SITELINK",
            )
            if link_res.get("resource_names"):
                campaign_asset_rn = link_res["resource_names"][0]

        return format_mutate_response(
            action="create_sitelink_asset",
            results=response.results,
            validate_only=False,
            extra={
                "customer_id": cid,
                "asset_resource_name": asset_rn,
                "campaign_asset_resource_name": campaign_asset_rn,
                "link_text": link_text,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_callout_asset(
    customer_id: str,
    callout_text: str,
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Callout (Frase de Destaque) asset and optionally links it to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        callout_text: The callout text (up to 25 characters, e.g. 'Atendimento 24h', 'Frete Grátis').
        campaign_id: Optional campaign ID to attach this callout to.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset resource name.
    """
    cid = clean_customer_id(customer_id)

    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        op = utils.get_googleads_type("AssetOperation", customer_id=cid)

        asset = op.create
        asset.callout_asset.callout_text = callout_text[:25]

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(
                customer_id=cid,
                operations=[op],
            )

        if validate_only:
            return format_mutate_response(
                action="create_callout_asset",
                results=[{"resource_name": f"customers/{cid}/assets/dry-run"}],
                validate_only=True,
                extra={"callout_text": callout_text},
            )

        asset_rn = response.results[0].resource_name

        campaign_asset_rn = None
        if campaign_id:
            link_res = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="CALLOUT",
            )
            if link_res.get("resource_names"):
                campaign_asset_rn = link_res["resource_names"][0]

        return format_mutate_response(
            action="create_callout_asset",
            results=response.results,
            validate_only=False,
            extra={
                "customer_id": cid,
                "asset_resource_name": asset_rn,
                "campaign_asset_resource_name": campaign_asset_rn,
                "callout_text": callout_text,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_structured_snippet_asset(
    customer_id: str,
    header: str,
    values: List[str],
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Structured Snippet (Snippet Estruturado) asset and optionally links it to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        header: The snippet header (e.g. 'Services', 'Brands', 'Types', 'Courses', 'Destinations', 'Models', 'Styles').
        values: List of snippet values (up to 10 values, max 25 chars each).
        campaign_id: Optional campaign ID to attach this snippet to.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset details.
    """
    cid = clean_customer_id(customer_id)

    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        op = utils.get_googleads_type("AssetOperation", customer_id=cid)

        asset = op.create
        asset.structured_snippet_asset.header = header
        asset.structured_snippet_asset.values.extend([v[:25] for v in values])

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(
                customer_id=cid,
                operations=[op],
            )

        if validate_only:
            return format_mutate_response(
                action="create_structured_snippet_asset",
                results=[{"resource_name": f"customers/{cid}/assets/dry-run"}],
                validate_only=True,
                extra={"header": header, "values": values},
            )

        asset_rn = response.results[0].resource_name

        campaign_asset_rn = None
        if campaign_id:
            link_res = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="STRUCTURED_SNIPPET",
            )
            if link_res.get("resource_names"):
                campaign_asset_rn = link_res["resource_names"][0]

        return format_mutate_response(
            action="create_structured_snippet_asset",
            results=response.results,
            validate_only=False,
            extra={
                "customer_id": cid,
                "asset_resource_name": asset_rn,
                "campaign_asset_resource_name": campaign_asset_rn,
                "header": header,
                "values": values,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_call_asset(
    customer_id: str,
    phone_number: str,
    country_code: str = "BR",
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Call asset (Extensão de Chamada / Telefone) and optionally links it to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        phone_number: The raw phone number string (e.g. '11999998888' or '(11) 99999-8888').
        country_code: Two-letter country code (default 'BR', 'US', etc.).
        campaign_id: Optional campaign ID to attach this call asset to.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset details.
    """
    cid = clean_customer_id(customer_id)

    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        op = utils.get_googleads_type("AssetOperation", customer_id=cid)

        asset = op.create
        asset.call_asset.phone_number = phone_number
        asset.call_asset.country_code = country_code.upper()

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(
                customer_id=cid,
                operations=[op],
            )

        if validate_only:
            return format_mutate_response(
                action="create_call_asset",
                results=[{"resource_name": f"customers/{cid}/assets/dry-run"}],
                validate_only=True,
                extra={"phone_number": phone_number, "country_code": country_code},
            )

        asset_rn = response.results[0].resource_name

        campaign_asset_rn = None
        if campaign_id:
            link_res = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="CALL",
            )
            if link_res.get("resource_names"):
                campaign_asset_rn = link_res["resource_names"][0]

        return format_mutate_response(
            action="create_call_asset",
            results=response.results,
            validate_only=False,
            extra={
                "customer_id": cid,
                "asset_resource_name": asset_rn,
                "campaign_asset_resource_name": campaign_asset_rn,
                "phone_number": phone_number,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def link_asset_to_campaign(
    customer_id: str,
    campaign_id: Union[str, int],
    asset_id_or_resource_name: Union[str, int],
    field_type: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Links an existing Asset to a Campaign.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        asset_id_or_resource_name: The Asset ID or full resource name ('customers/.../assets/...').
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and campaign asset link details.
    """
    cid = clean_customer_id(customer_id)

    clean_c_id = str(campaign_id).strip()
    if clean_c_id.startswith("customers/"):
        campaign_rn = clean_c_id
    else:
        campaign_rn = f"customers/{cid}/campaigns/{clean_c_id}"

    clean_a_id = str(asset_id_or_resource_name).strip()
    if clean_a_id.startswith("customers/"):
        asset_rn = clean_a_id
    else:
        asset_rn = f"customers/{cid}/assets/{clean_a_id}"

    try:
        campaign_asset_service = utils.get_googleads_service("CampaignAssetService", customer_id=cid)
        op = utils.get_googleads_type("CampaignAssetOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        ca = op.create
        ca.campaign = campaign_rn
        ca.asset = asset_rn

        field_type_enum = getattr(
            get_enum_class(client, "AssetFieldTypeEnum"),
            field_type.upper(),
            None,
        )
        if not field_type_enum:
            raise ValueError(f"Invalid field_type: '{field_type}'. Valid types: SITELINK, CALLOUT, STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, LEAD_FORM, BUSINESS_NAME, BUSINESS_LOGO, AD_IMAGE, BUSINESS_MESSAGE.")

        ca.field_type = field_type_enum

        if validate_only:
            response = campaign_asset_service.mutate_campaign_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_asset_service.mutate_campaign_assets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignAssets/dry-run"}]
        return format_mutate_response(
            action="link_asset_to_campaign",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "asset": asset_rn,
                "field_type": field_type.upper(),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_business_name_asset(
    customer_id: str,
    business_name: str,
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Business Name asset (TextAsset) and optionally links it to a campaign.

    NOTE: The Google Ads account must be enrolled/approved in the Advertiser Verification Program
    to display Business Name assets in Search ads.

    Args:
        customer_id: The Google Ads customer ID.
        business_name: The company/business name (up to 25 characters).
        campaign_id: Optional campaign ID to link this asset to immediately.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset resource name.
    """
    cid = clean_customer_id(customer_id)
    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        asset = op.create
        asset.name = f"Business Name - {business_name.strip()[:20]}"
        asset.text_asset.text = business_name.strip()
        asset.type_ = get_enum_value(client, "AssetTypeEnum", "TEXT")

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(customer_id=cid, operations=[op])

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/assets/dry-run"}]
        asset_rn = results[0]["resource_name"] if isinstance(results[0], dict) else getattr(results[0], "resource_name", f"customers/{cid}/assets/dry-run")

        link_result = None
        if campaign_id:
            link_result = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="BUSINESS_NAME",
                validate_only=validate_only,
            )

        return format_mutate_response(
            action="create_business_name_asset",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "business_name": business_name,
                "linked_to_campaign": bool(campaign_id),
                "link_details": link_result,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_image_asset(
    customer_id: str,
    name: str,
    image_url_or_base64: str,
    field_type: str = "AD_IMAGE",
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates an Image asset (for square logos or ad marketing images) and optionally links it to a campaign.

    Args:
        customer_id: The Google Ads customer ID.
        name: A descriptive name for the image asset.
        image_url_or_base64: An HTTPS URL pointing to the image, or a base64-encoded image string.
        field_type: 'AD_IMAGE' (marketing image) or 'BUSINESS_LOGO' (square business logo).
        campaign_id: Optional campaign ID to link this asset to immediately.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset resource name.
    """
    import base64
    import urllib.request

    cid = clean_customer_id(customer_id)
    try:
        # Obtain image bytes
        src = image_url_or_base64.strip()
        if src.startswith("http://") or src.startswith("https://"):
            req = urllib.request.Request(src, headers={"User-Agent": "GoogleAdsMCP/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                image_bytes = resp.read()
        else:
            # Assume base64 string
            if "base64," in src:
                src = src.split("base64,")[-1]
            image_bytes = base64.b64decode(src)

        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        asset = op.create
        asset.name = name.strip()
        asset.type_ = get_enum_value(client, "AssetTypeEnum", "IMAGE")
        asset.image_asset.data = image_bytes

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(customer_id=cid, operations=[op])

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/assets/dry-run"}]
        asset_rn = results[0]["resource_name"] if isinstance(results[0], dict) else getattr(results[0], "resource_name", f"customers/{cid}/assets/dry-run")

        target_field_type = field_type.upper().strip()
        link_result = None
        if campaign_id:
            link_result = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type=target_field_type,
                validate_only=validate_only,
            )

        return format_mutate_response(
            action="create_image_asset",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "asset_name": name,
                "field_type": target_field_type,
                "linked_to_campaign": bool(campaign_id),
                "link_details": link_result,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def create_business_message_asset(
    customer_id: str,
    name: str,
    whatsapp_phone_number: str,
    starter_message: Optional[str] = None,
    call_to_action: Optional[str] = None,
    campaign_id: Optional[Union[str, int]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Business Message (WhatsApp) asset and optionally links it to a campaign.

    NOTE: The WhatsApp phone number must be configured/authorized in the Google Ads account.

    Args:
        customer_id: The Google Ads customer ID.
        name: A descriptive name for the message asset.
        whatsapp_phone_number: International format phone number (e.g. '+5511999999999').
        starter_message: Optional pre-filled starter message sent when user clicks to chat.
        call_to_action: Optional call to action text shown alongside the message button.
        campaign_id: Optional campaign ID to link this asset to immediately.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and created asset resource name.
    """
    cid = clean_customer_id(customer_id)
    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        asset = op.create
        asset.name = name.strip()
        asset.type_ = get_enum_value(client, "AssetTypeEnum", "BUSINESS_MESSAGE")

        asset.business_message_asset.whatsapp_info.phone_number = whatsapp_phone_number.strip()
        if starter_message:
            asset.business_message_asset.starter_message = starter_message.strip()
        if call_to_action:
            asset.business_message_asset.call_to_action = call_to_action.strip()

        if validate_only:
            response = asset_service.mutate_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = asset_service.mutate_assets(customer_id=cid, operations=[op])

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/assets/dry-run"}]
        asset_rn = results[0]["resource_name"] if isinstance(results[0], dict) else getattr(results[0], "resource_name", f"customers/{cid}/assets/dry-run")

        link_result = None
        if campaign_id:
            link_result = link_asset_to_campaign(
                customer_id=cid,
                campaign_id=campaign_id,
                asset_id_or_resource_name=asset_rn,
                field_type="BUSINESS_MESSAGE",
                validate_only=validate_only,
            )

        return format_mutate_response(
            action="create_business_message_asset",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "asset_name": name,
                "phone_number": whatsapp_phone_number,
                "linked_to_campaign": bool(campaign_id),
                "link_details": link_result,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)

