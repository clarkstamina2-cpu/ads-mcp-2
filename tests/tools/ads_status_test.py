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

"""Tests for update_ad_status (API calls are mocked)."""

import enum
import unittest
from unittest import mock

from ads_mcp.tools import ads


class _AdStatus(enum.Enum):
    UNSPECIFIED = 0
    UNKNOWN = 1
    ENABLED = 2
    PAUSED = 3
    REMOVED = 4


class UpdateAdStatusTest(unittest.TestCase):
    def setUp(self):
        self.service = mock.Mock()
        self.service.mutate_ad_group_ads.return_value = mock.Mock(results=[mock.Mock(resource_name="x")])
        self.op = mock.MagicMock()
        self.op.update_mask.paths = []
        self.request = mock.MagicMock()
        self.request.operations = []
        mock.patch.object(ads.utils, "get_googleads_service", return_value=self.service).start()
        mock.patch.object(
            ads.utils,
            "get_googleads_type",
            side_effect=lambda name, customer_id: self.request if name == "MutateAdGroupAdsRequest" else self.op,
        ).start()
        mock.patch.object(ads.utils, "get_googleads_client", return_value=mock.Mock()).start()
        mock.patch.object(ads.utils, "get_login_customer_id_for_customer", return_value="9").start()
        mock.patch.object(ads, "get_enum_class", return_value=_AdStatus).start()
        self.addCleanup(mock.patch.stopall)

    def test_removed_is_sent_as_a_remove_operation(self):
        out = ads.update_ad_status("906-474-8845", "104375542016", "447641636331", "removed", validate_only=True)
        self.assertEqual(self.op.remove, "customers/9064748845/adGroupAds/104375542016~447641636331")
        self.assertEqual(list(self.op.update_mask.paths), [])
        self.assertTrue(self.request.validate_only)
        self.assertEqual(out["new_status"], "REMOVED")

    def test_paused_is_still_an_update(self):
        ads.update_ad_status("1", "2", "3", "PAUSED")
        self.assertEqual(self.op.update.resource_name, "customers/1/adGroupAds/2~3")
        self.assertEqual(self.op.update.status, _AdStatus.PAUSED)
        self.assertEqual(list(self.op.update_mask.paths), ["status"])


if __name__ == "__main__":
    unittest.main()
