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
"""Creating and updating an assistant from inside a shared workspace.

A NORMAL member owns no tenant, so their user id is not a tenant id: only the
creator of a workspace has `tenant.id == user.id`. `POST /chats` and
`PUT`/`PATCH /chats/<id>` read the tenant row off `current_user.id`, so every
member was answered `Tenant not found!` (code 102) without ever reaching the
assistant.

These tests pin both halves of the fix:

* the workspace is RESOLVED (the caller's active one, or the one named by
  `X-Tenant-Id`), and its tenant row supplies the assistant's model defaults;
* the assistant row still records the CREATOR as its `tenant_id`, which is the
  ownership `_ensure_owned_chat`, the chat list and the chat completion path
  read -- otherwise the member could create an assistant it could not use.
"""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from api.apps.restful_apis import chat_api

MEMBER_ID = "member-1"
WORKSPACE_ID = "ws-1"


class _AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


class _FakeDialog:
    def __init__(self, data=None):
        self._data = deepcopy(data) if data else {
            "id": "chat-1",
            "tenant_id": MEMBER_ID,
            "name": "member_chat",
            "description": "A helpful Assistant",
            "icon": "",
            "kb_ids": [],
            "llm_id": "ws-model",
            "llm_setting": {},
            "prompt_config": {"system": "", "prologue": "", "parameters": []},
        }

    def to_dict(self):
        return deepcopy(self._data)


class _FakeDialogService:
    """The dialog table, recording the ownership the route writes and reads."""

    def __init__(self, existing=None):
        self.saved = {}
        self.updated = {}
        self.queries = []
        self._existing = existing or _FakeDialog()

    def query(self, **kwargs):
        self.queries.append(kwargs)
        # A name lookup is the duplicate-name guard; an id lookup is the
        # ownership guard of `_ensure_owned_chat`.
        return [] if kwargs.get("name") else [self._existing]

    def save(self, **kwargs):
        self.saved.update(kwargs)
        return True

    def get_by_id(self, _chat_id):
        return True, self._existing

    def update_by_id(self, _chat_id, payload):
        self.updated.update(payload)
        return True


@pytest.fixture
def workspace(monkeypatch):
    """A NORMAL member with no tenant of its own, working in `ws-1`."""
    state = {"resolved": [], "tenant_lookups": []}
    dialogs = _FakeDialogService()

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state["resolved"].append((user_id, requested_tenant_id))
        return WORKSPACE_ID

    def get_by_id(tenant_id):
        state["tenant_lookups"].append(tenant_id)
        if tenant_id == WORKSPACE_ID:
            return True, SimpleNamespace(llm_id="ws-model", tenant_llm_id="ws-model")
        # The member's own id is not a tenant: this is what answered 102 before.
        return False, None

    def get_model_config_by_id(_tenant_id, _model_type, _model_id):
        raise LookupError("not a tenant model id")

    async def thread_pool_exec(func, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(chat_api, "current_user", SimpleNamespace(id=MEMBER_ID))
    monkeypatch.setattr(chat_api, "requested_tenant_id", lambda: WORKSPACE_ID)
    monkeypatch.setattr(chat_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id, get_by_id=get_by_id))
    monkeypatch.setattr(chat_api, "DialogService", dialogs)
    monkeypatch.setattr(chat_api, "thread_pool_exec", thread_pool_exec)
    monkeypatch.setattr(chat_api, "get_model_config_by_id", get_model_config_by_id)
    monkeypatch.setattr(chat_api, "resolve_model_id", lambda _tenant_id, _model_type, model_name: model_name)
    state["dialogs"] = dialogs
    return state


def _set_request(monkeypatch, payload):
    monkeypatch.setattr(chat_api, "get_request_json", lambda: _AwaitableValue(payload))


def test_member_creates_an_assistant_in_the_resolved_workspace(workspace, monkeypatch):
    _set_request(monkeypatch, {"name": "member_chat"})

    res = asyncio.run(chat_api.create.__wrapped__())

    assert res["code"] == 0, res
    # The workspace is resolved for the member and it is the tenant row that was
    # read -- `member-1` is never looked up as a tenant.
    assert workspace["resolved"] == [(MEMBER_ID, WORKSPACE_ID)]
    assert workspace["tenant_lookups"] == [WORKSPACE_ID]
    # ... and the assistant is scoped to it: its model defaults come from there.
    assert workspace["dialogs"].saved["llm_id"] == "ws-model"
    assert workspace["dialogs"].saved["tenant_llm_id"] == "ws-model"
    assert workspace["dialogs"].saved["name"] == "member_chat"


def test_the_created_assistant_stays_owned_by_its_creator(workspace, monkeypatch):
    _set_request(monkeypatch, {"name": "member_chat"})

    asyncio.run(chat_api.create.__wrapped__())

    # `_ensure_owned_chat`, the chat list and the completion path all read
    # `tenant_id` as the creator's user id, so an assistant the member created
    # must carry it: keyed on the workspace instead, the member could not have
    # updated, deleted or chatted with its own assistant.
    assert workspace["dialogs"].saved["tenant_id"] == MEMBER_ID


def test_member_updates_its_own_assistant(workspace, monkeypatch):
    _set_request(monkeypatch, {"name": "renamed"})

    res = asyncio.run(chat_api.patch_chat.__wrapped__("chat-1"))

    assert res["code"] == 0, res
    assert workspace["resolved"] == [(MEMBER_ID, WORKSPACE_ID)]
    assert workspace["dialogs"].updated["name"] == "renamed"
    # The ownership guard still answers for the creator, and only for them.
    assert workspace["dialogs"].queries[0]["tenant_id"] == MEMBER_ID


def test_member_without_a_workspace_is_refused_cleanly(workspace, monkeypatch):
    # No membership at all: the resolver falls back to the caller's id, which is
    # no tenant. The route must answer 102, not raise an IndexError.
    monkeypatch.setattr(chat_api.TenantService, "resolve_active_tenant_id", lambda _user_id, _requested_tenant_id=None: MEMBER_ID)
    _set_request(monkeypatch, {"name": "member_chat"})

    res = asyncio.run(chat_api.create.__wrapped__())

    assert res["code"] == 102, res
    assert res["message"] == "Tenant not found!"
    assert workspace["dialogs"].saved == {}
