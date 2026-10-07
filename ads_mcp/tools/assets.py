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
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
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
            field_type.upper().strip(),
            None,
        )
        if not field_type_enum:
            raise ValueError(f"Invalid field_type: '{field_type}'. Valid types: SITELINK, CALLOUT, STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, LEAD_FORM, BUSINESS_NAME, BUSINESS_LOGO, AD_IMAGE, BUSINESS_MESSAGE.")

        ca.field_type = field_type_enum
        ca.status = get_enum_value(client, "AssetLinkStatusEnum", "ENABLED")

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


def _parse_whatsapp_phone_and_country(raw_phone: str, default_country: str = "BR") -> tuple[str, str]:
    """Extracts 2-letter ISO country code and national phone number from user phone input."""
    cleaned = str(raw_phone).strip()
    country_code = default_country.upper().strip()
    digits_only = "".join(c for c in cleaned if c.isdigit())

    if cleaned.startswith("+55"):
        country_code = "BR"
        national = cleaned[3:].strip()
    elif cleaned.startswith("+1"):
        country_code = "US"
        national = cleaned[2:].strip()
    elif cleaned.startswith("+"):
        national = cleaned.lstrip("+").strip()
    elif digits_only.startswith("55") and len(digits_only) in (12, 13):
        country_code = "BR"
        national = digits_only[2:].strip()
    else:
        national = cleaned.strip()

    return country_code, national


@mcp.tool()
def create_business_message_asset(
    customer_id: str,
    name: str,
    whatsapp_phone_number: str,
    country_code: Optional[str] = "BR",
    starter_message: Optional[str] = None,
    call_to_action: Optional[str] = "Fale Conosco",
    call_to_action_selection: Optional[str] = "CONTACT_US",
    campaign_id: Optional[Union[str, int]] = None,
    link_to_customer: bool = False,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a Business Message (WhatsApp) asset and optionally links it to the account or a campaign.

    NOTE: The WhatsApp phone number must be configured/authorized in the Google Ads account.

    Args:
        customer_id: The Google Ads customer ID.
        name: A descriptive name for the message asset.
        whatsapp_phone_number: The WhatsApp phone number (e.g. '+5516997164515' or '(16) 99716-4515').
        country_code: Two-letter ISO country code (e.g. 'BR', 'US'). Default is 'BR'.
        starter_message: Optional pre-filled starter message sent when user clicks to chat.
        call_to_action: Optional call to action text shown alongside the message button (e.g. 'Fale Conosco').
        call_to_action_selection: Optional call to action enum ('CONTACT_US', 'LEARN_MORE', 'GET_QUOTE', 'BOOK_NOW', 'APPLY_NOW', 'GET_INFO', 'GET_OFFER', 'GET_STARTED'). Default is 'CONTACT_US'.
        campaign_id: Optional campaign ID to link this asset to immediately.
        link_to_customer: If True, links this WhatsApp asset at the Customer (Account) level so all campaigns can use it.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status, created asset resource name, and linkage details.
    """
    cid = clean_customer_id(customer_id)
    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        asset = op.create
        asset.name = name.strip()
        asset.type_ = get_enum_value(client, "AssetTypeEnum", "BUSINESS_MESSAGE")

        # Set provider to WHATSAPP
        asset.business_message_asset.message_provider = get_enum_value(
            client, "BusinessMessageProviderEnum", "WHATSAPP"
        )

        parsed_country, parsed_national = _parse_whatsapp_phone_and_country(
            whatsapp_phone_number, default_country=country_code or "BR"
        )
        asset.business_message_asset.whatsapp_info.country_code = parsed_country
        asset.business_message_asset.whatsapp_info.phone_number = parsed_national

        if starter_message:
            asset.business_message_asset.starter_message = starter_message.strip()

        # Handle call to action enum and description
        cta_selection_str = (call_to_action_selection or "CONTACT_US").upper().strip()
        cta_enum = getattr(
            get_enum_class(client, "BusinessMessageCallToActionTypeEnum"),
            cta_selection_str,
            get_enum_value(client, "BusinessMessageCallToActionTypeEnum", "CONTACT_US"),
        )
        if cta_enum is not None:
            asset.business_message_asset.call_to_action.call_to_action_selection = cta_enum

        cta_desc = (call_to_action or "").strip()
        if cta_desc:
            asset.business_message_asset.call_to_action.call_to_action_description = cta_desc

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
        if not validate_only:
            if link_to_customer:
                try:
                    link_result = link_asset_to_customer(
                        customer_id=cid,
                        asset_id_or_resource_name=asset_rn,
                        field_type="BUSINESS_MESSAGE",
                        validate_only=False,
                    )
                except Exception as link_err:
                    link_result = {
                        "warning": f"Asset created successfully ({asset_rn}), but linking to account failed: {str(link_err)}. You may link it using link_asset_to_customer."
                    }
            elif campaign_id:
                try:
                    link_result = link_asset_to_campaign(
                        customer_id=cid,
                        campaign_id=campaign_id,
                        asset_id_or_resource_name=asset_rn,
                        field_type="BUSINESS_MESSAGE",
                        validate_only=False,
                    )
                except Exception as link_err:
                    link_result = {
                        "warning": f"Asset created successfully ({asset_rn}), but linking to campaign failed: {str(link_err)}. You may link it using link_asset_to_campaign."
                    }
        else:
            if link_to_customer or campaign_id:
                link_result = {
                    "validate_only": True,
                    "message": "Asset creation validated. Linkage will occur on non-dry-run execution.",
                }

        return format_mutate_response(
            action="create_business_message_asset",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "asset_name": name,
                "country_code": parsed_country,
                "phone_number": parsed_national,
                "linked_to_customer": bool(link_to_customer),
                "linked_to_campaign": bool(campaign_id),
                "link_details": link_result,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def unlink_asset_from_campaign(
    customer_id: str,
    campaign_id: Optional[Union[str, int]] = None,
    asset_id_or_resource_name: Optional[Union[str, int]] = None,
    field_type: Optional[str] = None,
    campaign_asset_resource_name: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Unlinks / removes an Asset from a Campaign.

    You can either provide the full `campaign_asset_resource_name` ('customers/.../campaignAssets/...')
    OR pass `campaign_id`, `asset_id_or_resource_name`, and `field_type`.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        asset_id_or_resource_name: The Asset ID or resource name.
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
        campaign_asset_resource_name: Optional full resource name of the CampaignAsset link.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and removed campaign asset details.
    """
    cid = clean_customer_id(customer_id)
    if campaign_asset_resource_name:
        resource_name = campaign_asset_resource_name.strip()
    else:
        if not campaign_id or not asset_id_or_resource_name or not field_type:
            raise ValueError("Must provide either campaign_asset_resource_name or (campaign_id, asset_id_or_resource_name, and field_type).")
        clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
        clean_a_id = str(asset_id_or_resource_name).replace("-", "").strip().removeprefix(f"customers/{cid}/assets/")
        resource_name = f"customers/{cid}/campaignAssets/{clean_c_id}~{clean_a_id}~{field_type.upper().strip()}"

    try:
        campaign_asset_service = utils.get_googleads_service("CampaignAssetService", customer_id=cid)
        op = utils.get_googleads_type("CampaignAssetOperation", customer_id=cid)
        op.remove = resource_name

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

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="unlink_asset_from_campaign",
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
def link_asset_to_customer(
    customer_id: str,
    asset_id_or_resource_name: Union[str, int],
    field_type: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Links an existing Asset at the Customer (Account) level.

    Useful for account-wide assets such as WhatsApp/Business Messages,
    Account-level Sitelinks, Callouts, Business Name, or Business Logo.

    Args:
        customer_id: The Google Ads customer ID.
        asset_id_or_resource_name: The Asset ID or full resource name ('customers/.../assets/...').
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and customer asset link details.
    """
    cid = clean_customer_id(customer_id)
    clean_a_id = str(asset_id_or_resource_name).strip()
    if clean_a_id.startswith("customers/"):
        asset_rn = clean_a_id
    else:
        asset_rn = f"customers/{cid}/assets/{clean_a_id}"

    try:
        customer_asset_service = utils.get_googleads_service("CustomerAssetService", customer_id=cid)
        op = utils.get_googleads_type("CustomerAssetOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        ca = op.create
        ca.asset = asset_rn

        field_type_enum = getattr(
            get_enum_class(client, "AssetFieldTypeEnum"),
            field_type.upper().strip(),
            None,
        )
        if not field_type_enum:
            raise ValueError(f"Invalid field_type: '{field_type}'. Valid types: SITELINK, CALLOUT, STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, LEAD_FORM, BUSINESS_NAME, BUSINESS_LOGO, AD_IMAGE, BUSINESS_MESSAGE.")

        ca.field_type = field_type_enum
        ca.status = get_enum_value(client, "AssetLinkStatusEnum", "ENABLED")

        if validate_only:
            response = customer_asset_service.mutate_customer_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = customer_asset_service.mutate_customer_assets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/customerAssets/dry-run"}]
        return format_mutate_response(
            action="link_asset_to_customer",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "asset": asset_rn,
                "field_type": field_type.upper().strip(),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def unlink_asset_from_customer(
    customer_id: str,
    asset_id_or_resource_name: Optional[Union[str, int]] = None,
    field_type: Optional[str] = None,
    customer_asset_resource_name: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Unlinks / removes an Asset from the Customer (Account) level.

    Essential for unlinking outdated WhatsApp/Business Message assets or old account-level sitelinks.

    Args:
        customer_id: The Google Ads customer ID.
        asset_id_or_resource_name: The Asset ID or resource name.
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
        customer_asset_resource_name: Optional full resource name of the CustomerAsset link.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and removed customer asset details.
    """
    cid = clean_customer_id(customer_id)
    if customer_asset_resource_name:
        resource_name = customer_asset_resource_name.strip()
    else:
        if not asset_id_or_resource_name or not field_type:
            raise ValueError("Must provide either customer_asset_resource_name or (asset_id_or_resource_name and field_type).")
        clean_a_id = str(asset_id_or_resource_name).replace("-", "").strip().removeprefix(f"customers/{cid}/assets/")
        resource_name = f"customers/{cid}/customerAssets/{clean_a_id}~{field_type.upper().strip()}"

    try:
        customer_asset_service = utils.get_googleads_service("CustomerAssetService", customer_id=cid)
        op = utils.get_googleads_type("CustomerAssetOperation", customer_id=cid)
        op.remove = resource_name

        if validate_only:
            response = customer_asset_service.mutate_customer_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = customer_asset_service.mutate_customer_assets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="unlink_asset_from_customer",
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
def link_asset_to_ad_group(
    customer_id: str,
    ad_group_id: Union[str, int],
    asset_id_or_resource_name: Union[str, int],
    field_type: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Links an existing Asset to an Ad Group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        asset_id_or_resource_name: The Asset ID or resource name.
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and ad group asset link details.
    """
    cid = clean_customer_id(customer_id)
    clean_ag_id = str(ad_group_id).strip()
    if clean_ag_id.startswith("customers/"):
        ad_group_rn = clean_ag_id
    else:
        ad_group_rn = f"customers/{cid}/adGroups/{clean_ag_id}"

    clean_a_id = str(asset_id_or_resource_name).strip()
    if clean_a_id.startswith("customers/"):
        asset_rn = clean_a_id
    else:
        asset_rn = f"customers/{cid}/assets/{clean_a_id}"

    try:
        ad_group_asset_service = utils.get_googleads_service("AdGroupAssetService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupAssetOperation", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        aga = op.create
        aga.ad_group = ad_group_rn
        aga.asset = asset_rn

        field_type_enum = getattr(
            get_enum_class(client, "AssetFieldTypeEnum"),
            field_type.upper().strip(),
            None,
        )
        if not field_type_enum:
            raise ValueError(f"Invalid field_type: '{field_type}'. Valid types: SITELINK, CALLOUT, STRUCTURED_SNIPPET, CALL, PROMOTION, PRICE, LEAD_FORM, BUSINESS_NAME, BUSINESS_LOGO, AD_IMAGE, BUSINESS_MESSAGE.")

        aga.field_type = field_type_enum
        aga.status = get_enum_value(client, "AssetLinkStatusEnum", "ENABLED")

        if validate_only:
            response = ad_group_asset_service.mutate_ad_group_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = ad_group_asset_service.mutate_ad_group_assets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/adGroupAssets/dry-run"}]
        return format_mutate_response(
            action="link_asset_to_ad_group",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group": ad_group_rn,
                "asset": asset_rn,
                "field_type": field_type.upper().strip(),
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def unlink_asset_from_ad_group(
    customer_id: str,
    ad_group_id: Optional[Union[str, int]] = None,
    asset_id_or_resource_name: Optional[Union[str, int]] = None,
    field_type: Optional[str] = None,
    ad_group_asset_resource_name: Optional[str] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Unlinks / removes an Asset from an Ad Group.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        asset_id_or_resource_name: The Asset ID or resource name.
        field_type: Field type ('SITELINK', 'CALLOUT', 'STRUCTURED_SNIPPET', 'CALL', 'PROMOTION', 'PRICE', 'LEAD_FORM', 'BUSINESS_NAME', 'BUSINESS_LOGO', 'AD_IMAGE', 'BUSINESS_MESSAGE').
        ad_group_asset_resource_name: Optional full resource name of the AdGroupAsset link.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and removed ad group asset details.
    """
    cid = clean_customer_id(customer_id)
    if ad_group_asset_resource_name:
        resource_name = ad_group_asset_resource_name.strip()
    else:
        if not ad_group_id or not asset_id_or_resource_name or not field_type:
            raise ValueError("Must provide either ad_group_asset_resource_name or (ad_group_id, asset_id_or_resource_name, and field_type).")
        clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
        clean_a_id = str(asset_id_or_resource_name).replace("-", "").strip().removeprefix(f"customers/{cid}/assets/")
        resource_name = f"customers/{cid}/adGroupAssets/{clean_ag_id}~{clean_a_id}~{field_type.upper().strip()}"

    try:
        ad_group_asset_service = utils.get_googleads_service("AdGroupAssetService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupAssetOperation", customer_id=cid)
        op.remove = resource_name

        if validate_only:
            response = ad_group_asset_service.mutate_ad_group_assets(
                request={
                    "customer_id": cid,
                    "operations": [op],
                    "validate_only": True,
                }
            )
        else:
            response = ad_group_asset_service.mutate_ad_group_assets(
                customer_id=cid,
                operations=[op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="unlink_asset_from_ad_group",
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
def update_asset(
    customer_id: str,
    asset_id_or_resource_name: Union[str, int],
    name: Optional[str] = None,
    sitelink_text: Optional[str] = None,
    sitelink_description1: Optional[str] = None,
    sitelink_description2: Optional[str] = None,
    callout_text: Optional[str] = None,
    call_phone_number: Optional[str] = None,
    whatsapp_phone_number: Optional[str] = None,
    whatsapp_country_code: Optional[str] = None,
    starter_message: Optional[str] = None,
    call_to_action: Optional[str] = None,
    call_to_action_selection: Optional[str] = None,
    final_urls: Optional[List[str]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates an existing Asset in Google Ads without needing to recreate it.

    Supports updating Sitelinks, Callouts, Call assets, WhatsApp/Business Message assets,
    asset names, and destination URLs.

    Args:
        customer_id: The Google Ads customer ID.
        asset_id_or_resource_name: The Asset ID or resource name ('customers/.../assets/...').
        name: Optional updated internal name of the asset.
        sitelink_text: Optional updated text for Sitelink asset (up to 25 chars).
        sitelink_description1: Optional updated description 1 for Sitelink.
        sitelink_description2: Optional updated description 2 for Sitelink.
        callout_text: Optional updated callout text (up to 25 chars).
        call_phone_number: Optional updated phone number for Call asset.
        whatsapp_phone_number: Optional updated WhatsApp phone number.
        whatsapp_country_code: Optional updated country code for WhatsApp (e.g. 'BR').
        starter_message: Optional updated pre-filled starter message for WhatsApp.
        call_to_action: Optional updated call to action text for WhatsApp.
        call_to_action_selection: Optional updated call to action enum ('CONTACT_US', 'LEARN_MORE', etc.).
        final_urls: Optional updated destination URLs list.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and updated asset details.
    """
    cid = clean_customer_id(customer_id)
    clean_a_id = str(asset_id_or_resource_name).strip()
    if clean_a_id.startswith("customers/"):
        asset_rn = clean_a_id
    else:
        asset_rn = f"customers/{cid}/assets/{clean_a_id}"

    try:
        asset_service = utils.get_googleads_service("AssetService", customer_id=cid)
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))

        op = utils.get_googleads_type("AssetOperation", customer_id=cid)
        asset = op.update
        asset.resource_name = asset_rn

        paths = []

        if name is not None:
            asset.name = name.strip()
            paths.append("name")

        if sitelink_text is not None:
            asset.sitelink_asset.link_text = sitelink_text.strip()
            paths.append("sitelink_asset.link_text")

        if sitelink_description1 is not None:
            asset.sitelink_asset.description1 = sitelink_description1.strip()
            paths.append("sitelink_asset.description1")

        if sitelink_description2 is not None:
            asset.sitelink_asset.description2 = sitelink_description2.strip()
            paths.append("sitelink_asset.description2")

        if callout_text is not None:
            asset.callout_asset.callout_text = callout_text.strip()
            paths.append("callout_asset.callout_text")

        if call_phone_number is not None:
            asset.call_asset.phone_number = call_phone_number.strip()
            paths.append("call_asset.phone_number")

        if whatsapp_phone_number is not None:
            w_country, w_national = _parse_whatsapp_phone_and_country(
                whatsapp_phone_number, default_country=whatsapp_country_code or "BR"
            )
            asset.business_message_asset.whatsapp_info.country_code = w_country
            asset.business_message_asset.whatsapp_info.phone_number = w_national
            paths.append("business_message_asset.whatsapp_info.country_code")
            paths.append("business_message_asset.whatsapp_info.phone_number")

        if starter_message is not None:
            asset.business_message_asset.starter_message = starter_message.strip()
            paths.append("business_message_asset.starter_message")

        if call_to_action is not None or call_to_action_selection is not None:
            if call_to_action_selection is not None:
                cta_selection_str = call_to_action_selection.upper().strip()
                cta_enum = getattr(
                    get_enum_class(client, "BusinessMessageCallToActionTypeEnum"),
                    cta_selection_str,
                    get_enum_value(client, "BusinessMessageCallToActionTypeEnum", "CONTACT_US"),
                )
                if cta_enum is not None:
                    asset.business_message_asset.call_to_action.call_to_action_selection = cta_enum
                    paths.append("business_message_asset.call_to_action.call_to_action_selection")

            if call_to_action is not None:
                asset.business_message_asset.call_to_action.call_to_action_description = call_to_action.strip()
                paths.append("business_message_asset.call_to_action.call_to_action_description")

        if final_urls:
            asset.final_urls.extend(final_urls)
            paths.append("final_urls")

        if not paths:
            raise ValueError("No fields provided to update on asset.")

        client.copy_from(op.update_mask, utils.get_googleads_type("FieldMask", customer_id=cid, paths=paths))

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

        results = response.results if not validate_only else [{"resource_name": asset_rn}]
        return format_mutate_response(
            action="update_asset",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "asset_resource_name": asset_rn,
                "updated_fields": paths,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


