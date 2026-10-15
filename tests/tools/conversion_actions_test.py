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

"""Tests for create_conversion_action (API calls are mocked)."""

import enum
import unittest
from unittest import mock

from fastmcp.exceptions import ToolError

from ads_mcp.tools import conversion_actions as ca


class _Type(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    WEBPAGE = 2


class _Category(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    DEFAULT = 2
    CONTACT = 3
    SUBMIT_LEAD_FORM = 4
    PURCHASE = 5


class _Counting(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ONE_PER_CLICK = 2
    MANY_PER_CLICK = 3


class _Status(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ENABLED = 2


class _Attribution(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    GOOGLE_ADS_LAST_CLICK = 2


ENUMS = {
    "ConversionActionTypeEnum": _Type,
    "ConversionActionCategoryEnum": _Category,
    "ConversionActionCountingTypeEnum": _Counting,
    "ConversionActionStatusEnum": _Status,
    "AttributionModelEnum": _Attribution,
}

# Fake IDs: the real format is "'send_to': 'AW-<conversion id>/<label>'"
SNIPPETS = [
    {"global_site_tag": "<script async src='https://www.googletagmanager.com/gtag/js?id=AW-1112223334'></script>"},
    {"event_snippet": "gtag('event', 'conversion', {'send_to': 'AW-1112223334/AbCdEfGhIjK_lMn-oP'});"},
]


class ExtractSendToTest(unittest.TestCase):
    def test_finds_id_and_label(self):
        out = ca.extract_send_to(SNIPPETS)
        self.assertEqual(out["conversion_id"], "1112223334")
        self.assertEqual(out["conversion_label"], "AbCdEfGhIjK_lMn-oP")
        self.assertEqual(out["send_to"], "AW-1112223334/AbCdEfGhIjK_lMn-oP")

    def test_global_tag_alone_has_no_label(self):
        self.assertIsNone(ca.extract_send_to(SNIPPETS[:1]))

    def test_empty_inputs(self):
        self.assertIsNone(ca.extract_send_to(None))
        self.assertIsNone(ca.extract_send_to([]))


class CreateConversionActionTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        self.op = mock.MagicMock()
        self.service.mutate_conversion_actions.return_value = mock.Mock(
            results=[mock.Mock(resource_name="customers/1234567890/conversionActions/555")]
        )
        self.search = mock.Mock(return_value=[{"conversion_action.tag_snippets": SNIPPETS}])
        patches = [
            mock.patch.object(ca, "search", self.search),
            mock.patch.object(ca.utils, "get_googleads_client", return_value=mock.Mock()),
            mock.patch.object(ca.utils, "get_login_customer_id_for_customer", return_value="9"),
            mock.patch.object(ca.utils, "get_googleads_service", return_value=self.service),
            mock.patch.object(ca.utils, "get_googleads_type", return_value=self.op),
            mock.patch.object(ca, "get_enum_class", side_effect=lambda client, name: ENUMS[name]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_creates_secondary_conversion_and_returns_id_and_label(self):
        out = ca.create_conversion_action("123-456-7890", "Conversao teste", category="contact")
        created = self.op.create
        self.assertFalse(created.primary_for_goal)  # secondary by default
        self.assertEqual(created.category, _Category.CONTACT)
        self.assertEqual(created.type_, _Type.WEBPAGE)
        self.assertEqual(created.counting_type, _Counting.ONE_PER_CLICK)
        self.assertEqual(created.click_through_lookback_window_days, 30)
        self.assertEqual(out["conversion_action_id"], "555")
        self.assertEqual(out["conversion_id"], "1112223334")
        self.assertEqual(out["conversion_label"], "AbCdEfGhIjK_lMn-oP")
        self.assertEqual(out["send_to"], "AW-1112223334/AbCdEfGhIjK_lMn-oP")
        self.assertFalse(out["validate_only"])
        self.assertEqual(self.service.mutate_conversion_actions.call_args.kwargs["customer_id"], "1234567890")

    def test_primary_only_when_asked(self):
        ca.create_conversion_action("1", "x", primary_for_goal=True)
        self.assertTrue(self.op.create.primary_for_goal)

    def test_validate_only_creates_nothing_and_does_not_read_snippets(self):
        out = ca.create_conversion_action("1", "Conversao teste", validate_only=True)
        request = self.service.mutate_conversion_actions.call_args.kwargs["request"]
        self.assertTrue(request["validate_only"])
        self.assertTrue(out["validate_only"])
        self.assertEqual(out["would_create"]["name"], "Conversao teste")
        self.assertFalse(out["would_create"]["primary_for_goal"])
        self.search.assert_not_called()

    def test_lead_is_an_alias_for_submit_lead_form(self):
        out = ca.create_conversion_action("1", "x", category="LEAD", validate_only=True)
        self.assertEqual(self.op.create.category, _Category.SUBMIT_LEAD_FORM)
        self.assertEqual(out["would_create"]["category"], "SUBMIT_LEAD_FORM")

    def test_value_settings_and_attribution(self):
        ca.create_conversion_action(
            "1", "x", default_value=50.0, currency_code="brl", attribution_model="GOOGLE_ADS_LAST_CLICK", validate_only=True
        )
        created = self.op.create
        self.assertEqual(created.value_settings.default_value, 50.0)
        self.assertEqual(created.value_settings.default_currency_code, "BRL")
        self.assertEqual(created.attribution_model_settings.attribution_model, _Attribution.GOOGLE_ADS_LAST_CLICK)

    def test_view_through_window_is_optional_and_validated(self):
        ca.create_conversion_action("1", "x", view_through_lookback_window_days=7, validate_only=True)
        self.assertEqual(self.op.create.view_through_lookback_window_days, 7)
        with self.assertRaises(ToolError):
            ca.create_conversion_action("1", "x", view_through_lookback_window_days=31)
        with self.assertRaises(ToolError):
            ca.create_conversion_action("1", "x", view_through_lookback_window_days=0)

    def test_no_value_settings_when_no_default_value(self):
        self.op.create.value_settings = mock.Mock(spec=["default_value"])
        ca.create_conversion_action("1", "x", validate_only=True)
        self.assertFalse(hasattr(self.op.create.value_settings, "default_currency_code"))

    def test_invalid_category_lists_valid_values(self):
        with self.assertRaises(ToolError) as ctx:
            ca.create_conversion_action("1", "x", category="NOPE")
        self.assertIn("CONTACT", str(ctx.exception))
        self.service.mutate_conversion_actions.assert_not_called()

    def test_invalid_lookback_and_empty_name_are_rejected(self):
        with self.assertRaises(ToolError):
            ca.create_conversion_action("1", "x", click_through_lookback_window_days=0)
        with self.assertRaises(ToolError):
            ca.create_conversion_action("1", "x", click_through_lookback_window_days=91)
        with self.assertRaises(ToolError):
            ca.create_conversion_action("1", "   ")
        self.service.mutate_conversion_actions.assert_not_called()

    def test_note_when_label_is_not_available_yet(self):
        self.search.return_value = [{"conversion_action.tag_snippets": SNIPPETS[:1]}]
        out = ca.create_conversion_action("1", "x")
        self.assertEqual(out["conversion_action_id"], "555")
        self.assertIsNone(out["conversion_label"])
        self.assertIn("note", out)


if __name__ == "__main__":
    unittest.main()
