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

"""Tools for managing Campaign Budgets in Google Ads."""

from typing import Any, Dict, Optional, Union
from ads_mcp.coordinator import mcp
import ads_mcp.utils as utils
from ads_mcp.tools.mutate_utils import (
    clean_customer_id,
    parse_money_to_micros,
    micros_to_currency,
    handle_googleads_exception,
    format_mutate_response,
    get_enum_class,
    get_enum_value,
)


@mcp.tool()
def create_campaign_budget(
    customer_id: str,
    name: str,
    amount: Union[float, int, str],
    delivery_method: str = "STANDARD",
    explicitly_shared: bool = False,
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Creates a new campaign budget in Google Ads.

    Args:
        customer_id: The Google Ads customer ID (e.g. '1234567890' or '123-456-7890').
        name: Name of the budget (must be unique if shared).
        amount: Daily budget amount in currency units (e.g. 50.00 or '50.00'). Automatically converted to micros.
        delivery_method: Delivery method, defaults to 'STANDARD'.
        explicitly_shared: Whether this budget can be shared across multiple campaigns (default False).
        validate_only: If True, only validates the request without executing (dry-run).

    Returns:
        Dict with success status, created resource name, and budget details.
    """
    cid = clean_customer_id(customer_id)
    amount_micros = parse_money_to_micros(amount)

    try:
        campaign_budget_service = utils.get_googleads_service("CampaignBudgetService", customer_id=cid)
        budget_op = utils.get_googleads_type("CampaignBudgetOperation", customer_id=cid)
        budget = budget_op.create

        budget.name = name
        budget.amount_micros = amount_micros
        budget.explicitly_shared = explicitly_shared

        client = utils.get_googleads_client(login_customer_id=utils.get_login_customer_id_for_customer(cid))
        delivery_enum = getattr(get_enum_class(client, "BudgetDeliveryMethodEnum"), delivery_method.upper(), None)
        if delivery_enum:
            budget.delivery_method = delivery_enum

        if validate_only:
            response = campaign_budget_service.mutate_campaign_budgets(
                request={
                    "customer_id": cid,
                    "operations": [budget_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=cid,
                operations=[budget_op],
            )

        results = response.results if not validate_only else [{"resource_name": f"customers/{cid}/campaignBudgets/dry-run"}]
        return format_mutate_response(
            action="create_campaign_budget",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "name": name,
                "amount": micros_to_currency(amount_micros),
                "amount_micros": amount_micros,
                "explicitly_shared": explicitly_shared,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def update_campaign_budget(
    customer_id: str,
    budget_id: Union[str, int],
    amount: Union[float, int, str],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Updates the daily amount of an existing campaign budget.

    Args:
        customer_id: The Google Ads customer ID.
        budget_id: The Campaign Budget ID or full resource name ('customers/.../campaignBudgets/...').
        amount: New daily budget amount in currency units (e.g. 100.00). Automatically converted to micros.
        validate_only: If True, only validates without applying changes.

    Returns:
        Dict with success status and updated budget details.
    """
    cid = clean_customer_id(customer_id)
    amount_micros = parse_money_to_micros(amount)

    clean_budget_id = str(budget_id).strip()
    if clean_budget_id.startswith("customers/"):
        resource_name = clean_budget_id
    else:
        resource_name = f"customers/{cid}/campaignBudgets/{clean_budget_id}"

    try:
        campaign_budget_service = utils.get_googleads_service("CampaignBudgetService", customer_id=cid)
        budget_op = utils.get_googleads_type("CampaignBudgetOperation", customer_id=cid)
        
        budget = budget_op.update
        budget.resource_name = resource_name
        budget.amount_micros = amount_micros
        
        # Set field mask
        budget_op.update_mask.paths.append("amount_micros")

        if validate_only:
            response = campaign_budget_service.mutate_campaign_budgets(
                request={
                    "customer_id": cid,
                    "operations": [budget_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=cid,
                operations=[budget_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="update_campaign_budget",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "resource_name": resource_name,
                "new_amount": micros_to_currency(amount_micros),
                "new_amount_micros": amount_micros,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)


@mcp.tool()
def remove_campaign_budget(
    customer_id: str,
    budget_id: Union[str, int],
    validate_only: bool = False,
) -> Dict[str, Any]:
    """Removes an unused/orphan campaign budget from the account.

    NOTE: Google Ads allows removing a budget ONLY if it is not currently associated with any active campaign.

    Args:
        customer_id: The Google Ads customer ID.
        budget_id: The Campaign Budget ID or full resource name ('customers/.../campaignBudgets/...').
        validate_only: If True, only validates without applying changes.

    Returns:
        Dict with success status and removed budget details.
    """
    cid = clean_customer_id(customer_id)
    clean_b_id = str(budget_id).replace("-", "").strip()
    if clean_b_id.startswith("customers/"):
        resource_name = clean_b_id
    else:
        resource_name = f"customers/{cid}/campaignBudgets/{clean_b_id}"

    try:
        campaign_budget_service = utils.get_googleads_service("CampaignBudgetService", customer_id=cid)
        budget_op = utils.get_googleads_type("CampaignBudgetOperation", customer_id=cid)
        budget_op.remove = resource_name

        if validate_only:
            response = campaign_budget_service.mutate_campaign_budgets(
                request={
                    "customer_id": cid,
                    "operations": [budget_op],
                    "validate_only": True,
                }
            )
        else:
            response = campaign_budget_service.mutate_campaign_budgets(
                customer_id=cid,
                operations=[budget_op],
            )

        results = response.results if not validate_only else [{"resource_name": resource_name}]
        return format_mutate_response(
            action="remove_campaign_budget",
            results=results,
            validate_only=validate_only,
            extra={
                "customer_id": cid,
                "removed_resource_name": resource_name,
            },
        )
    except Exception as ex:
        raise handle_googleads_exception(ex)

