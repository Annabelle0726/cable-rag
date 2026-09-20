#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
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
"""Which model the conversation titler runs on.

`_resolve_title_model_config` is exercised directly, with the three resolvers
stubbed: it is the whole of the choice, and the endpoint around it needs an
authenticated tenant plus a working model.

The last fallback is the point of these tests. Titling used to resolve only the
requested model or the tenant default, so a tenant whose chat model was configured
and usable but never marked as the default got its raw first question back as the
title — forever, and with nothing in the log to say why.
"""

import pytest

from api.apps.restful_apis import chat_api


@pytest.fixture
def resolvers(monkeypatch):
    """Stub the three lookups and record which ones were consulted."""
    state = {"requested": [], "default_called": 0, "fallback_called": 0, "fallback_name": None}

    def resolve_model_config(tenant_id, model_type, model_ref):
        state["requested"].append(model_ref)
        if model_ref == "resolvable":
            return {"llm_name": "resolvable", "model_type": model_type.value if hasattr(model_type, "value") else model_type}
        raise LookupError(f"cannot resolve {model_ref}")

    def get_tenant_default_model_by_type(tenant_id, model_type):
        state["default_called"] += 1
        if state.get("has_default"):
            return {"llm_name": "the-default", "model_type": "chat"}
        raise Exception(f"No default {model_type} model is set.")

    def get_first_tenant_model_name_by_type(tenant_id, model_type):
        state["fallback_called"] += 1
        return state["fallback_name"]

    monkeypatch.setattr(chat_api, "resolve_model_config", resolve_model_config)
    monkeypatch.setattr(chat_api, "get_tenant_default_model_by_type", get_tenant_default_model_by_type)
    monkeypatch.setattr(chat_api, "get_first_tenant_model_name_by_type", get_first_tenant_model_name_by_type)

    return state


def test_the_requested_model_wins(resolvers):
    config = chat_api._resolve_title_model_config("tenant-1", "resolvable")

    assert config == {"llm_name": "resolvable", "model_type": "chat"}
    assert resolvers["default_called"] == 0
    assert resolvers["fallback_called"] == 0


def test_the_tenant_default_is_used_when_no_model_was_requested(resolvers):
    resolvers["has_default"] = True

    config = chat_api._resolve_title_model_config("tenant-1", "")

    assert config == {"llm_name": "the-default", "model_type": "chat"}
    assert resolvers["fallback_called"] == 0


def test_an_unresolvable_requested_model_falls_through_to_the_default(resolvers):
    resolvers["has_default"] = True

    config = chat_api._resolve_title_model_config("tenant-1", "gone-after-a-rebuild")

    assert config == {"llm_name": "the-default", "model_type": "chat"}


def test_a_tenant_with_no_default_is_titled_with_a_configured_model(resolvers):
    resolvers["fallback_name"] = "resolvable"

    config = chat_api._resolve_title_model_config("tenant-1", "")

    assert config == {"llm_name": "resolvable", "model_type": "chat"}
    assert resolvers["fallback_called"] == 1


def test_a_tenant_with_no_chat_model_at_all_resolves_to_nothing(resolvers):
    # The endpoint turns this into a message naming what to configure, instead of the
    # empty title that used to be indistinguishable from "the model said nothing".
    assert chat_api._resolve_title_model_config("tenant-1", "") is None
    assert resolvers["fallback_called"] == 1


def test_a_configured_model_that_no_longer_resolves_also_yields_nothing(resolvers):
    resolvers["fallback_name"] = "stale-name"

    assert chat_api._resolve_title_model_config("tenant-1", "") is None
