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

"""Tools for recommendation auto-apply subscriptions and audience name resolution."""

from typing import Any, Dict, List, Optional, Union
from fastmcp.exceptions import ToolError
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.search import search
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    handle_googleads_exception,
    get_enum_class,
)

_SUB_FIELDS = [
    "recommendation_subscription.resource_name",
    "recommendation_subscription.type",
    "recommendation_subscription.status",
    "recommendation_subscription.modify_date_time",
]
_VALID_STATUSES = ("ENABLED", "PAUSED")


UNKNOWN_TYPE = "UNKNOWN"
_UNKNOWN_REASON = (
    "the API reports this subscription with type UNKNOWN (its resource name is literally '.../UNKNOWN'), "
    "so it cannot be read or changed through the API; change it in the Google Ads UI "
    "(Recommendations > Auto-apply)"
)


def type_from_resource_name(resource_name: str) -> str:
    """The recommendation type is the last segment of the resource name (e.g. 'KEYWORD').

    Some subscriptions come back as 'UNKNOWN' (types the API cannot represent); those cannot be mutated.
    """
    return str(resource_name).rsplit("/", 1)[-1].strip()


def parse_audience_id(value: Union[str, int]) -> int:
    """Parses '80103', 80103 or 'uservertical::80103' (any 'prefix::id') into an int."""
    raw = str(value).strip()
    if "::" in raw:
        raw = raw.rsplit("::", 1)[-1]
    if not raw.isdigit():
        raise ToolError(f"Invalid audience ID '{value}'. Use a number or the 'uservertical::ID' form.")
    return int(raw)


def _read_subscriptions(cid: str) -> List[Dict[str, Any]]:
    rows = search(customer_id=cid, fields=_SUB_FIELDS, resource="recommendation_subscription")
    subs = []
    for row in rows:
        resource_name = row["recommendation_subscription.resource_name"]
        subs.append(
            {
                "type": type_from_resource_name(resource_name),
                "status": row["recommendation_subscription.status"],
                "resource_name": resource_name,
                "modified": row.get("recommendation_subscription.modify_date_time"),
            }
        )
    return subs


@mcp.tool()
def list_recommendation_subscriptions(customer_id: str) -> Dict[str, Any]:
    """Lists the recommendation auto-apply subscriptions of an account (which recommendation types Google applies automatically).

    A subscription with status ENABLED means Google AUTO-APPLIES that type of recommendation; PAUSED means it does not.
    The returned 'type' is the type name (e.g. 'KEYWORD', 'SEARCH_PARTNERS_OPT_IN', 'TARGET_CPA_OPT_IN').
    Subscriptions of type 'UNKNOWN' ('api_manageable': false) are reported by the API but cannot be changed through it;
    they must be changed in the Google Ads UI.

    Args:
        customer_id: The Google Ads customer ID.

    Returns:
        Dict with the subscriptions, how many have auto-apply enabled and how many of those cannot be changed via API.
    """
    cid = clean_customer_id(customer_id)
    subs = _read_subscriptions(cid)
    for s in subs:
        s["api_manageable"] = s["type"].upper() != UNKNOWN_TYPE
    enabled = [s for s in subs if s["status"] == "ENABLED"]
    result = {
        "customer_id": cid,
        "auto_apply_enabled_count": len(enabled),
        "enabled_not_manageable_via_api": sum(1 for s in enabled if not s["api_manageable"]),
        "total": len(subs),
        "subscriptions": subs,
    }
    if result["enabled_not_manageable_via_api"]:
        result["note"] = (
            f"{result['enabled_not_manageable_via_api']} enabled subscription(s) have type UNKNOWN and can only be "
            "turned off in the Google Ads UI (Recommendations > Auto-apply)."
        )
    return result


@mcp.tool()
def set_recommendation_subscription_status(
    customer_id: str,
    status: str,
    recommendation_types: Optional[List[str]] = None,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Turns recommendation auto-apply ON (ENABLED) or OFF (PAUSED) for an account, per recommendation type.

    Use list_recommendation_subscriptions first to see the current state and the type names.
    Subscriptions of type 'UNKNOWN' cannot be changed through the API: they are reported in 'skipped' and must be
    changed in the Google Ads UI. So 'ALL' turns off every API-manageable type, which may not be the whole account.

    Args:
        customer_id: The Google Ads customer ID.
        status: 'PAUSED' to turn auto-apply OFF, 'ENABLED' to turn it ON.
        recommendation_types: Type names to change (e.g. ['KEYWORD', 'TARGET_CPA_OPT_IN']). If omitted or ['ALL'],
                              applies to every existing subscription (e.g. turn OFF all auto-apply on the account).
        validate_only: If True, only validates without applying changes (dry-run).

    Returns:
        Dict listing what was changed, what was already in the requested state and what was skipped.
    """
    cid = clean_customer_id(customer_id)
    target = str(status).strip().upper()
    if target not in _VALID_STATUSES:
        raise ToolError(f"Invalid status '{status}'. Use 'ENABLED' (auto-apply ON) or 'PAUSED' (auto-apply OFF).")

    requested = None
    if recommendation_types and [t.strip().upper() for t in recommendation_types] != ["ALL"]:
        requested = [t.strip().upper() for t in recommendation_types if t.strip()]

    try:
        all_subs = _read_subscriptions(cid)
        unknown_subs = [s for s in all_subs if s["type"].upper() == UNKNOWN_TYPE]
        existing = {s["type"].upper(): s for s in all_subs if s["type"].upper() != UNKNOWN_TYPE}
        wanted = list(existing) if requested is None else [t for t in requested if t != UNKNOWN_TYPE]

        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        status_enum = getattr(get_enum_class(client, "RecommendationSubscriptionStatusEnum"), target)
        type_enum_cls = get_enum_class(client, "RecommendationTypeEnum")

        operations, changed, unchanged, skipped = [], [], [], []
        for rec_type in wanted:
            current = existing.get(rec_type)
            if current:
                if current["status"] == target:
                    unchanged.append(rec_type)
                    continue
                op = utils.get_googleads_type("RecommendationSubscriptionOperation", customer_id=cid)
                op.update.resource_name = current["resource_name"]
                op.update.status = status_enum
                op.update_mask.paths.append("status")
                operations.append(op)
                changed.append({"type": rec_type, "from": current["status"], "to": target})
            elif target == "ENABLED":
                type_value = getattr(type_enum_cls, rec_type, None)
                if type_value is None:
                    skipped.append({"type": rec_type, "reason": "unknown recommendation type"})
                    continue
                op = utils.get_googleads_type("RecommendationSubscriptionOperation", customer_id=cid)
                op.create.type_ = type_value
                op.create.status = status_enum
                operations.append(op)
                changed.append({"type": rec_type, "from": "NOT_SUBSCRIBED", "to": target})
            else:
                skipped.append({"type": rec_type, "reason": "no subscription exists (auto-apply is already off)"})

        # UNKNOWN subscriptions can't be mutated via API: report the ones that are not already in the target state
        if requested is None or UNKNOWN_TYPE in (requested or []):
            pending_unknown = [s for s in unknown_subs if s["status"] != target]
            if pending_unknown:
                skipped.append(
                    {"type": UNKNOWN_TYPE, "count": len(pending_unknown), "reason": _UNKNOWN_REASON}
                )

        if operations:
            service = utils.get_googleads_service("RecommendationSubscriptionService", customer_id=cid)
            if validate_only:
                service.mutate_recommendation_subscription(
                    request={"customer_id": cid, "operations": operations, "validate_only": True}
                )
            else:
                service.mutate_recommendation_subscription(customer_id=cid, operations=operations)

        return {
            "success": True,
            "action": "set_recommendation_subscription_status",
            "validate_only": validate_only,
            "customer_id": cid,
            "target_status": target,
            "changed": changed,
            "unchanged": unchanged,
            "skipped": skipped,
        }
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def resolve_audience_names(
    ids: List[Union[str, int]],
    customer_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Translates audience IDs into readable names (affinity / in-market, detailed demographics, life events).

    Accepts plain numbers or the form returned by reports, such as 'uservertical::80103'.
    The names come from the Google Ads taxonomy (user_interest, detailed_demographic, life_event).

    Args:
        ids: Audience IDs, e.g. ['uservertical::80103', 80104, '30001'].
        customer_id: Any accessible customer ID (the taxonomy is global). Defaults to the MCC configured on the server.

    Returns:
        Dict with 'resolved' (id -> list of {name, source}) and 'not_found'.
    """
    parsed = [parse_audience_id(i) for i in ids]
    if not parsed:
        raise ToolError("Provide at least one audience ID.")

    cid = clean_customer_id(customer_id) if customer_id else utils._get_login_customer_id()
    if not cid:
        raise ToolError("customer_id is required (no default MCC configured on the server).")
    cid = clean_customer_id(cid)

    id_list = ",".join(str(i) for i in sorted(set(parsed)))
    sources = (
        ("user_interest", "user_interest.user_interest_id", "user_interest.name"),
        ("detailed_demographic", "detailed_demographic.id", "detailed_demographic.name"),
        ("life_event", "life_event.id", "life_event.name"),
    )

    resolved: Dict[str, List[Dict[str, str]]] = {}
    for resource, id_field, name_field in sources:
        rows = search(
            customer_id=cid,
            fields=[id_field, name_field],
            resource=resource,
            conditions=[f"{id_field} IN ({id_list})"],
        )
        for row in rows:
            resolved.setdefault(str(row[id_field]), []).append({"name": row[name_field], "source": resource})

    return {
        "resolved": resolved,
        "not_found": [str(i) for i in sorted(set(parsed)) if str(i) not in resolved],
    }
