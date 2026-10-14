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

"""Tests for the device bid modifier fix, EU declaration, demographic bid modifiers and diagnosis (API mocked)."""

import enum
import unittest
from unittest import mock

from fastmcp.exceptions import ToolError

from ads_mcp.tools import campaign_adjustments as adj
from ads_mcp.tools import targeting


class _EU(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    CONTAINS_EU_POLITICAL_ADVERTISING = 2
    DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING = 3


class _Age(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    AGE_RANGE_18_24 = 2
    AGE_RANGE_25_34 = 3


class _Gender(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    MALE = 2
    FEMALE = 3


ENUMS = {
    "EuPoliticalAdvertisingStatusEnum": _EU,
    "AgeRangeTypeEnum": _Age,
    "GenderTypeEnum": _Gender,
}


def _patch_utils(module, service, ops):
    def new_op(*_a, **_k):
        op = mock.MagicMock()
        ops.append(op)
        return op

    return [
        mock.patch.object(module.utils, "get_googleads_service", return_value=service),
        mock.patch.object(module.utils, "get_googleads_type", side_effect=new_op),
        mock.patch.object(module.utils, "get_googleads_client", return_value=mock.Mock()),
        mock.patch.object(module.utils, "get_login_customer_id_for_customer", return_value="9"),
    ]


class DeviceBidModifierTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        self.service.mutate_campaign_criteria.return_value = mock.Mock(results=[])
        self.ops = []
        for p in _patch_utils(targeting, self.service, self.ops):
            p.start()
            self.addCleanup(p.stop)

    def test_uses_campaign_criteria_with_fixed_device_ids(self):
        out = targeting.set_campaign_device_bid_modifiers("123-456-7890", "555", desktop_modifier=0.5, mobile_modifier=1.2)
        self.assertEqual(len(self.ops), 2)
        self.assertEqual(self.ops[0].update.resource_name, "customers/1234567890/campaignCriteria/555~30000")
        self.assertEqual(self.ops[0].update.bid_modifier, 0.5)
        self.assertEqual(self.ops[1].update.resource_name, "customers/1234567890/campaignCriteria/555~30001")
        self.assertEqual(self.ops[1].update.bid_modifier, 1.2)
        self.ops[0].update_mask.paths.append.assert_called_with("bid_modifier")
        self.service.mutate_campaign_criteria.assert_called_once()
        self.assertTrue(out["success"])

    def test_tablet_uses_30002_and_accepts_resource_name(self):
        targeting.set_campaign_device_bid_modifiers("1", "customers/1/campaigns/777", tablet_modifier=0.0)
        self.assertEqual(self.ops[0].update.resource_name, "customers/1/campaignCriteria/777~30002")

    def test_does_not_use_the_bid_modifier_service(self):
        targeting.set_campaign_device_bid_modifiers("1", "5", desktop_modifier=0.5)
        names = [c.args[0] for c in targeting.utils.get_googleads_service.call_args_list]
        self.assertEqual(names, ["CampaignCriterionService"])

    def test_validate_only(self):
        out = targeting.set_campaign_device_bid_modifiers("1", "5", desktop_modifier=0.5, validate_only=True)
        request = self.service.mutate_campaign_criteria.call_args.kwargs["request"]
        self.assertTrue(request["validate_only"])
        self.assertTrue(out["validate_only"])

    def test_requires_at_least_one_device(self):
        with self.assertRaises(ToolError):
            targeting.set_campaign_device_bid_modifiers("1", "5")
        self.service.mutate_campaign_criteria.assert_not_called()


class EuPoliticalTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        self.service.mutate_campaigns.return_value = mock.Mock(results=[mock.Mock(resource_name="customers/1/campaigns/5")])
        self.ops = []
        patches = _patch_utils(adj, self.service, self.ops) + [
            mock.patch.object(adj, "get_enum_class", side_effect=lambda client, name: ENUMS[name]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_declares_no_political_ads(self):
        out = adj.set_campaign_eu_political_advertising("1", "5", False)
        op = self.ops[0]
        self.assertEqual(op.update.resource_name, "customers/1/campaigns/5")
        self.assertEqual(op.update.contains_eu_political_advertising, _EU.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING)
        op.update_mask.paths.append.assert_called_with("contains_eu_political_advertising")
        self.assertEqual(out["status"], "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING")

    def test_declares_political_ads(self):
        adj.set_campaign_eu_political_advertising("1", "customers/1/campaigns/5", True)
        self.assertEqual(self.ops[0].update.contains_eu_political_advertising, _EU.CONTAINS_EU_POLITICAL_ADVERTISING)

    def test_value_is_required(self):
        with self.assertRaises(TypeError):
            adj.set_campaign_eu_political_advertising("1", "5")  # no default on purpose

    def test_validate_only(self):
        out = adj.set_campaign_eu_political_advertising("1", "5", False, validate_only=True)
        self.assertTrue(self.service.mutate_campaigns.call_args.kwargs["request"]["validate_only"])
        self.assertTrue(out["validate_only"])


class DemographicBidModifierTest(unittest.TestCase):
    EXISTING = [{"ad_group_criterion.resource_name": "customers/1/adGroupCriteria/9~503002", "ad_group_criterion.criterion_id": 503002, "ad_group_criterion.negative": False}]

    def setUp(self):
        self.service = mock.Mock()
        self.service.mutate_ad_group_criteria.return_value = mock.Mock(results=[mock.Mock(resource_name="customers/1/adGroupCriteria/9~503002")])
        self.ops = []
        self.search = mock.Mock(return_value=self.EXISTING)
        patches = _patch_utils(adj, self.service, self.ops) + [
            mock.patch.object(adj, "search", self.search),
            mock.patch.object(adj, "get_enum_class", side_effect=lambda client, name: ENUMS[name]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_updates_existing_criterion(self):
        out = adj.set_ad_group_demographic_bid_modifier("1", "9", "age_range", "age_range_25_34", 1.3)
        op = self.ops[0]
        self.assertEqual(op.update.resource_name, "customers/1/adGroupCriteria/9~503002")
        self.assertEqual(op.update.bid_modifier, 1.3)
        op.update_mask.paths.append.assert_called_with("bid_modifier")
        self.assertEqual(out["operation"], "updated")
        conditions = self.search.call_args.kwargs["conditions"]
        self.assertIn("ad_group.id = 9", conditions)
        self.assertIn("ad_group_criterion.type = 'AGE_RANGE'", conditions)
        self.assertIn("ad_group_criterion.age_range.type = 'AGE_RANGE_25_34'", conditions)

    def test_creates_when_the_segment_does_not_exist(self):
        self.search.return_value = []
        out = adj.set_ad_group_demographic_bid_modifier("1", "9", "GENDER", "FEMALE", 0.8)
        op = self.ops[0]
        self.assertEqual(op.create.ad_group, "customers/1/adGroups/9")
        self.assertEqual(op.create.gender.type_, _Gender.FEMALE)
        self.assertEqual(op.create.bid_modifier, 0.8)
        self.assertEqual(out["operation"], "created")

    def test_refuses_excluded_segment(self):
        self.search.return_value = [{**self.EXISTING[0], "ad_group_criterion.negative": True}]
        with self.assertRaises(ToolError) as ctx:
            adj.set_ad_group_demographic_bid_modifier("1", "9", "AGE_RANGE", "AGE_RANGE_25_34", 1.2)
        self.assertIn("EXCLUDED", str(ctx.exception))
        self.service.mutate_ad_group_criteria.assert_not_called()

    def test_validation_errors(self):
        for args in (
            ("1", "9", "HEIGHT", "TALL", 1.2),
            ("1", "9", "GENDER", "ROBOT", 1.2),
            ("1", "9", "GENDER", "MALE", 0.0),
            ("1", "9", "GENDER", "MALE", 10.5),
        ):
            with self.assertRaises(ToolError, msg=str(args)):
                adj.set_ad_group_demographic_bid_modifier(*args)
        self.service.mutate_ad_group_criteria.assert_not_called()

    def test_validate_only(self):
        adj.set_ad_group_demographic_bid_modifier("1", "9", "GENDER", "MALE", 1.1, validate_only=True)
        self.assertTrue(self.service.mutate_ad_group_criteria.call_args.kwargs["request"]["validate_only"])


class BuildFindingsTest(unittest.TestCase):
    OK_CAMPAIGN = {"status": "ENABLED", "primary_status": "ELIGIBLE", "primary_status_reasons": [], "serving_status": "SERVING"}
    GROUPS = {"ENABLED": 1, "total": 1}
    ADS = {"total": 1, "enabled_and_approved": 1, "disapproved": 0}
    ZERO = {"impressions": 0}

    def test_paused_campaign_is_a_blocker(self):
        camp = {**self.OK_CAMPAIGN, "status": "PAUSED", "primary_status": "PAUSED", "primary_status_reasons": ["CAMPAIGN_PAUSED"], "serving_status": "NONE"}
        out = adj.build_findings(camp, self.ZERO, self.ZERO, self.GROUPS, self.ADS, None)
        codes = [f["code"] for f in out["findings"]]
        self.assertIn("CAMPAIGN_PAUSED", codes)
        self.assertTrue(out["likely_cause"].startswith("Há bloqueio"))
        self.assertIn("pausada", out["likely_cause"])

    def test_budget_constrained_reason_is_explained_in_portuguese(self):
        camp = {**self.OK_CAMPAIGN, "primary_status": "LIMITED", "primary_status_reasons": ["BUDGET_CONSTRAINED"]}
        out = adj.build_findings(camp, {"impressions": 50}, {"impressions": 200}, self.GROUPS, self.ADS, None)
        self.assertIn("orçamento", out["findings"][0]["message"])
        self.assertEqual(out["findings"][0]["severity"], "warning")

    def test_eligible_with_zero_impressions_points_to_search_volume(self):
        kws = {"total": 18, "rarely_served": 11, "eligible": 7}
        out = adj.build_findings(self.OK_CAMPAIGN, self.ZERO, self.ZERO, self.GROUPS, self.ADS, kws)
        self.assertEqual([f["code"] for f in out["findings"]], ["SOME_KEYWORDS_RARELY_SERVED"])
        self.assertIn("volume de busca baixo", out["likely_cause"])

    def test_serving_campaign_says_so(self):
        out = adj.build_findings(self.OK_CAMPAIGN, {"impressions": 10}, {"impressions": 90}, self.GROUPS, self.ADS, None)
        self.assertIn("está veiculando", out["likely_cause"])

    def test_no_approved_ads_and_no_ad_groups(self):
        out = adj.build_findings(
            self.OK_CAMPAIGN, self.ZERO, self.ZERO, {"total": 0}, {"total": 2, "enabled_and_approved": 0, "disapproved": 2}, None
        )
        codes = {f["code"] for f in out["findings"]}
        self.assertTrue({"NO_AD_GROUPS", "NO_APPROVED_ENABLED_ADS", "HAS_ADS_DISAPPROVED"} <= codes)

    def test_unknown_reason_falls_back_to_the_code(self):
        self.assertIn("SOMETHING_NEW", adj.explain_reason("SOMETHING_NEW"))


class DiagnoseCampaignTest(unittest.TestCase):
    def _fake_search(self, **kwargs):
        resource, conditions = kwargs["resource"], kwargs.get("conditions", [])
        if resource == "campaign" and "metrics.impressions" in kwargs["fields"]:
            return [{"metrics.impressions": 0, "metrics.clicks": 0, "metrics.cost_micros": 0}]
        if resource == "campaign":
            return [{
                "campaign.id": 11122233344, "campaign.name": "Campanha teste", "campaign.status": "ENABLED",
                "campaign.primary_status": "ELIGIBLE", "campaign.primary_status_reasons": [],
                "campaign.serving_status": "SERVING", "campaign.bidding_strategy_type": "TARGET_SPEND",
                "campaign.advertising_channel_type": "SEARCH", "campaign_budget.amount_micros": 10_000_000,
            }]
        if resource == "ad_group":
            return [{"ad_group.id": 1, "ad_group.status": "ENABLED"}]
        if resource == "ad_group_ad":
            return [{"ad_group_ad.status": "ENABLED", "ad_group_ad.policy_summary.approval_status": "APPROVED"}]
        if resource == "ad_group_criterion":
            return [{"ad_group_criterion.status": "ENABLED", "ad_group_criterion.system_serving_status": "RARELY_SERVED"}] * 11 + [
                {"ad_group_criterion.status": "ENABLED", "ad_group_criterion.system_serving_status": "ELIGIBLE"}
            ] * 7
        raise AssertionError(resource)

    def test_full_diagnosis_of_an_eligible_campaign_with_no_impressions(self):
        with mock.patch.object(adj, "search", side_effect=self._fake_search):
            out = adj.diagnose_campaign_serving("111-222-3333", "11122233344")
        self.assertEqual(out["customer_id"], "1112223333")
        self.assertEqual(out["campaign"]["daily_budget"], 10.0)
        self.assertEqual(out["impressions"]["last_7_days"]["impressions"], 0)
        self.assertEqual(out["keywords"], {"total": 18, "rarely_served": 11, "eligible": 7})
        self.assertEqual(out["ads"]["enabled_and_approved"], 1)
        self.assertIn("volume de busca baixo", out["likely_cause"])

    def test_campaign_not_found(self):
        with mock.patch.object(adj, "search", return_value=[]):
            with self.assertRaises(ToolError):
                adj.diagnose_campaign_serving("1", "999")

    def test_non_search_campaign_skips_keywords(self):
        def fake(**kwargs):
            rows = self._fake_search(**kwargs)
            if kwargs["resource"] == "campaign" and "campaign.id" in kwargs["fields"]:
                rows[0]["campaign.advertising_channel_type"] = "PERFORMANCE_MAX"
            return rows

        with mock.patch.object(adj, "search", side_effect=fake):
            out = adj.diagnose_campaign_serving("1", "5")
        self.assertIsNone(out["keywords"])


if __name__ == "__main__":
    unittest.main()
