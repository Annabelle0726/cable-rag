#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

import json

from api.utils.masking import (
    SECRET_MASK,
    client_supplied_secret,
    is_masked,
    mask_secret,
    resolve_secret_on_write,
)

STORED = "sk-storedkey1234567890"


class TestMaskSecret:
    def test_bare_key_keeps_a_recognisable_prefix_and_suffix(self):
        assert mask_secret("sk-bf0e05ffa1234567890abcdef") == f"sk-{SECRET_MASK}cdef"

    def test_result_is_recognisable_as_a_mask(self):
        assert is_masked(mask_secret("sk-bf0e05ffa1234567890abcdef"))

    def test_short_value_is_masked_whole(self):
        # Revealing 3 + 4 characters of a short secret would expose most of it.
        assert mask_secret("sk-abc") == SECRET_MASK

    def test_empty_and_none_pass_through_so_not_configured_stays_visible(self):
        assert mask_secret("") == ""
        assert mask_secret(None) is None
        assert not is_masked("")

    def test_cleartext_never_survives_for_a_real_key_length(self):
        raw = "sk-bf0e05ffa1234567890abcdef"
        assert raw not in mask_secret(raw)

    def test_json_bundle_masks_only_the_credential_fields(self):
        raw = json.dumps({"api_key": "sk-real1234567890", "group_id": "123"})
        masked = json.loads(mask_secret(raw))
        assert masked["api_key"] == f"sk-{SECRET_MASK}7890"
        # Structural fields must survive so provider forms keep their logic.
        assert masked["group_id"] == "123"

    def test_bedrock_bundle_masks_the_key_and_keeps_structural_fields(self):
        raw = json.dumps(
            {
                "auth_mode": "bedrock_api_key",
                "bedrock_api_key": "AKIA1234567890ABCD",
                "bedrock_region": "us-east-1",
            }
        )
        masked = json.loads(mask_secret(raw))
        assert masked["bedrock_api_key"] == f"AKI{SECRET_MASK}ABCD"
        assert masked["auth_mode"] == "bedrock_api_key"
        assert masked["bedrock_region"] == "us-east-1"

    def test_already_parsed_bundle_dict_is_supported(self):
        masked = mask_secret({"api_key": "sk-real1234567890"})
        assert masked["api_key"] == f"sk-{SECRET_MASK}7890"


class TestResolveSecretOnWrite:
    def test_absent_value_keeps_the_stored_credential(self):
        assert resolve_secret_on_write(None, STORED) == STORED

    def test_empty_value_keeps_the_stored_credential(self):
        # The regression this guards: the update path used to write "" here,
        # silently destroying every configured provider key.
        assert resolve_secret_on_write("", STORED) == STORED
        assert resolve_secret_on_write("   ", STORED) == STORED

    def test_echoed_mask_keeps_the_stored_credential(self):
        # Read-mask / write-back must not persist the mask as the key.
        echoed = mask_secret(STORED)
        assert is_masked(echoed)
        assert resolve_secret_on_write(echoed, STORED) == STORED

    def test_new_credential_replaces_the_stored_one(self):
        assert resolve_secret_on_write("sk-newkey9876543210", STORED) == "sk-newkey9876543210"

    def test_bundle_merges_new_fields_and_keeps_masked_ones(self):
        stored = json.dumps({"api_key": "sk-old1234567890", "group_id": "111"})
        incoming = {"api_key": mask_secret("sk-old1234567890"), "group_id": "222"}
        merged = json.loads(resolve_secret_on_write(incoming, stored))
        assert merged["api_key"] == "sk-old1234567890"
        assert merged["group_id"] == "222"

    def test_bundle_json_string_form_is_merged_too(self):
        stored = json.dumps({"api_key": "sk-old1234567890", "group_id": "111"})
        incoming = json.dumps({"api_key": mask_secret("sk-old1234567890")})
        merged = json.loads(resolve_secret_on_write(incoming, stored))
        assert merged["api_key"] == "sk-old1234567890"
        assert merged["group_id"] == "111"


class TestClientSuppliedSecret:
    def test_nothing_supplied(self):
        assert not client_supplied_secret(None)
        assert not client_supplied_secret("")
        assert not client_supplied_secret("   ")

    def test_mask_is_not_treated_as_supplied(self):
        assert not client_supplied_secret(mask_secret(STORED))

    def test_real_credential_is_supplied(self):
        assert client_supplied_secret("sk-newkey9876543210")

    def test_bundle_of_only_masks_is_not_supplied(self):
        assert not client_supplied_secret({"api_key": mask_secret(STORED)})

    def test_bundle_with_a_real_field_is_supplied(self):
        assert client_supplied_secret({"api_key": mask_secret(STORED), "group_id": "222"})

    def test_empty_bundle_is_not_supplied(self):
        assert not client_supplied_secret({})
