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

"""Tools: EU political ads declaration, demographic bid modifiers and 'why is my campaign not serving'."""

import collections
from typing import Any, Dict, List, Optional, Union
from fastmcp.exceptions import ToolError
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.search import search
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    format_mutate_response,
    get_enum_class,
    handle_googleads_exception,
)


def _numeric_id(value: Union[str, int]) -> str:
    """Accepts '123', 123 or a resource name ('customers/1/campaigns/123') and returns '123'."""
    return str(value).strip().rsplit("/", 1)[-1].replace("-", "")


# ---------------------------------------------------------------------------
# 1. EU political advertising declaration on an existing campaign
# ---------------------------------------------------------------------------
@mcp.tool()
def set_campaign_eu_political_advertising(
    customer_id: str,
    campaign_id: Union[str, int],
    contains_eu_political_advertising: bool,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Declares whether an EXISTING campaign contains EU political advertising.

    Google requires this declaration before some changes to a campaign (for example geo targets), and fails with a
    "confirm whether the campaign has EU political ads" error otherwise. This is a declaration made by the
    advertiser, so the value is REQUIRED (there is no default): pass False only if the campaign does NOT contain
    political ads targeting the EU.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID or resource name.
        contains_eu_political_advertising: True if the campaign contains EU political ads, False if it does not.
        validate_only: If True, only validates without applying.

    Returns:
        Dict with success status and the declared value.
    """
    cid = clean_customer_id(customer_id)
    campaign_rn = f"customers/{cid}/campaigns/{_numeric_id(campaign_id)}"
    status_name = (
        "CONTAINS_EU_POLITICAL_ADVERTISING"
        if contains_eu_political_advertising
        else "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
    )

    try:
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        service = utils.get_googleads_service("CampaignService", customer_id=cid)
        op = utils.get_googleads_type("CampaignOperation", customer_id=cid)

        campaign = op.update
        campaign.resource_name = campaign_rn
        campaign.contains_eu_political_advertising = getattr(
            get_enum_class(client, "EuPoliticalAdvertisingStatusEnum"), status_name
        )
        op.update_mask.paths.append("contains_eu_political_advertising")

        if validate_only:
            service.mutate_campaigns(request={"customer_id": cid, "operations": [op], "validate_only": True})
            results = [{"resource_name": campaign_rn}]
        else:
            results = service.mutate_campaigns(customer_id=cid, operations=[op]).results

        return format_mutate_response(
            action="set_campaign_eu_political_advertising",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "campaign": campaign_rn,
                "contains_eu_political_advertising": bool(contains_eu_political_advertising),
                "status": status_name,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


# ---------------------------------------------------------------------------
# 2. Bid modifier by demographic segment (age, gender, parental status, income) at ad group level
# ---------------------------------------------------------------------------
_DEMOGRAPHICS = {
    # type: (criterion type in GAQL, enum name, attribute on the criterion)
    "AGE_RANGE": ("AGE_RANGE", "AgeRangeTypeEnum", "age_range"),
    "GENDER": ("GENDER", "GenderTypeEnum", "gender"),
    "PARENTAL_STATUS": ("PARENTAL_STATUS", "ParentalStatusTypeEnum", "parental_status"),
    "INCOME_RANGE": ("INCOME_RANGE", "IncomeRangeTypeEnum", "income_range"),
}


@mcp.tool()
def set_ad_group_demographic_bid_modifier(
    customer_id: str,
    ad_group_id: Union[str, int],
    demographic_type: str,
    value: str,
    bid_modifier: float,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Sets a bid adjustment for a demographic segment (age range, gender, parental status or income) in an ad group.

    Examples of bid_modifier: 1.0 = no change, 1.2 = +20%, 0.7 = -30%. Allowed range 0.1 to 10.0.
    To EXCLUDE a segment instead, use add_ad_group_demographic_exclusion.

    Args:
        customer_id: The Google Ads customer ID.
        ad_group_id: The ad group ID or resource name.
        demographic_type: 'AGE_RANGE', 'GENDER', 'PARENTAL_STATUS' or 'INCOME_RANGE'.
        value: The segment, depending on demographic_type:
               - AGE_RANGE: 'AGE_RANGE_18_24', 'AGE_RANGE_25_34', 'AGE_RANGE_35_44', 'AGE_RANGE_45_54',
                 'AGE_RANGE_55_64', 'AGE_RANGE_65_UP', 'AGE_RANGE_UNDETERMINED'
               - GENDER: 'MALE', 'FEMALE', 'UNDETERMINED'
               - PARENTAL_STATUS: 'PARENT', 'NOT_A_PARENT', 'UNDETERMINED'
               - INCOME_RANGE: 'INCOME_RANGE_0_50', 'INCOME_RANGE_50_60', 'INCOME_RANGE_60_70', 'INCOME_RANGE_70_80',
                 'INCOME_RANGE_80_90', 'INCOME_RANGE_90_UP', 'INCOME_RANGE_UNDETERMINED'
        bid_modifier: The bid multiplier (0.1 to 10.0).
        validate_only: If True, only validates without applying.

    Returns:
        Dict with the action taken ('updated' an existing criterion or 'created' a new one) and the resource name.
    """
    cid = clean_customer_id(customer_id)
    ad_group = _numeric_id(ad_group_id)
    dtype = str(demographic_type).strip().upper()
    seg = str(value).strip().upper()

    if dtype not in _DEMOGRAPHICS:
        raise ToolError(f"Invalid demographic_type '{demographic_type}'. Use one of: {', '.join(_DEMOGRAPHICS)}.")
    if not 0.1 <= float(bid_modifier) <= 10.0:
        raise ToolError("bid_modifier must be between 0.1 and 10.0 (to exclude a segment use add_ad_group_demographic_exclusion).")
    gaql_type, enum_name, attr = _DEMOGRAPHICS[dtype]

    try:
        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        enum_cls = get_enum_class(client, enum_name)
        enum_value = getattr(enum_cls, seg, None)
        if enum_value is None:
            valid = [m.name for m in enum_cls if m.name not in ("UNSPECIFIED", "UNKNOWN")]
            raise ToolError(f"Invalid value '{value}' for {dtype}. Valid values: {', '.join(valid)}.")

        existing = search(
            customer_id=cid,
            fields=[
                "ad_group_criterion.resource_name",
                "ad_group_criterion.criterion_id",
                "ad_group_criterion.negative",
            ],
            resource="ad_group_criterion",
            conditions=[
                f"ad_group.id = {ad_group}",
                f"ad_group_criterion.type = '{gaql_type}'",
                f"ad_group_criterion.{attr}.type = '{seg}'",
            ],
        )

        service = utils.get_googleads_service("AdGroupCriterionService", customer_id=cid)
        op = utils.get_googleads_type("AdGroupCriterionOperation", customer_id=cid)

        if existing:
            row = existing[0]
            if row["ad_group_criterion.negative"]:
                raise ToolError(
                    f"The segment {seg} is EXCLUDED in this ad group, so a bid modifier does not apply. "
                    "Remove the exclusion first if you want to bid on it."
                )
            resource_name = row["ad_group_criterion.resource_name"]
            criterion = op.update
            criterion.resource_name = resource_name
            criterion.bid_modifier = float(bid_modifier)
            op.update_mask.paths.append("bid_modifier")
            action_taken = "updated"
        else:
            criterion = op.create
            criterion.ad_group = f"customers/{cid}/adGroups/{ad_group}"
            getattr(criterion, attr).type_ = enum_value
            criterion.bid_modifier = float(bid_modifier)
            resource_name = f"customers/{cid}/adGroupCriteria/{ad_group}~(new)"
            action_taken = "created"

        if validate_only:
            service.mutate_ad_group_criteria(request={"customer_id": cid, "operations": [op], "validate_only": True})
            results = [{"resource_name": resource_name}]
        else:
            response = service.mutate_ad_group_criteria(customer_id=cid, operations=[op])
            results = response.results
            resource_name = results[0].resource_name

        return format_mutate_response(
            action="set_ad_group_demographic_bid_modifier",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "ad_group_id": ad_group,
                "demographic_type": dtype,
                "value": seg,
                "bid_modifier": float(bid_modifier),
                "operation": action_taken,
                "resource_name": resource_name,
            },
        )
    except ToolError:
        raise
    except Exception as ex:
        raise handle_googleads_exception(ex)


# ---------------------------------------------------------------------------
# 3. Why is a campaign not serving?
# ---------------------------------------------------------------------------
_REASON_PT = {
    "CAMPAIGN_REMOVED": "A campanha foi removida.",
    "CAMPAIGN_PAUSED": "A campanha está pausada.",
    "CAMPAIGN_PENDING": "A campanha ainda não começou (data de início no futuro).",
    "CAMPAIGN_ENDED": "A campanha terminou (data final passou).",
    "CAMPAIGN_DRAFT": "A campanha é um rascunho.",
    "BIDDING_STRATEGY_MISCONFIGURED": "A estratégia de lances está mal configurada.",
    "BIDDING_STRATEGY_LIMITED": "A estratégia de lances está limitada (ex.: lance máximo ou meta restritiva demais).",
    "BIDDING_STRATEGY_LEARNING": "A estratégia de lances está em fase de aprendizado.",
    "BIDDING_STRATEGY_CONSTRAINED": "A estratégia de lances está restringida por configurações da campanha.",
    "BUDGET_CONSTRAINED": "O orçamento é o limitador: ele acaba antes de a campanha alcançar todo o tráfego possível.",
    "BUDGET_MISCONFIGURED": "O orçamento está mal configurado.",
    "SEARCH_VOLUME_LIMITED": "O volume de buscas é baixo para o que foi configurado (palavras-chave e segmentação).",
    "AD_GROUPS_PAUSED": "Todos os grupos de anúncios estão pausados.",
    "NO_AD_GROUPS": "A campanha não tem grupos de anúncios.",
    "KEYWORDS_PAUSED": "Todas as palavras-chave estão pausadas.",
    "NO_KEYWORDS": "A campanha não tem palavras-chave.",
    "AD_GROUP_ADS_PAUSED": "Todos os anúncios estão pausados.",
    "NO_AD_GROUP_ADS": "A campanha não tem anúncios.",
    "HAS_ADS_LIMITED_BY_POLICY": "Há anúncios limitados por política.",
    "HAS_ADS_DISAPPROVED": "Há anúncios reprovados.",
    "MOST_ADS_UNDER_REVIEW": "A maioria dos anúncios está em análise.",
    "MISSING_LEAD_FORM_EXTENSION": "Falta o formulário de lead.",
    "MISSING_CALL_EXTENSION": "Falta a extensão de ligação.",
    "LEAD_FORM_EXTENSION_UNDER_REVIEW": "O formulário de lead está em análise.",
    "LEAD_FORM_EXTENSION_DISAPPROVED": "O formulário de lead foi reprovado.",
    "CALL_EXTENSION_UNDER_REVIEW": "A extensão de ligação está em análise.",
    "CALL_EXTENSION_DISAPPROVED": "A extensão de ligação foi reprovada.",
    "HAS_ASSET_GROUPS_DISAPPROVED": "Há grupos de recursos reprovados.",
    "HAS_ASSET_GROUPS_LIMITED_BY_POLICY": "Há grupos de recursos limitados por política.",
    "MOST_ASSET_GROUPS_UNDER_REVIEW": "A maioria dos grupos de recursos está em análise.",
    "NO_ASSET_GROUPS": "A campanha não tem grupos de recursos.",
    "ASSET_GROUPS_PAUSED": "Todos os grupos de recursos estão pausados.",
    "MISSING_LOCATION_TARGETING": "Falta segmentação de local.",
}


def explain_reason(code: str) -> str:
    return _REASON_PT.get(str(code), f"Motivo informado pelo Google: {code}.")


def build_findings(
    campaign: Dict[str, Any],
    metrics_7d: Dict[str, int],
    metrics_30d: Dict[str, int],
    ad_group_status: Dict[str, int],
    ad_status: Dict[str, Any],
    keywords: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Turns the raw campaign data into a list of findings and a likely cause (pure function, easy to test)."""
    findings: List[Dict[str, str]] = []

    def add(severity: str, code: str, message: str) -> None:
        findings.append({"severity": severity, "code": code, "message": message})

    if campaign.get("status") != "ENABLED":
        add("blocker", f"CAMPAIGN_{campaign.get('status')}", f"A campanha está com status {campaign.get('status')}.")
    for reason in campaign.get("primary_status_reasons", []):
        add("blocker" if campaign.get("primary_status") in ("NOT_ELIGIBLE", "PAUSED", "REMOVED", "ENDED", "PENDING", "MISCONFIGURED") else "warning", reason, explain_reason(reason))
    if campaign.get("serving_status") not in ("SERVING", None):
        add("blocker", f"SERVING_{campaign.get('serving_status')}", f"Status de veiculação: {campaign.get('serving_status')}.")

    if ad_group_status.get("total", 0) == 0:
        add("blocker", "NO_AD_GROUPS", explain_reason("NO_AD_GROUPS"))
    elif ad_group_status.get("ENABLED", 0) == 0:
        add("blocker", "AD_GROUPS_PAUSED", explain_reason("AD_GROUPS_PAUSED"))

    if ad_status.get("total", 0) == 0:
        add("blocker", "NO_AD_GROUP_ADS", explain_reason("NO_AD_GROUP_ADS"))
    else:
        if ad_status.get("enabled_and_approved", 0) == 0:
            add("blocker", "NO_APPROVED_ENABLED_ADS", "Nenhum anúncio está ativo e aprovado.")
        if ad_status.get("disapproved", 0):
            add("warning", "HAS_ADS_DISAPPROVED", f"{ad_status['disapproved']} anúncio(s) reprovado(s).")

    if keywords is not None:
        if keywords.get("total", 0) == 0:
            add("warning", "NO_KEYWORDS", explain_reason("NO_KEYWORDS"))
        elif keywords.get("rarely_served", 0) == keywords["total"]:
            add("warning", "ALL_KEYWORDS_RARELY_SERVED", "Todas as palavras-chave estão com volume de busca baixo (RARELY_SERVED).")
        elif keywords.get("rarely_served", 0):
            add("info", "SOME_KEYWORDS_RARELY_SERVED", f"{keywords['rarely_served']} de {keywords['total']} palavras-chave estão com volume de busca baixo (RARELY_SERVED).")

    blockers = [f for f in findings if f["severity"] == "blocker"]
    if blockers:
        likely = "Há bloqueio de configuração: " + " ".join(f["message"] for f in blockers)
    elif metrics_7d.get("impressions", 0) > 0:
        likely = "A campanha está veiculando: tem impressões nos últimos 7 dias."
    else:
        likely = (
            "Nenhum bloqueio de configuração foi encontrado e o Google considera a campanha elegível, mas ela não teve "
            "impressões. As causas mais comuns são volume de busca baixo nas palavras-chave, lances ou orçamento "
            "baixos para o leilão, ou segmentação (local, horário, público) muito restrita."
        )
    return {"findings": findings, "likely_cause": likely}


def _sum(rows: List[Dict[str, Any]], key: str) -> int:
    return int(sum(r.get(key, 0) or 0 for r in rows))


@mcp.tool()
def diagnose_campaign_serving(customer_id: str, campaign_id: Union[str, int]) -> Dict[str, Any]:
    """Explains why a campaign is not serving (or serving little): status, reasons given by Google, budget, ad groups, ads, keywords and recent impressions.

    Read-only. Use it when a campaign shows 0 impressions. Combines Google's own primary status and reasons with
    checks on ad groups, ad approval and keyword search volume, and returns findings plus the likely cause (in Portuguese).

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: The campaign ID.

    Returns:
        Dict with the campaign summary, impressions (7 and 30 days), counts of ad groups/ads/keywords, findings and likely_cause.
    """
    cid = clean_customer_id(customer_id)
    camp_id = _numeric_id(campaign_id)

    rows = search(
        customer_id=cid,
        resource="campaign",
        fields=[
            "campaign.id",
            "campaign.name",
            "campaign.status",
            "campaign.primary_status",
            "campaign.primary_status_reasons",
            "campaign.serving_status",
            "campaign.bidding_strategy_type",
            "campaign.advertising_channel_type",
            "campaign_budget.amount_micros",
        ],
        conditions=[f"campaign.id = {camp_id}"],
    )
    if not rows:
        raise ToolError(f"Campaign {camp_id} not found in customer {cid}.")
    row = rows[0]
    campaign = {
        "id": str(row["campaign.id"]),
        "name": row["campaign.name"],
        "status": row["campaign.status"],
        "primary_status": row["campaign.primary_status"],
        "primary_status_reasons": [str(r) for r in (row.get("campaign.primary_status_reasons") or [])],
        "serving_status": row["campaign.serving_status"],
        "bidding_strategy_type": row["campaign.bidding_strategy_type"],
        "channel_type": row["campaign.advertising_channel_type"],
        "daily_budget": (row.get("campaign_budget.amount_micros") or 0) / 1_000_000,
    }

    def metrics(period: str) -> Dict[str, int]:
        data = search(
            customer_id=cid,
            resource="campaign",
            fields=["metrics.impressions", "metrics.clicks", "metrics.cost_micros"],
            conditions=[f"campaign.id = {camp_id}", f"segments.date DURING {period}"],
        )
        return {
            "impressions": _sum(data, "metrics.impressions"),
            "clicks": _sum(data, "metrics.clicks"),
            "cost": round(_sum(data, "metrics.cost_micros") / 1_000_000, 2),
        }

    m7, m30 = metrics("LAST_7_DAYS"), metrics("LAST_30_DAYS")

    groups = search(
        customer_id=cid,
        resource="ad_group",
        fields=["ad_group.id", "ad_group.status"],
        conditions=[f"campaign.id = {camp_id}", "ad_group.status != 'REMOVED'"],
    )
    group_counts = dict(collections.Counter(g["ad_group.status"] for g in groups))
    group_counts["total"] = len(groups)

    ads = search(
        customer_id=cid,
        resource="ad_group_ad",
        fields=["ad_group_ad.status", "ad_group_ad.policy_summary.approval_status"],
        conditions=[f"campaign.id = {camp_id}", "ad_group_ad.status != 'REMOVED'"],
    )
    ad_counts = {
        "total": len(ads),
        "enabled_and_approved": sum(
            1
            for a in ads
            if a["ad_group_ad.status"] == "ENABLED"
            and a["ad_group_ad.policy_summary.approval_status"] in ("APPROVED", "APPROVED_LIMITED")
        ),
        "disapproved": sum(1 for a in ads if a["ad_group_ad.policy_summary.approval_status"] == "DISAPPROVED"),
    }

    keyword_counts: Optional[Dict[str, Any]] = None
    if campaign["channel_type"] == "SEARCH":
        kws = search(
            customer_id=cid,
            resource="ad_group_criterion",
            fields=["ad_group_criterion.status", "ad_group_criterion.system_serving_status"],
            conditions=[
                f"campaign.id = {camp_id}",
                "ad_group_criterion.type = 'KEYWORD'",
                "ad_group_criterion.negative = FALSE",
                "ad_group_criterion.status != 'REMOVED'",
            ],
        )
        keyword_counts = {
            "total": len(kws),
            "rarely_served": sum(1 for k in kws if k["ad_group_criterion.system_serving_status"] == "RARELY_SERVED"),
            "eligible": sum(1 for k in kws if k["ad_group_criterion.system_serving_status"] == "ELIGIBLE"),
        }

    verdict = build_findings(campaign, m7, m30, group_counts, ad_counts, keyword_counts)
    return {
        "customer_id": cid,
        "campaign": campaign,
        "impressions": {"last_7_days": m7, "last_30_days": m30},
        "ad_groups": group_counts,
        "ads": ad_counts,
        "keywords": keyword_counts,
        **verdict,
    }
