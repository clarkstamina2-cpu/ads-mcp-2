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

"""Tests for the extended update_conversion_action (API calls are mocked)."""

import enum
import unittest
from unittest import mock

from fastmcp.exceptions import ToolError

from ads_mcp.tools import conversions as conv


class _Counting(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ONE_PER_CLICK = 2
    MANY_PER_CLICK = 3


class _Attribution(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    GOOGLE_ADS_LAST_CLICK = 2
    GOOGLE_SEARCH_ATTRIBUTION_DATA_DRIVEN = 3


class _Status(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ENABLED = 2
    PAUSED = 3
    HIDDEN = 4


ENUMS = {
    "ConversionActionCountingTypeEnum": _Counting,
    "AttributionModelEnum": _Attribution,
    "ConversionActionStatusEnum": _Status,
}


class UpdateConversionActionTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        self.service.mutate_conversion_actions.return_value = mock.Mock(
            results=[mock.Mock(resource_name="customers/1234567890/conversionActions/55")]
        )
        self.op = mock.MagicMock()
        self.op.update_mask.paths = []  # a real list, like the empty repeated field of the API
        patches = [
            mock.patch.object(conv.utils, "get_googleads_service", return_value=self.service),
            mock.patch.object(conv.utils, "get_googleads_type", return_value=self.op),
            mock.patch.object(conv.utils, "get_googleads_client", return_value=mock.Mock()),
            mock.patch.object(conv.utils, "get_login_customer_id_for_customer", return_value="9"),
            mock.patch.object(conv, "get_enum_class", side_effect=lambda client, name: ENUMS[name]),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def _mask(self):
        return list(self.op.update_mask.paths)

    def test_updates_all_new_fields_with_the_right_mask_paths(self):
        out = conv.update_conversion_action(
            "123-456-7890",
            "55",
            click_through_lookback_window_days=90,
            view_through_lookback_window_days=7,
            counting_type="many_per_click",
            attribution_model="google_ads_last_click",
            default_value=1,
            always_use_default_value=True,
            default_currency_code="brl",
        )
        action = self.op.update
        self.assertEqual(action.resource_name, "customers/1234567890/conversionActions/55")
        self.assertEqual(action.click_through_lookback_window_days, 90)
        self.assertEqual(action.view_through_lookback_window_days, 7)
        self.assertEqual(action.counting_type, _Counting.MANY_PER_CLICK)
        self.assertEqual(action.attribution_model_settings.attribution_model, _Attribution.GOOGLE_ADS_LAST_CLICK)
        self.assertEqual(action.value_settings.default_value, 1.0)
        self.assertTrue(action.value_settings.always_use_default_value)
        self.assertEqual(action.value_settings.default_currency_code, "BRL")
        self.assertEqual(
            self._mask(),
            [
                "click_through_lookback_window_days",
                "view_through_lookback_window_days",
                "counting_type",
                "attribution_model_settings.attribution_model",
                "value_settings.default_value",
                "value_settings.always_use_default_value",
                "value_settings.default_currency_code",
            ],
        )
        self.assertEqual(out["updated_fields"]["default_currency_code"], "BRL")
        self.assertEqual(self.service.mutate_conversion_actions.call_args.kwargs["customer_id"], "1234567890")

    def test_only_the_passed_fields_are_in_the_mask(self):
        conv.update_conversion_action("1", "55", click_through_lookback_window_days=60)
        self.assertEqual(self._mask(), ["click_through_lookback_window_days"])

    def test_existing_parameters_still_work(self):
        conv.update_conversion_action("1", "55", primary_for_goal=False, status="paused", name="  Novo nome ")
        self.assertEqual(self._mask(), ["primary_for_goal", "status", "name"])
        self.assertFalse(self.op.update.primary_for_goal)
        self.assertEqual(self.op.update.status, _Status.PAUSED)
        self.assertEqual(self.op.update.name, "Novo nome")

    def test_resource_name_is_accepted(self):
        conv.update_conversion_action("1", "customers/1/conversionActions/77", default_value=2.5)
        self.assertEqual(self.op.update.resource_name, "customers/1/conversionActions/77")

    def test_validate_only_sends_the_flag(self):
        out = conv.update_conversion_action("1", "55", click_through_lookback_window_days=90, validate_only=True)
        request = self.service.mutate_conversion_actions.call_args.kwargs["request"]
        self.assertTrue(request["validate_only"])
        self.assertTrue(out["validate_only"])

    def test_window_ranges_are_validated(self):
        for kwargs in (
            {"click_through_lookback_window_days": 0},
            {"click_through_lookback_window_days": 91},
            {"view_through_lookback_window_days": 0},
            {"view_through_lookback_window_days": 31},
        ):
            with self.assertRaises(ToolError, msg=str(kwargs)):
                conv.update_conversion_action("1", "55", **kwargs)
        self.service.mutate_conversion_actions.assert_not_called()

    def test_invalid_enum_lists_the_valid_values(self):
        with self.assertRaises(ToolError) as ctx:
            conv.update_conversion_action("1", "55", attribution_model="LAST_CLICK")
        self.assertIn("GOOGLE_ADS_LAST_CLICK", str(ctx.exception))
        self.assertIn("Invalid attribution_model", str(ctx.exception))
        with self.assertRaises(ToolError):
            conv.update_conversion_action("1", "55", counting_type="SOMETIMES")
        self.service.mutate_conversion_actions.assert_not_called()

    def test_no_parameter_is_an_error(self):
        with self.assertRaises(ToolError) as ctx:
            conv.update_conversion_action("1", "55")
        self.assertIn("At least one parameter", str(ctx.exception))
        self.service.mutate_conversion_actions.assert_not_called()


if __name__ == "__main__":
    unittest.main()
