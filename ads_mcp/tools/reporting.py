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

"""Reporting, Intelligence, and Audit tools for Google Ads."""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta, timezone
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    micros_to_currency,
)


@mcp.tool()
def get_search_terms_report(
    customer_id: str,
    campaign_id: Optional[Union[str, int]] = None,
    date_range: str = "LAST_30_DAYS",
    only_unconverted: bool = False,
    min_cost: float = 0.0,
    limit: int = 50,
) -> Dict[str, Any]:
    """Retrieves actual user search terms that triggered ads, with performance and waste metrics.

    Essential for negative keyword discovery and identifying wasted spend.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: Optional campaign ID to filter terms by a specific campaign.
        date_range: Date range (e.g. 'LAST_7_DAYS', 'LAST_14_DAYS', 'LAST_30_DAYS', 'THIS_MONTH').
        only_unconverted: If True, only returns search terms that generated zero conversions (wasted spend).
        min_cost: Minimum spend in currency units to filter significant terms (e.g. 10.0 for >= R$10 / $10).
        limit: Maximum number of search terms to return (default 50, max 200).

    Returns:
        Dict with status, list of search terms, cost, clicks, conversions, and campaign/ad group details.
    """
    cid = clean_customer_id(customer_id)
    where_clauses = [f"segments.date DURING {date_range.upper().strip()}"]

    if campaign_id:
        clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
        where_clauses.append(f"campaign.id = {clean_c_id}")

    if only_unconverted:
        where_clauses.append("metrics.conversions = 0")

    if min_cost > 0:
        min_cost_micros = int(min_cost * 1_000_000)
        where_clauses.append(f"metrics.cost_micros >= {min_cost_micros}")

    where_str = " AND ".join(where_clauses)
    query_limit = min(max(1, limit), 200)

    query = f"""
        SELECT
            search_term_view.search_term,
            search_term_view.status,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            metrics.clicks,
            metrics.impressions,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM search_term_view
        WHERE {where_str}
        ORDER BY metrics.cost_micros DESC
        LIMIT {query_limit}
    """

    try:
        ga_service = utils.get_googleads_service("GoogleAdsService", customer_id=cid)
        response = ga_service.search(customer_id=cid, query=query)

        rows = []
        for row in response:
            cost_micros = row.metrics.cost_micros
            avg_cpc_micros = row.metrics.average_cpc
            rows.append({
                "search_term": row.search_term_view.search_term,
                "status": row.search_term_view.status.name if hasattr(row.search_term_view.status, "name") else str(row.search_term_view.status),
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "ad_group_id": row.ad_group.id,
                "ad_group_name": row.ad_group.name,
                "clicks": row.metrics.clicks,
                "impressions": row.metrics.impressions,
                "cost": micros_to_currency(cost_micros),
                "cost_micros": cost_micros,
                "conversions": row.metrics.conversions,
                "ctr": f"{row.metrics.ctr * 100:.2f}%",
                "average_cpc": micros_to_currency(avg_cpc_micros),
            })

        return {
            "success": True,
            "action": "get_search_terms_report",
            "customer_id": cid,
            "count": len(rows),
            "date_range": date_range,
            "only_unconverted": only_unconverted,
            "search_terms": rows,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def get_keyword_quality_score_report(
    customer_id: str,
    campaign_id: Optional[Union[str, int]] = None,
    ad_group_id: Optional[Union[str, int]] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Audits Quality Score (1-10) and its 3 component diagnostic pillars for active keywords.

    Pillars:
    - Expected CTR (search_predicted_ctr)
    - Ad Relevance (creative_quality_score)
    - Landing Page Experience (post_click_quality_score)

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: Optional campaign ID filter.
        ad_group_id: Optional ad group ID filter.
        limit: Maximum number of keywords to return (default 50, max 200).

    Returns:
        Dict with status and keyword diagnostic list with score and component evaluations.
    """
    cid = clean_customer_id(customer_id)
    where_clauses = [
        "ad_group_criterion.status = 'ENABLED'",
        "campaign.status = 'ENABLED'",
        "ad_group.status = 'ENABLED'",
    ]

    if campaign_id:
        clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
        where_clauses.append(f"campaign.id = {clean_c_id}")

    if ad_group_id:
        clean_ag_id = str(ad_group_id).replace("-", "").strip().removeprefix(f"customers/{cid}/adGroups/")
        where_clauses.append(f"ad_group.id = {clean_ag_id}")

    where_str = " AND ".join(where_clauses)
    query_limit = min(max(1, limit), 200)

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group_criterion.criterion_id,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.quality_info.creative_quality_score,
            ad_group_criterion.quality_info.post_click_quality_score,
            ad_group_criterion.quality_info.search_predicted_ctr
        FROM keyword_view
        WHERE {where_str}
        LIMIT {query_limit}
    """

    try:
        ga_service = utils.get_googleads_service("GoogleAdsService", customer_id=cid)
        response = ga_service.search(customer_id=cid, query=query)

        rows = []
        for row in response:
            q = row.ad_group_criterion.quality_info
            qs = q.quality_score if q and q.quality_score > 0 else None

            def format_score_enum(val):
                return val.name if hasattr(val, "name") else str(val)

            rows.append({
                "keyword": row.ad_group_criterion.keyword.text,
                "match_type": row.ad_group_criterion.keyword.match_type.name if hasattr(row.ad_group_criterion.keyword.match_type, "name") else str(row.ad_group_criterion.keyword.match_type),
                "quality_score": qs,
                "expected_ctr": format_score_enum(q.search_predicted_ctr) if q else None,
                "ad_relevance": format_score_enum(q.creative_quality_score) if q else None,
                "landing_page_experience": format_score_enum(q.post_click_quality_score) if q else None,
                "campaign_name": row.campaign.name,
                "campaign_id": row.campaign.id,
                "ad_group_name": row.ad_group.name,
                "ad_group_id": row.ad_group.id,
                "criterion_id": row.ad_group_criterion.criterion_id,
            })

        return {
            "success": True,
            "action": "get_keyword_quality_score_report",
            "customer_id": cid,
            "count": len(rows),
            "keywords": rows,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def get_campaign_change_history(
    customer_id: str,
    campaign_id: Optional[Union[str, int]] = None,
    days: int = 7,
    limit: int = 50,
) -> Dict[str, Any]:
    """Retrieves recent audit log changes (budget changes, paused ads, new keywords, etc.) from change_event.

    Uses Google's change_event resource with correctly formatted GAQL timestamps and campaign filters.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: Optional campaign ID to filter changes for a specific campaign.
        days: Number of days back to look for changes (1 to 30, default 7).
        limit: Maximum number of change records to return (default 50, max 200).

    Returns:
        Dict with status and chronological change event records.
    """
    cid = clean_customer_id(customer_id)
    lookback_days = min(max(1, days), 30)

    start_date = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d %H:%M:%S")

    where_clauses = [f"change_event.change_date_time >= '{start_date}'"]
    if campaign_id:
        clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
        where_clauses.append(f"change_event.campaign = 'customers/{cid}/campaigns/{clean_c_id}'")

    where_str = " AND ".join(where_clauses)
    query_limit = min(max(1, limit), 200)

    query = f"""
        SELECT
            change_event.change_date_time,
            change_event.change_resource_type,
            change_event.change_resource_name,
            change_event.user_email,
            change_event.client_type,
            change_event.resource_change_operation,
            change_event.changed_fields,
            change_event.campaign,
            change_event.ad_group
        FROM change_event
        WHERE {where_str}
        ORDER BY change_event.change_date_time DESC
        LIMIT {query_limit}
    """

    try:
        ga_service = utils.get_googleads_service("GoogleAdsService", customer_id=cid)
        response = ga_service.search(customer_id=cid, query=query)

        rows = []
        for row in response:
            ce = row.change_event
            rows.append({
                "timestamp": ce.change_date_time,
                "user_email": ce.user_email,
                "resource_type": ce.change_resource_type.name if hasattr(ce.change_resource_type, "name") else str(ce.change_resource_type),
                "operation": ce.resource_change_operation.name if hasattr(ce.resource_change_operation, "name") else str(ce.resource_change_operation),
                "changed_fields": list(ce.changed_fields.paths) if hasattr(ce.changed_fields, "paths") else [],
                "resource_name": ce.change_resource_name,
                "campaign": ce.campaign,
                "ad_group": ce.ad_group,
                "client_type": ce.client_type.name if hasattr(ce.client_type, "name") else str(ce.client_type),
            })

        return {
            "success": True,
            "action": "get_campaign_change_history",
            "customer_id": cid,
            "count": len(rows),
            "lookback_days": lookback_days,
            "changes": rows,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def get_campaign_competitive_share(
    customer_id: str,
    campaign_id: Optional[Union[str, int]] = None,
    date_range: str = "LAST_30_DAYS",
) -> Dict[str, Any]:
    """Retrieves Competitive Impression Share metrics (Impression Share, Budget Lost, Rank Lost, Top Share).

    Shows how much impression volume the campaign won vs lost to budget limits or poor ad rank.

    Args:
        customer_id: The Google Ads customer ID.
        campaign_id: Optional campaign ID filter.
        date_range: Date range (e.g. 'LAST_7_DAYS', 'LAST_14_DAYS', 'LAST_30_DAYS', 'THIS_MONTH').

    Returns:
        Dict with status and competitive impression share metrics per campaign.
    """
    cid = clean_customer_id(customer_id)
    where_clauses = [
        f"segments.date DURING {date_range.upper().strip()}",
        "campaign.status = 'ENABLED'",
    ]

    if campaign_id:
        clean_c_id = str(campaign_id).replace("-", "").strip().removeprefix(f"customers/{cid}/campaigns/")
        where_clauses.append(f"campaign.id = {clean_c_id}")

    where_str = " AND ".join(where_clauses)

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share,
            metrics.search_top_impression_share,
            metrics.search_absolute_top_impression_share,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros
        FROM campaign
        WHERE {where_str}
        ORDER BY metrics.cost_micros DESC
    """

    try:
        ga_service = utils.get_googleads_service("GoogleAdsService", customer_id=cid)
        response = ga_service.search(customer_id=cid, query=query)

        rows = []
        for row in response:
            def format_share(val):
                if val is None or val < 0:
                    return "< 10%"
                return f"{val * 100:.1f}%"

            rows.append({
                "campaign_id": row.campaign.id,
                "campaign_name": row.campaign.name,
                "search_impression_share": format_share(row.metrics.search_impression_share),
                "budget_lost_impression_share": format_share(row.metrics.search_budget_lost_impression_share),
                "rank_lost_impression_share": format_share(row.metrics.search_rank_lost_impression_share),
                "top_impression_share": format_share(row.metrics.search_top_impression_share),
                "absolute_top_impression_share": format_share(row.metrics.search_absolute_top_impression_share),
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost": micros_to_currency(row.metrics.cost_micros),
            })

        return {
            "success": True,
            "action": "get_campaign_competitive_share",
            "customer_id": cid,
            "count": len(rows),
            "date_range": date_range,
            "campaigns": rows,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)
