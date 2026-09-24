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
"""Registering an MCP server from inside a shared workspace.

`POST /mcp/servers` checked that the caller had a tenant by reading the tenant
row off `current_user.id`. A NORMAL member owns no tenant, so the check answered
`Tenant not found.` (code 102) to every member.

The workspace is now resolved instead. The ROW keeps the caller's user id: an
`mcp_server` row is user-scoped in this codebase -- list, detail, update, delete,
import and export all compare its `tenant_id` column with `current_user.id` --
so writing any other id there would hide the server from its creator.
"""

import asyncio
import contextlib
from types import SimpleNamespace

import pytest

from api.apps.restful_apis import mcp_api

MEMBER_ID = "member-1"
WORKSPACE_ID = "ws-1"


class _AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


@pytest.fixture
def workspace(monkeypatch):
    """A NORMAL member with no tenant of its own, working in `ws-1`."""
    state = {"resolved": [], "tenant_lookups": [], "inserted": {}}

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state["resolved"].append((user_id, requested_tenant_id))
        return WORKSPACE_ID

    def get_by_id(tenant_id):
        state["tenant_lookups"].append(tenant_id)
        # The member's own id is not a tenant: this is what answered 102 before.
        return (True, SimpleNamespace(id=WORKSPACE_ID)) if tenant_id == WORKSPACE_ID else (False, None)

    async def thread_pool_exec(_func, servers, _timeout):
        return {servers[0].name: [{"name": "tool_a"}]}, None

    @contextlib.contextmanager
    def pin_dns_global(_hostname, _resolved_ip):
        yield

    monkeypatch.setattr(mcp_api, "current_user", SimpleNamespace(id=MEMBER_ID))
    monkeypatch.setattr(mcp_api, "requested_tenant_id", lambda: WORKSPACE_ID)
    monkeypatch.setattr(mcp_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id, get_by_id=get_by_id))
    monkeypatch.setattr(mcp_api, "MCPServerService", SimpleNamespace(get_by_name_and_tenant=lambda **_kwargs: (False, None), insert=lambda **kwargs: state["inserted"].update(kwargs) or True))
    monkeypatch.setattr(mcp_api, "assert_url_is_safe", lambda _url: ("mcp.example", "127.0.0.1"))
    monkeypatch.setattr(mcp_api, "pin_dns_global", pin_dns_global)
    monkeypatch.setattr(mcp_api, "thread_pool_exec", thread_pool_exec)
    monkeypatch.setattr(mcp_api, "get_request_json", lambda: _AwaitableValue({"name": "srv", "url": "http://mcp.example", "server_type": "sse"}))

    return state


def test_member_registers_an_mcp_server(workspace):
    res = asyncio.run(mcp_api.create.__wrapped__.__wrapped__())

    assert res["code"] == 0, res
    # The workspace was resolved for the member and it is the tenant row that was
    # read; the member's own id is never looked up as a tenant.
    assert workspace["resolved"] == [(MEMBER_ID, WORKSPACE_ID)]
    assert workspace["tenant_lookups"] == [WORKSPACE_ID]
    # The row stays user-scoped, so the member can read it back.
    assert workspace["inserted"]["tenant_id"] == MEMBER_ID
    assert workspace["inserted"]["variables"]["tools"] == {"tool_a": {"name": "tool_a"}}


def test_member_without_a_workspace_is_refused_cleanly(workspace, monkeypatch):
    monkeypatch.setattr(mcp_api.TenantService, "resolve_active_tenant_id", lambda _user_id, _requested_tenant_id=None: MEMBER_ID)

    res = asyncio.run(mcp_api.create.__wrapped__.__wrapped__())

    assert res["code"] == 102, res
    assert res["message"] == "Tenant not found."
    assert workspace["inserted"] == {}
