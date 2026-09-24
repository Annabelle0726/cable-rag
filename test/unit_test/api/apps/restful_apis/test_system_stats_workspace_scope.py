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
"""Whose usage `/system/stats` reports.

A NORMAL member owns no tenant, so `user.id` is not a tenant id, and the
unfiltered membership query the route used returned the member's joined
workspace -- fine for `tenants[0]` by luck, but the wrong workspace whenever the
caller belongs to several, and a revoked or not-yet-accepted INVITE row could be
picked just as well. The stats must belong to the caller's ACTIVE workspace.
"""

from types import SimpleNamespace

import pytest

from api.apps.restful_apis import stats_api

USER_ID = "user-1"
WORKSPACE_ID = "ws-1"
OTHER_WORKSPACE_ID = "ws-9"


class _Args(dict):
    def get(self, key, default=None):
        return super().get(key, default)


@pytest.fixture
def stats_env(monkeypatch):
    state = {
        "resolved": [],
        "memberships": [{"tenant_id": WORKSPACE_ID, "role": "normal"}],
        "active": WORKSPACE_ID,
        "reported": [],
    }

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state["resolved"].append((user_id, requested_tenant_id))
        return state["active"]

    monkeypatch.setattr(stats_api, "current_user", SimpleNamespace(id=USER_ID))
    monkeypatch.setattr(stats_api, "requested_tenant_id", lambda: None)
    monkeypatch.setattr(stats_api, "request", SimpleNamespace(args=_Args()))
    monkeypatch.setattr(stats_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id))
    monkeypatch.setattr(stats_api, "UserTenantService", SimpleNamespace(get_tenants_by_user_id=lambda _user_id: state["memberships"]))
    monkeypatch.setattr(stats_api, "API4ConversationService", SimpleNamespace(stats=lambda tenant_id, _from_date, _to_date, _source: state["reported"].append(tenant_id) or []))
    return state


def test_a_member_gets_the_active_workspace_stats(stats_env):
    res = stats_api.stats.__wrapped__()

    assert res["code"] == 0, res
    assert stats_env["reported"] == [WORKSPACE_ID]
    assert stats_env["resolved"] == [(USER_ID, None)]
    assert set(res["data"]) == {"pv", "uv", "speed", "tokens", "round", "thumb_up"}


def test_the_requested_workspace_is_the_one_reported(stats_env, monkeypatch):
    # A member of two workspaces naming the second one with `X-Tenant-Id`.
    stats_env["memberships"] = [{"tenant_id": WORKSPACE_ID, "role": "normal"}, {"tenant_id": OTHER_WORKSPACE_ID, "role": "normal"}]
    stats_env["active"] = OTHER_WORKSPACE_ID
    monkeypatch.setattr(stats_api, "requested_tenant_id", lambda: OTHER_WORKSPACE_ID)

    res = stats_api.stats.__wrapped__()

    assert res["code"] == 0, res
    assert stats_env["resolved"] == [(USER_ID, OTHER_WORKSPACE_ID)]
    assert stats_env["reported"] == [OTHER_WORKSPACE_ID]


def test_a_user_with_no_workspace_is_refused_cleanly(stats_env):
    stats_env["memberships"] = []

    res = stats_api.stats.__wrapped__()

    assert res["code"] == 102, res
    assert res["message"] == "Tenant not found!"
    assert stats_env["reported"] == []
