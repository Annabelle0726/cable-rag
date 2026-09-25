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
"""An assistant belongs to a WORKSPACE, and every member of it may use one.

A NORMAL member owns no tenant, so their user id is not a tenant id: only the
creator of a workspace has `tenant.id == user.id`. Two consequences, and this
file pins both:

* an assistant must be bound to the workspace resolved from `X-Tenant-Id` /
  membership, because that is the tenant its chat, rerank and TTS models are
  resolved in and the tenant its sessions are read through. Bound to the
  creator's user id instead, the assistant could not be read back (`GET
  /chats/<id>` answered `109 no authorization`), no model could be saved into it
  (``llm_id … doesn't exist``, code 102) and a turn could not resolve a model at
  all;
* access is "creator OR member of the owning workspace". Both halves are needed:
  the creator half keeps a personal workspace (which IS the user id) and every
  assistant created before this change working, and the membership half is what
  lets an administrator or a member use the workspace's assistants.

A caller who is neither is refused with code **108** (a permission denial). 109
is the authentication code, and it used to be the answer for an assistant the
caller had just created itself.
"""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest

from api.apps.restful_apis import chat_api

MEMBER_ID = "member-1"
WORKSPACE_ID = "ws-1"
OTHER_WORKSPACE_ID = "ws-2"
CHAT_ID = "chat-1"


class _AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


_DEFAULT_CHAT = {
    "id": CHAT_ID,
    "tenant_id": WORKSPACE_ID,
    "status": "1",
    "name": "member_chat",
    "description": "A helpful Assistant",
    "icon": "",
    "kb_ids": [],
    "llm_id": "ws-model",
    "llm_setting": {},
    "prompt_config": {"system": "", "prologue": "", "parameters": []},
}


def _chat_payload(**overrides):
    data = deepcopy(_DEFAULT_CHAT)
    data.update(overrides)
    return data


class _FakeDialog:
    def __init__(self, data=None):
        self._data = _chat_payload() if data is None else deepcopy(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(name) from None

    def to_dict(self):
        return deepcopy(self._data)


class _FakeDialogService:
    """The dialog table, recording the ownership the routes write and read."""

    def __init__(self, existing=None):
        self.saved = {}
        self.updated = {}
        self.queries = []
        self.list_calls = []
        self._existing = existing or _FakeDialog()

    def query(self, **kwargs):
        self.queries.append(kwargs)
        # A name lookup is the duplicate-name guard; anything else is an
        # existence check for a specific row.
        return [] if kwargs.get("name") else [self._existing]

    def save(self, **kwargs):
        self.saved.update(kwargs)
        return True

    def get_by_id(self, _chat_id):
        return True, self._existing

    def update_by_id(self, _chat_id, payload):
        self.updated.update(payload)
        return True

    def get_by_tenant_ids(self, joined_tenant_ids, user_id, *args, **kwargs):
        self.list_calls.append((list(joined_tenant_ids), user_id))
        return [], 0


@pytest.fixture
def workspace(monkeypatch):
    """A member with no tenant of its own, working in `ws-1`."""
    state = SimpleNamespace(
        resolved=[],
        tenant_lookups=[],
        membership_lookups=[],
        normalizations=[],
        dialogs=_FakeDialogService(),
        memberships=[SimpleNamespace(tenant_id=WORKSPACE_ID, user_id=MEMBER_ID)],
    )

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state.resolved.append((user_id, requested_tenant_id))
        return WORKSPACE_ID

    def get_by_id(tenant_id):
        state.tenant_lookups.append(tenant_id)
        if tenant_id == WORKSPACE_ID:
            return True, SimpleNamespace(id=WORKSPACE_ID, llm_id="ws-model", tenant_llm_id="ws-model")
        # The member's own id is not a tenant: this is what answered 102 before.
        return False, None

    def user_tenant_query(**kwargs):
        state.membership_lookups.append(kwargs)
        tenant_id = kwargs.get("tenant_id")
        return [row for row in state.memberships if row.tenant_id == tenant_id and row.user_id == kwargs.get("user_id")]

    async def thread_pool_exec(func, *args, **kwargs):
        return func(*args, **kwargs)

    def get_model_config_by_id(tenant_id, model_type, _model_id):
        # A model id lookup is only meaningful inside the tenant that owns the
        # model, so the tenant it was asked about is the subject under test.
        state.normalizations.append((tenant_id, model_type))
        raise LookupError("not a tenant model id")

    def resolve_model_id(tenant_id, model_type, model_name):
        state.normalizations.append((tenant_id, model_type))
        return model_name

    monkeypatch.setattr(chat_api, "current_user", SimpleNamespace(id=MEMBER_ID))
    monkeypatch.setattr(chat_api, "requested_tenant_id", lambda: WORKSPACE_ID)
    monkeypatch.setattr(chat_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id, get_by_id=get_by_id))
    monkeypatch.setattr(chat_api, "UserTenantService", SimpleNamespace(query=user_tenant_query))
    monkeypatch.setattr(chat_api, "DialogService", state.dialogs)
    monkeypatch.setattr(chat_api, "thread_pool_exec", thread_pool_exec)
    monkeypatch.setattr(chat_api, "get_model_config_by_id", get_model_config_by_id)
    monkeypatch.setattr(chat_api, "resolve_model_id", resolve_model_id)
    return state


def _set_request(monkeypatch, payload):
    monkeypatch.setattr(chat_api, "get_request_json", lambda: _AwaitableValue(payload))


class _Args(dict):
    """A `request.args` stand-in: the listing reads `.get` and `.getlist`."""

    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


def _set_query(monkeypatch, args=None):
    monkeypatch.setattr(chat_api, "request", SimpleNamespace(args=_Args(args or {})))


# ---------------------------------------------------------------------------
# Creating: bound to the workspace whose models it uses
# ---------------------------------------------------------------------------


def test_member_creates_an_assistant_in_the_resolved_workspace(workspace, monkeypatch):
    _set_request(monkeypatch, {"name": "member_chat"})

    res = asyncio.run(chat_api.create.__wrapped__())

    assert res["code"] == 0, res
    # The workspace is resolved for the member and it is the tenant row that was
    # read -- `member-1` is never looked up as a tenant.
    assert workspace.resolved == [(MEMBER_ID, WORKSPACE_ID)]
    assert workspace.tenant_lookups == [WORKSPACE_ID]
    # ... and its model defaults come from there.
    assert workspace.dialogs.saved["llm_id"] == "ws-model"
    assert workspace.dialogs.saved["tenant_llm_id"] == "ws-model"
    assert workspace.dialogs.saved["name"] == "member_chat"


def test_the_created_assistant_is_bound_to_that_workspace(workspace, monkeypatch):
    """The workspace owns the models, so the workspace is what the row names.

    Keyed on the creator's user id instead, the tenant of this row is a user id
    that is not a tenant at all: `GET /chats/<id>` then matched none of the
    caller's memberships and answered 109 for the assistant it had just made.
    """
    _set_request(monkeypatch, {"name": "member_chat"})

    asyncio.run(chat_api.create.__wrapped__())

    assert workspace.dialogs.saved["tenant_id"] == WORKSPACE_ID


def test_the_model_pair_is_validated_in_the_workspace_not_the_caller(workspace, monkeypatch):
    _set_request(monkeypatch, {"name": "member_chat", "llm_id": "ws-model"})

    asyncio.run(chat_api.create.__wrapped__())

    assert [tenant_id for tenant_id, _field in workspace.normalizations] == [WORKSPACE_ID, WORKSPACE_ID]


def test_a_member_without_a_workspace_is_refused_cleanly(workspace, monkeypatch):
    # No membership at all: the resolver falls back to the caller's id, which is
    # no tenant. The route must answer 102, not raise an IndexError.
    monkeypatch.setattr(chat_api.TenantService, "resolve_active_tenant_id", lambda _user_id, _requested_tenant_id=None: MEMBER_ID)
    _set_request(monkeypatch, {"name": "member_chat"})

    res = asyncio.run(chat_api.create.__wrapped__())

    assert res["code"] == 102, res
    assert res["message"] == "Tenant not found!"
    assert workspace.dialogs.saved == {}


# ---------------------------------------------------------------------------
# Reading and updating: creator OR member of the owning workspace
# ---------------------------------------------------------------------------


def test_a_member_of_the_owning_workspace_can_read_the_assistant(workspace):
    """The reported defect: this answered `109 no authorization`."""
    res = asyncio.run(chat_api.get_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 0, res
    assert res["data"]["id"] == CHAT_ID
    assert workspace.membership_lookups == [{"user_id": MEMBER_ID, "tenant_id": WORKSPACE_ID}]


def test_a_member_of_the_owning_workspace_can_save_a_model_into_it(workspace, monkeypatch):
    """The other half of the defect: this answered 102 `llm_id … doesn't exist`."""
    _set_request(monkeypatch, {"llm_id": "ws-model", "name": "renamed"})

    res = asyncio.run(chat_api.patch_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 0, res
    assert workspace.dialogs.updated["name"] == "renamed"
    # The model is resolved in the assistant's own workspace -- the member's user
    # id owns no models at all.
    assert [tenant_id for tenant_id, _field in workspace.normalizations] == [WORKSPACE_ID, WORKSPACE_ID]


def test_an_assistant_owned_by_the_caller_needs_no_membership(workspace, monkeypatch):
    """A personal workspace IS the user id, and pre-change rows carry it too."""
    workspace.dialogs._existing = _FakeDialog(_chat_payload(tenant_id=MEMBER_ID))

    res = asyncio.run(chat_api.get_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 0, res
    assert workspace.membership_lookups == [], "the creator branch answers without a membership lookup"


def test_a_stranger_is_refused_as_a_permission_error(workspace, monkeypatch):
    """Not 109: 109 means the session is not authenticated, and it is."""
    workspace.memberships = []
    workspace.dialogs._existing = _FakeDialog(_chat_payload(tenant_id=OTHER_WORKSPACE_ID))

    res = asyncio.run(chat_api.get_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 108, res
    assert res["message"] == "no authorization"


def test_a_deleted_assistant_is_not_accessible(workspace, monkeypatch):
    workspace.dialogs._existing = _FakeDialog(_chat_payload(status="0"))

    res = asyncio.run(chat_api.get_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 108, res


def test_a_stranger_cannot_save_settings_on_someone_elses_assistant(workspace, monkeypatch):
    workspace.memberships = []
    workspace.dialogs._existing = _FakeDialog(_chat_payload(tenant_id=OTHER_WORKSPACE_ID))
    _set_request(monkeypatch, {"name": "hijacked"})

    res = asyncio.run(chat_api.patch_chat.__wrapped__(CHAT_ID))

    assert res["code"] == 108, res
    assert workspace.dialogs.updated == {}


def test_a_stranger_cannot_chat_with_someone_elses_assistant(workspace, monkeypatch):
    workspace.memberships = []
    workspace.dialogs._existing = _FakeDialog(_chat_payload(tenant_id=OTHER_WORKSPACE_ID))
    _set_request(monkeypatch, {"chat_id": CHAT_ID, "messages": [{"role": "user", "content": "hi"}]})

    res = asyncio.run(chat_api.session_completion.__wrapped__())

    assert res["code"] == 108, res


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_the_chat_list_is_scoped_to_the_workspace_and_the_caller(workspace, monkeypatch):
    """The workspace's assistants, plus the caller's own (personal / legacy)."""
    _set_query(monkeypatch)

    asyncio.run(chat_api.list_chats.__wrapped__())

    assert workspace.dialogs.list_calls == [([WORKSPACE_ID], MEMBER_ID)]
