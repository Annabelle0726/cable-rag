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
"""A search app is personally private; the models it runs on are the workspace's.

The same split as chat, pinned at the Search surface: `created_by` owns the app
(nobody else may list, read or delete it), `tenant_id` is the workspace whose
chat/rerank models answer it. Reading an app back through the caller's
memberships - which is what `GET /searches/<id>` used to do - let any member of a
workspace open a colleague's app, and binding `tenant_id` to the caller's user id
(not a tenant at all for a member) made the completion resolve models against an
account that owns none.
"""

import asyncio
from types import SimpleNamespace

import pytest

from api.apps.restful_apis import search_api

MEMBER_ID = "member-1"
COLLEAGUE_ID = "colleague-1"
WORKSPACE_ID = "ws-1"
SEARCH_ID = "search-1"

_APP = {
    "id": SEARCH_ID,
    "tenant_id": WORKSPACE_ID,
    "created_by": MEMBER_ID,
    "name": "mine",
    "search_config": {"kb_ids": ["kb-1"]},
}


class _FakeSearchService:
    """The search table, answering exactly what the routes ask it."""

    def __init__(self, app=None):
        self.app = dict(app or _APP)
        self.saved = {}
        self.list_calls = []
        self.deleted = []

    # ownership: the same predicate `SearchService.accessible4deletion` uses
    def accessible4deletion(self, search_id, user_id):
        return search_id == self.app["id"] and self.app["created_by"] == user_id

    def get_detail(self, _search_id):
        return dict(self.app)

    def get_by_tenant_ids(self, joined_tenant_ids, user_id, *args, **kwargs):
        self.list_calls.append((list(joined_tenant_ids), user_id, kwargs.get("created_by")))
        return [], 0

    def save(self, **kwargs):
        self.saved.update(kwargs)
        return True

    def delete_by_id(self, search_id):
        self.deleted.append(search_id)
        return True

    def query(self, **kwargs):
        if "name" in kwargs:
            return []
        if kwargs.get("id") == self.app["id"] and kwargs.get("created_by") == self.app["created_by"]:
            return [SimpleNamespace(name=self.app["name"], search_config=self.app["search_config"])]
        return []


class _NullAtomic:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


@pytest.fixture
def searches(monkeypatch):
    service = _FakeSearchService()
    state = SimpleNamespace(service=service, asked=[], tenant_lookups=[])

    def resolve_active_tenant_id(user_id, requested_tenant_id=None):
        state.asked.append((user_id, requested_tenant_id))
        return WORKSPACE_ID

    def get_by_id(tenant_id):
        state.tenant_lookups.append(tenant_id)
        return (tenant_id == WORKSPACE_ID), SimpleNamespace(id=WORKSPACE_ID)

    monkeypatch.setattr(search_api, "current_user", SimpleNamespace(id=MEMBER_ID))
    monkeypatch.setattr(search_api, "requested_tenant_id", lambda: WORKSPACE_ID)
    monkeypatch.setattr(search_api, "TenantService", SimpleNamespace(resolve_active_tenant_id=resolve_active_tenant_id, get_by_id=get_by_id))
    monkeypatch.setattr(search_api, "SearchService", service)
    monkeypatch.setattr(search_api, "DB", SimpleNamespace(atomic=_NullAtomic))
    monkeypatch.setattr(search_api, "duplicate_name", lambda _query, name, **_kwargs: name)
    monkeypatch.setattr(search_api, "validate_request", lambda *_fields: (lambda func: func))
    return state


class _Args(dict):
    """A `request.args` stand-in: the listing reads `.get` and `.getlist`."""

    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        return value if isinstance(value, list) else [value]


def _set_query(monkeypatch, args=None):
    monkeypatch.setattr(search_api, "request", SimpleNamespace(args=_Args(args or {})))


class _AwaitableValue:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


def _set_request(monkeypatch, payload):
    monkeypatch.setattr(search_api, "get_request_json", lambda: _AwaitableValue(payload))


def _route(func):
    """The route body with every decorator peeled off.

    `@validate_request` and `@login_required` are applied at import time, so
    stubbing them afterwards cannot help; what these tests are about is the
    authorization INSIDE the body, and the decorators around it are covered by
    the routes that do not need a request context.
    """
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


# ---------------------------------------------------------------------------
# Listing
# ---------------------------------------------------------------------------


def test_the_search_list_is_scoped_to_the_caller_and_its_workspace(searches, monkeypatch):
    _set_query(monkeypatch)

    res = _route(search_api.list_searches)()

    assert res["code"] == 0, res
    assert searches.service.list_calls == [([WORKSPACE_ID], MEMBER_ID, MEMBER_ID)]


# ---------------------------------------------------------------------------
# Reading / writing one app
# ---------------------------------------------------------------------------


def test_the_creator_can_read_its_own_app(searches):
    res = _route(search_api.detail)(SEARCH_ID)

    assert res["code"] == 0, res
    assert res["data"]["id"] == SEARCH_ID


def test_a_colleague_cannot_read_it(searches):
    """Membership is not ownership: this answered with the colleague's app."""
    searches.service.app["created_by"] = COLLEAGUE_ID

    res = _route(search_api.detail)(SEARCH_ID)

    assert res["code"] == 108, res
    assert res["message"] == "no authorization"


def test_a_colleague_cannot_delete_it(searches):
    searches.service.app["created_by"] = COLLEAGUE_ID

    res = _route(search_api.delete_search)(SEARCH_ID)

    assert res["code"] == 108, res
    assert searches.service.deleted == []


def test_a_colleague_cannot_run_it(searches, monkeypatch):
    searches.service.app["created_by"] = COLLEAGUE_ID
    _set_request(monkeypatch, {"question": "hi"})

    res = asyncio.run(_route(search_api.completion)(SEARCH_ID))

    assert res["code"] == 108, res


def test_creating_an_app_binds_the_workspace_and_the_creator(searches, monkeypatch):
    _set_request(monkeypatch, {"name": "mine"})

    res = asyncio.run(_route(search_api.create)())

    assert res["code"] == 0, res
    assert searches.service.saved["tenant_id"] == WORKSPACE_ID
    assert searches.service.saved["created_by"] == MEMBER_ID
    # The workspace is resolved through the resolver; the caller's user id is
    # never used as a tenant.
    assert searches.asked == [(MEMBER_ID, WORKSPACE_ID)]
    assert searches.tenant_lookups == [WORKSPACE_ID]
