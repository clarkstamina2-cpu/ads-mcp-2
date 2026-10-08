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

"""Unit tests validating the 2026-10-08 connector improvements and new tools."""

import unittest
from unittest.mock import MagicMock, patch
from fastmcp.exceptions import ToolError

from ads_mcp.tools import assets, targeting, planner, search


class TestValidation20261008(unittest.TestCase):
    """Rigorous validation test suite for new tools and log fixes."""

    # -------------------------------------------------------------
    # 1. PMax Signals: add_asset_group_signals & remove_asset_group_signal
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_add_asset_group_signals_search_themes(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/assetGroupSignals/101~555")]
        mock_service.mutate_asset_group_signals.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = assets.add_asset_group_signals(
            customer_id="123",
            asset_group_id="101",
            search_themes=["energia solar", "placa solar"],
            validate_only=False,
        )

        self.assertTrue(res["success"])
        self.assertEqual(len(mock_service.mutate_asset_group_signals.call_args[1]["operations"]), 2)
        self.assertEqual(res["search_themes"], ["energia solar", "placa solar"])

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_remove_asset_group_signal(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/assetGroupSignals/101~999")]
        mock_service.mutate_asset_group_signals.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = assets.remove_asset_group_signal(
            customer_id="123",
            asset_group_id="101",
            criterion_id="999",
            validate_only=False,
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.remove, "customers/123/assetGroupSignals/101~999")

    # -------------------------------------------------------------
    # 2. PMax Asset Group Links: link & unlink
    # -------------------------------------------------------------
    @patch("ads_mcp.tools.assets.get_enum_class")
    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_link_asset_to_asset_group(self, mock_get_type, mock_get_service, mock_get_client, mock_get_enum):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/assetGroupAssets/101~202~HEADLINE")]
        mock_service.mutate_asset_group_assets.return_value = mock_response

        enum_class = MagicMock()
        enum_class.HEADLINE = 2
        mock_get_enum.return_value = enum_class

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = assets.link_asset_to_asset_group(
            customer_id="123",
            asset_group_id="101",
            asset_id_or_resource_name="202",
            field_type="HEADLINE",
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.asset_group, "customers/123/assetGroups/101")
        self.assertEqual(op_instance.create.asset, "customers/123/assets/202")
        self.assertEqual(op_instance.create.field_type, 2)

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_unlink_asset_from_asset_group(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/assetGroupAssets/101~202~HEADLINE")]
        mock_service.mutate_asset_group_assets.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = assets.unlink_asset_from_asset_group(
            customer_id="123",
            asset_group_id="101",
            asset_id_or_resource_name="202",
            field_type="HEADLINE",
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.remove, "customers/123/assetGroupAssets/101~202~HEADLINE")

    # -------------------------------------------------------------
    # 3. YouTube Video Asset Creation & URL Parsing
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_create_youtube_video_asset_from_url(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/assets/777")]
        mock_service.mutate_assets.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        # Test URL parsing with youtu.be
        res = assets.create_youtube_video_asset(
            customer_id="123",
            youtube_video_id_or_url="https://youtu.be/dQw4w9WgXcQ",
            asset_name="Rick Roll",
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.youtube_video_asset.youtube_video_id, "dQw4w9WgXcQ")
        self.assertEqual(res["youtube_video_id"], "dQw4w9WgXcQ")

    def test_create_youtube_video_asset_invalid_id(self):
        with self.assertRaises(ToolError):
            assets.create_youtube_video_asset(
                customer_id="123",
                youtube_video_id_or_url="too_short",
            )

    # -------------------------------------------------------------
    # 4. Bid Modifier Update on Criterion
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_update_campaign_criterion_bid_modifier(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/campaignCriteria/999~20088")]
        mock_service.mutate_campaign_criteria.return_value = mock_response

        op_instance = MagicMock()
        op_instance.update_mask.paths = []
        mock_get_type.return_value = op_instance

        res = targeting.update_campaign_criterion_bid_modifier(
            customer_id="123",
            campaign_id="999",
            criterion_id="20088",
            bid_modifier=0.7,
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.update.resource_name, "customers/123/campaignCriteria/999~20088")
        self.assertEqual(op_instance.update.bid_modifier, 0.7)
        self.assertIn("bid_modifier", op_instance.update_mask.paths)

    # -------------------------------------------------------------
    # 5. Placement Exclusions (Campaign & Customer level)
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_add_placement_exclusion_campaign_level(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/campaignCriteria/999~111")]
        mock_service.mutate_campaign_criteria.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = targeting.add_placement_exclusion(
            customer_id="123",
            placement_urls=["glance.com"],
            campaign_id="999",
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.campaign, "customers/123/campaigns/999")
        self.assertTrue(op_instance.create.negative)
        self.assertEqual(op_instance.create.placement.url, "glance.com")

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_add_placement_exclusion_customer_level(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/customerNegativeCriteria/111")]
        mock_service.mutate_customer_negative_criteria.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = targeting.add_placement_exclusion(
            customer_id="123",
            placement_urls=["glance.com"],
            campaign_id=None,
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.placement.url, "glance.com")

    # -------------------------------------------------------------
    # 6. Ad Group Demographic Exclusion (Gender, Age, Parental, Income)
    # -------------------------------------------------------------
    @patch("ads_mcp.tools.targeting.get_enum_value")
    @patch("ads_mcp.utils.get_googleads_client")
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_add_ad_group_demographic_exclusion_gender(self, mock_get_type, mock_get_service, mock_get_client, mock_get_enum):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/adGroupCriteria/555~777")]
        mock_service.mutate_ad_group_criteria.return_value = mock_response

        mock_get_enum.return_value = 1

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = targeting.add_ad_group_demographic_exclusion(
            customer_id="123",
            ad_group_id="555",
            demographic_type="GENDER",
            value="MALE",
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.ad_group, "customers/123/adGroups/555")
        self.assertTrue(op_instance.create.negative)
        self.assertEqual(op_instance.create.gender.type, 1)

    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_client")
    def test_add_ad_group_demographic_exclusion_invalid_type(self, mock_get_client, mock_get_type, mock_get_service):
        with self.assertRaises(ToolError) as ctx:
            targeting.add_ad_group_demographic_exclusion(
                customer_id="123",
                ad_group_id="555",
                demographic_type="INVALID_TYPE",
                value="MALE",
            )
        self.assertIn("Invalid demographic_type", str(ctx.exception))

    # -------------------------------------------------------------
    # 7. Campaign Audience Criterion (User List & User Interest)
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_service")
    @patch("ads_mcp.utils.get_googleads_type")
    def test_add_campaign_audience_criterion(self, mock_get_type, mock_get_service):
        mock_service = MagicMock()
        mock_get_service.return_value = mock_service
        mock_response = MagicMock()
        mock_response.results = [MagicMock(resource_name="customers/123/campaignCriteria/999~888")]
        mock_service.mutate_campaign_criteria.return_value = mock_response

        op_instance = MagicMock()
        mock_get_type.return_value = op_instance

        res = targeting.add_campaign_audience_criterion(
            customer_id="123",
            campaign_id="999",
            user_list_id="444",
            negative=False,
            bid_modifier=1.2,
        )

        self.assertTrue(res["success"])
        self.assertEqual(op_instance.create.campaign, "customers/123/campaigns/999")
        self.assertFalse(op_instance.create.negative)
        self.assertEqual(op_instance.create.user_list.user_list, "customers/123/userLists/444")
        self.assertEqual(op_instance.create.bid_modifier, 1.2)

    def test_add_campaign_audience_criterion_missing_target(self):
        with self.assertRaises(ToolError) as ctx:
            targeting.add_campaign_audience_criterion(
                customer_id="123",
                campaign_id="999",
            )
        self.assertIn("Must specify either user_interest_id or user_list_id", str(ctx.exception))

    # -------------------------------------------------------------
    # 8. Keyword Planner Explorer Access Error Trap
    # -------------------------------------------------------------
    @patch("ads_mcp.utils.get_googleads_type")
    @patch("ads_mcp.utils.get_googleads_service")
    def test_generate_keyword_ideas_explorer_access(self, mock_get_service, mock_get_type):
        from google.ads.googleads.errors import GoogleAdsException

        mock_req = MagicMock()
        mock_get_type.return_value = mock_req

        mock_service = MagicMock()
        mock_get_service.return_value = mock_service

        mock_error = MagicMock()
        mock_error.message = "The developer token is not approved for this service (KeywordPlanIdeaService)"
        mock_failure = MagicMock()
        mock_failure.errors = [mock_error]

        mock_ex = GoogleAdsException(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        mock_ex.failure = mock_failure
        mock_service.generate_keyword_ideas.side_effect = mock_ex

        with self.assertRaises(ToolError) as ctx:
            planner.generate_keyword_ideas(
                customer_id="123",
                keywords=["marketing digital"],
            )

        self.assertIn("Explorer Access", str(ctx.exception))
        self.assertIn("Standard", str(ctx.exception))

    # -------------------------------------------------------------
    # 9. Search GAQL Caveats Check
    # -------------------------------------------------------------
    def test_search_doc_contains_gaql_caveats(self):
        doc = search.search.__doc__ or ""
        self.assertIn("change_event.change_resource_type", doc)
        self.assertIn("ASSET_GROUP", doc)
        self.assertIn("performance_label", doc)
        self.assertIn("url_expansion_opt_out", doc)
        self.assertIn("BUSINESS_MESSAGE", doc)
