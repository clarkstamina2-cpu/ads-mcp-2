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

"""Tools for Keyword Planning and Research using the Google Ads Keyword Planner API."""

from typing import Any, Dict, List, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    micros_to_currency,
)


@mcp.tool()
def generate_keyword_ideas(
    customer_id: str,
    keywords: Optional[List[str]] = None,
    url: Optional[str] = None,
    language_code_or_id: Union[str, int] = "pt",
    geo_target_constants: Optional[List[Union[str, int]]] = None,
    include_adult_keywords: bool = False,
    page_size: int = 25,
) -> Dict[str, Any]:
    """Generates keyword ideas, monthly search volumes, competition levels, and CPC estimates.

    Uses Google's official KeywordPlanIdeaService (Keyword Planner) to provide market demand data.

    Args:
        customer_id: The Google Ads customer ID.
        keywords: Optional seed keyword list (e.g. ['marketing medico', 'clinica medica']).
        url: Optional webpage/site URL to extract keyword ideas from (e.g. 'https://stamina.digital').
        language_code_or_id: Language code (e.g. 'pt', 'en', 'es') or constant ID (default 'pt' / 1014).
        geo_target_constants: Geographic location IDs to target (default [2076] for Brazil).
        include_adult_keywords: Whether to include adult keywords (default False).
        page_size: Maximum number of keyword suggestions to return (default 25, max 100).

    Returns:
        Dict with status, count, and list of keyword ideas with search volume, competition, and top-of-page CPC range.
    """
    if not keywords and not url:
        raise ValueError("At least one seed keyword or a website URL must be provided.")

    cid = clean_customer_id(customer_id)

    lang_map = {
        "pt": 1014, "en": 1000, "es": 1003, "fr": 1002, "de": 1001, "it": 1004,
    }
    clean_l = str(language_code_or_id).strip().lower()
    if clean_l.startswith("languageconstants/"):
        lang_rn = clean_l
    elif clean_l in lang_map:
        lang_rn = f"languageConstants/{lang_map[clean_l]}"
    elif clean_l.isdigit():
        lang_rn = f"languageConstants/{clean_l}"
    else:
        lang_rn = "languageConstants/1014"

    geo_rns = []
    if geo_target_constants:
        for g in geo_target_constants:
            cg = str(g).strip().removeprefix("geoTargetConstants/")
            geo_rns.append(f"geoTargetConstants/{cg}")
    else:
        geo_rns = ["geoTargetConstants/2076"]  # Brazil default

    try:
        idea_service = utils.get_googleads_service("KeywordPlanIdeaService", customer_id=cid)
        request = utils.get_googleads_type("GenerateKeywordIdeasRequest", customer_id=cid)

        request.customer_id = cid
        request.language = lang_rn
        request.geo_target_constants.extend(geo_rns)
        request.include_adult_keywords = include_adult_keywords

        # Set seeds
        clean_kws = [k.strip() for k in keywords if str(k).strip()] if keywords else []
        clean_url = url.strip() if url else None

        if clean_kws and clean_url:
            request.keyword_and_url_seed.keywords.extend(clean_kws)
            request.keyword_and_url_seed.url = clean_url
        elif clean_kws:
            request.keyword_seed.keywords.extend(clean_kws)
        elif clean_url:
            request.url_seed.url = clean_url

        response = idea_service.generate_keyword_ideas(request=request)

        ideas = []
        limit = min(max(1, page_size), 100)

        for idea in response:
            m = idea.keyword_idea_metrics
            competition_name = None
            if m and hasattr(m, "competition"):
                competition_name = getattr(m.competition, "name", str(m.competition))

            ideas.append({
                "keyword": idea.text,
                "avg_monthly_searches": getattr(m, "avg_monthly_searches", 0) if m else 0,
                "competition": competition_name,
                "competition_index": getattr(m, "competition_index", 0) if m else 0,
                "low_top_of_page_bid": micros_to_currency(m.low_top_of_page_bid_micros) if (m and m.low_top_of_page_bid_micros) else None,
                "high_top_of_page_bid": micros_to_currency(m.high_top_of_page_bid_micros) if (m and m.high_top_of_page_bid_micros) else None,
            })

            if len(ideas) >= limit:
                break

        return {
            "success": True,
            "action": "generate_keyword_ideas",
            "customer_id": cid,
            "count": len(ideas),
            "seed_keywords": clean_kws,
            "seed_url": clean_url,
            "language": lang_rn,
            "geo_targets": geo_rns,
            "ideas": ideas,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)
