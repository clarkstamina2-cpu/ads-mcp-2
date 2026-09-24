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

"""Tools for exposing simple, core API methods to the MCP server."""

from typing import Any, Dict, List, Optional
from ads_mcp.coordinator import mcp
from mcp.types import ToolAnnotations

import ads_mcp.utils as utils


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_accessible_customers() -> List[str]:
    """Returns ids of customers directly accessible by the user authenticating the call.

    Use this tool to discover root/manager customer IDs.
    To see all client accounts with their names and IDs, use list_client_accounts.

    Returns:
        List[str]: A list of customer IDs.
    """
    ga_service = utils.get_googleads_service("CustomerService")
    accessible_customers = ga_service.list_accessible_customers()
    return [
        cust_rn.removeprefix("customers/")
        for cust_rn in accessible_customers.resource_names
    ]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
def list_client_accounts(
    manager_customer_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Returns all active client accounts under the accessible MCCs with their descriptive names and IDs.

    Use this tool FIRST when you need to know which client accounts exist, their names,
    and their customer IDs to perform reports and queries.

    Args:
        manager_customer_id: Optional manager ID (MCC) to filter accounts. If omitted,
                              lists accounts across all accessible MCCs.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing account id, name, manager status, and parent MCC.
    """
    if manager_customer_id:
        target_mccs = [str(manager_customer_id).replace("-", "").strip()]
    else:
        target_mccs = list_accessible_customers()

    accounts: List[Dict[str, Any]] = []
    seen_ids = set()

    for mcc_id in target_mccs:
        try:
            ga_service = utils.get_googleads_service(
                "GoogleAdsService", login_customer_id=mcc_id
            )
            query = (
                "SELECT customer_client.client_customer, "
                "customer_client.descriptive_name, "
                "customer_client.manager, "
                "customer_client.status "
                "FROM customer_client "
                "WHERE customer_client.status = 'ENABLED'"
            )
            response = ga_service.search(customer_id=mcc_id, query=query)
            for row in response:
                cc = row.customer_client
                cid = cc.client_customer.removeprefix("customers/")
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    utils._account_mcc_cache[cid] = mcc_id
                    accounts.append({
                        "customer_id": cid,
                        "name": cc.descriptive_name,
                        "is_manager": cc.manager,
                        "status": str(cc.status),
                        "managing_mcc_id": mcc_id,
                    })
        except Exception as e:
            utils.logger.warning(f"Could not list accounts for MCC {mcc_id}: {e}")

    return accounts
