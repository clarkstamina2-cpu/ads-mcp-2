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

"""Tests for the recommendation subscription and audience name tools (API calls are mocked)."""

import unittest
from types import SimpleNamespace
from unittest import mock

from fastmcp.exceptions import ToolError

from ads_mcp.tools import recommendations as rec


def _row(rec_type, status, shown_type="UNKNOWN"):
    return {
        "recommendation_subscription.resource_name": f"customers/1/recommendationSubscriptions/{rec_type}",
        "recommendation_subscription.type": shown_type,
        "recommendation_subscription.status": status,
        "recommendation_subscription.modify_date_time": "2024-01-01 00:00:00",
    }


ROWS = [
    _row("KEYWORD", "ENABLED", "KEYWORD"),
    _row("NEW_TYPE_FROM_GOOGLE", "ENABLED"),
    _row("TARGET_CPA_OPT_IN", "PAUSED", "TARGET_CPA_OPT_IN"),
]
# Real case seen on a client account: subscriptions whose resource name is literally '.../UNKNOWN'
ROWS_WITH_UNKNOWN = ROWS + [
    _row("UNKNOWN", "ENABLED"),
    _row("UNKNOWN", "ENABLED"),
    _row("UNKNOWN", "PAUSED"),
]
ENUMS = {
    "RecommendationSubscriptionStatusEnum": SimpleNamespace(ENABLED="E", PAUSED="P"),
    "RecommendationTypeEnum": SimpleNamespace(KEYWORD="K", TARGET_CPA_OPT_IN="T"),
}


class HelpersTest(unittest.TestCase):
    def test_type_comes_from_resource_name_even_when_unknown(self):
        self.assertEqual(
            rec.type_from_resource_name("customers/1/recommendationSubscriptions/NEW_TYPE_FROM_GOOGLE"),
            "NEW_TYPE_FROM_GOOGLE",
        )

    def test_parse_audience_id_variants(self):
        self.assertEqual(rec.parse_audience_id("uservertical::80103"), 80103)
        self.assertEqual(rec.parse_audience_id(80104), 80104)
        self.assertEqual(rec.parse_audience_id(" 30001 "), 30001)

    def test_parse_audience_id_rejects_garbage(self):
        for bad in ("abc", "uservertical::", "", "12x"):
            with self.assertRaises(ToolError, msg=bad):
                rec.parse_audience_id(bad)


class SetStatusTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        patches = [
            mock.patch.object(rec, "search", return_value=ROWS),
            mock.patch.object(rec.utils, "get_googleads_client", return_value=mock.Mock()),
            mock.patch.object(rec.utils, "get_login_customer_id_for_customer", return_value="9"),
            mock.patch.object(rec.utils, "get_googleads_service", return_value=self.service),
            mock.patch.object(rec.utils, "get_googleads_type", side_effect=lambda *a, **k: mock.MagicMock()),
            mock.patch.object(rec, "get_enum_class", side_effect=lambda client, name: ENUMS[name]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_turn_all_off_changes_only_enabled_ones(self):
        out = rec.set_recommendation_subscription_status("123-456-7890", "paused")
        self.assertEqual({c["type"] for c in out["changed"]}, {"KEYWORD", "NEW_TYPE_FROM_GOOGLE"})
        self.assertEqual(out["unchanged"], ["TARGET_CPA_OPT_IN"])
        self.assertEqual(len(self.service.mutate_recommendation_subscription.call_args.kwargs["operations"]), 2)
        self.assertEqual(self.service.mutate_recommendation_subscription.call_args.kwargs["customer_id"], "1234567890")

    def test_all_keyword_is_case_insensitive(self):
        out = rec.set_recommendation_subscription_status("1", "PAUSED", ["all"])
        self.assertEqual(len(out["changed"]), 2)

    def test_validate_only_sends_validate_flag(self):
        out = rec.set_recommendation_subscription_status("1", "PAUSED", ["KEYWORD"], validate_only=True)
        request = self.service.mutate_recommendation_subscription.call_args.kwargs["request"]
        self.assertTrue(request["validate_only"])
        self.assertTrue(out["validate_only"])

    def test_nothing_to_change_makes_no_api_call(self):
        out = rec.set_recommendation_subscription_status("1", "PAUSED", ["TARGET_CPA_OPT_IN"])
        self.assertEqual(out["changed"], [])
        self.service.mutate_recommendation_subscription.assert_not_called()

    def test_enable_creates_missing_known_type_and_skips_unknown(self):
        out = rec.set_recommendation_subscription_status("1", "ENABLED", ["TARGET_CPA_OPT_IN", "BOGUS_TYPE"])
        self.assertEqual([c["type"] for c in out["changed"]], ["TARGET_CPA_OPT_IN"])
        self.assertEqual(out["skipped"][0]["type"], "BOGUS_TYPE")

    def test_pausing_a_type_without_subscription_is_skipped(self):
        out = rec.set_recommendation_subscription_status("1", "PAUSED", ["NOT_SUBSCRIBED_YET"])
        self.assertEqual(out["changed"], [])
        self.assertEqual(len(out["skipped"]), 1)

    def test_invalid_status_is_rejected(self):
        with self.assertRaises(ToolError):
            rec.set_recommendation_subscription_status("1", "DELETE")
        self.service.mutate_recommendation_subscription.assert_not_called()

    def test_unknown_type_subscriptions_are_skipped_not_sent_to_the_api(self):
        with mock.patch.object(rec, "search", return_value=ROWS_WITH_UNKNOWN):
            out = rec.set_recommendation_subscription_status("1", "PAUSED")
        ops = self.service.mutate_recommendation_subscription.call_args.kwargs["operations"]
        self.assertEqual(len(ops), 2)  # only KEYWORD and NEW_TYPE_FROM_GOOGLE
        unknown = [s for s in out["skipped"] if s["type"] == "UNKNOWN"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["count"], 2)  # the 2 enabled ones; the paused one needs nothing
        self.assertIn("UI", unknown[0]["reason"])

    def test_asking_for_unknown_explicitly_only_reports_it(self):
        with mock.patch.object(rec, "search", return_value=ROWS_WITH_UNKNOWN):
            out = rec.set_recommendation_subscription_status("1", "PAUSED", ["UNKNOWN"])
        self.service.mutate_recommendation_subscription.assert_not_called()
        self.assertEqual(out["changed"], [])
        self.assertEqual(out["skipped"][0]["type"], "UNKNOWN")

    def test_unknown_already_in_target_state_is_not_reported(self):
        rows = [_row("UNKNOWN", "PAUSED"), _row("KEYWORD", "ENABLED", "KEYWORD")]
        with mock.patch.object(rec, "search", return_value=rows):
            out = rec.set_recommendation_subscription_status("1", "PAUSED")
        self.assertEqual(out["skipped"], [])


class ListAndResolveTest(unittest.TestCase):
    def test_list_counts_enabled(self):
        with mock.patch.object(rec, "search", return_value=ROWS):
            out = rec.list_recommendation_subscriptions("1")
        self.assertEqual(out["auto_apply_enabled_count"], 2)
        self.assertEqual(out["total"], 3)
        self.assertEqual(out["subscriptions"][1]["type"], "NEW_TYPE_FROM_GOOGLE")
        self.assertEqual(out["enabled_not_manageable_via_api"], 0)
        self.assertNotIn("note", out)

    def test_list_flags_unknown_subscriptions_as_not_manageable(self):
        with mock.patch.object(rec, "search", return_value=ROWS_WITH_UNKNOWN):
            out = rec.list_recommendation_subscriptions("1")
        self.assertEqual(out["auto_apply_enabled_count"], 4)
        self.assertEqual(out["enabled_not_manageable_via_api"], 2)
        self.assertIn("2 enabled", out["note"])
        flags = {s["type"]: s["api_manageable"] for s in out["subscriptions"]}
        self.assertFalse(flags["UNKNOWN"])
        self.assertTrue(flags["KEYWORD"])

    def test_resolve_names_merges_sources_and_reports_missing(self):
        def fake_search(customer_id, fields, resource, conditions=None, **_):
            self.assertIn("IN (30001,80103,99999)", conditions[0])
            data = {
                "user_interest": [{"user_interest.user_interest_id": 80103, "user_interest.name": "Beauty"}],
                "detailed_demographic": [{"detailed_demographic.id": 30001, "detailed_demographic.name": "Education"}],
                "life_event": [],
            }
            return data[resource]

        with mock.patch.object(rec, "search", side_effect=fake_search), mock.patch.object(
            rec.utils, "_get_login_customer_id", return_value="1112223334"
        ):
            out = rec.resolve_audience_names(["uservertical::80103", 30001, "99999", "80103"])
        self.assertEqual(out["resolved"]["80103"], [{"name": "Beauty", "source": "user_interest"}])
        self.assertEqual(out["resolved"]["30001"][0]["name"], "Education")
        self.assertEqual(out["not_found"], ["99999"])

    def test_resolve_needs_a_customer_when_no_default(self):
        with mock.patch.object(rec.utils, "_get_login_customer_id", return_value=None):
            with self.assertRaises(ToolError):
                rec.resolve_audience_names([1])

    def test_resolve_rejects_empty_list(self):
        with self.assertRaises(ToolError):
            rec.resolve_audience_names([])


if __name__ == "__main__":
    unittest.main()
