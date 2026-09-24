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
"""Whose API key `/system/tokens` reads, creates and deletes.

The list and create routes picked the caller's OWNER membership out of an
unfiltered query with `[t for t in tenants if t.role == "owner"][0]`. A NORMAL
member has no OWNER row, so the index raised `IndexError` and the request
answered HTTP 500; delete and the stats route used `tenants[0]` of the same
unfiltered list, which is an arbitrary workspace -- a revoked one or a pending
INVITE included.

These tests pin the refusal (a member gets a clean code 108, never a 500) and
that the key belongs to the caller's ACTIVE workspace rather than to list order.
"""

from types import SimpleNamespace

import pytest

from api.apps.restful_apis import system_api

USER_ID = "user-1"
WORKSPACE_ID = "ws-1"
OTHER_WORKSPACE_ID = "ws-9"


class _ExprField:
    """`APIToken.tenant_id == value` as an inspectable tuple, no database."""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return (self.name, other)


class _FakeAPIToken:
    tenant_id = _ExprField("tenant_id")
    token = _ExprField("token")


@pytest.fixture
def tokens(monkeypatch):
    state = {
        "resolved": [],
        "memberships": [{"tenant_id": WORKSPACE_ID, "role": "owner"}],
        "active": WORKSPACE_ID,
        "queried": [],
        "saved": [],
        "deleted": [],
    }

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state["resolved"].append((user_id, requested_tenant_id))
        return state["active"]

    monkeypatch.setattr(system_api, "current_user", SimpleNamespace(id=USER_ID))
    monkeypatch.setattr(system_api, "requested_tenant_id", lambda: None)
    monkeypatch.setattr(system_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id))
    monkeypatch.setattr(system_api, "UserTenantService", SimpleNamespace(get_tenants_by_user_id=lambda _user_id: state["memberships"]))
    monkeypatch.setattr(system_api, "APIToken", _FakeAPIToken)
    monkeypatch.setattr(
        system_api,
        "APITokenService",
        SimpleNamespace(
            query=lambda **kwargs: state["queried"].append(kwargs) or [],
            filter_update=lambda *_args, **_kwargs: True,
            save=lambda **kwargs: state["saved"].append(kwargs) or True,
            filter_delete=lambda conditions: state["deleted"].append(conditions) or True,
        ),
    )
    return state


def test_a_member_is_refused_cleanly_on_every_token_route(tokens):
    # A NORMAL member: belongs to the workspace, owns none.
    tokens["memberships"] = [{"tenant_id": WORKSPACE_ID, "role": "normal"}]

    for route, call in (
        ("GET /system/tokens", lambda: system_api.token_list.__wrapped__()),
        ("POST /system/tokens", lambda: system_api.new_token.__wrapped__()),
        ("DELETE /system/tokens/<token>", lambda: system_api.rm.__wrapped__("token-1")),
    ):
        res = call()
        assert res["code"] == 108, (route, res)
        assert "owner role required" in res["message"], (route, res)

    # Nothing was read, written or deleted on the member's behalf.
    assert tokens["queried"] == []
    assert tokens["saved"] == []
    assert tokens["deleted"] == []


def test_a_user_with_no_workspace_is_refused_cleanly(tokens, monkeypatch):
    tokens["memberships"] = []
    # The resolver falls back to the caller's id, which is no tenant at all.
    monkeypatch.setattr(system_api.TenantService, "resolve_active_tenant_id", lambda _user_id, _requested_tenant_id=None: USER_ID)

    assert system_api.token_list.__wrapped__()["code"] == 108
    assert system_api.new_token.__wrapped__()["code"] == 108
    assert system_api.rm.__wrapped__("token-1")["code"] == 108


def test_the_key_belongs_to_the_active_workspace(tokens):
    # Owner of two workspaces, currently working in the SECOND one.
    tokens["memberships"] = [
        {"tenant_id": WORKSPACE_ID, "role": "owner"},
        {"tenant_id": OTHER_WORKSPACE_ID, "role": "owner"},
    ]
    tokens["active"] = OTHER_WORKSPACE_ID

    assert system_api.token_list.__wrapped__()["code"] == 0
    assert tokens["queried"] == [{"tenant_id": OTHER_WORKSPACE_ID}]

    assert system_api.new_token.__wrapped__()["code"] == 0
    assert tokens["saved"][0]["tenant_id"] == OTHER_WORKSPACE_ID

    assert system_api.rm.__wrapped__("token-1")["code"] == 0
    assert tokens["deleted"][0] == [("tenant_id", OTHER_WORKSPACE_ID), ("token", "token-1")]

    assert tokens["resolved"] == [(USER_ID, None)] * 3
