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
"""``PATCH /users/me/models`` writes a workspace the caller may administer.

``GET /users/me/models`` answers the caller's ACTIVE workspace, which is a shared
workspace rather than its own id whenever the caller is working in one. The write
refused anything but ``current_user.id``, so echoing the id the read had just
handed back was rejected and a shared workspace could never be configured. The
write now applies the predicate ``@require_tenant_admin`` applies: OWNER or ADMIN
on the workspace named, and nothing else.
"""

import asyncio
import inspect
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch

import api.apps  # noqa: F401 - registers the route modules under api.apps.restful_apis

ADMIN = "user-admin"
WORKSPACE = "tenant-workspace"
OTHER_WORKSPACE = "tenant-other"

USER_API = sys.modules["api.apps.restful_apis.user_api"]
# The route carries login_required and validate_request; this test drives the
# handler itself, with the request and the current user supplied directly.
SET_TENANT_MODELS = inspect.unwrap(USER_API.set_tenant_info)

BODY = {
    "tenant_id": WORKSPACE,
    "llm_id": "gpt-4@default@OpenAI",
    "embd_id": "",
    "asr_id": "",
    "img2txt_id": "",
}


def _request_json(body):
    async def _get_request_json():
        return dict(body)

    return _get_request_json


def _call(body, *, administers, written):
    """Drive the handler and return (response body, predicate mock)."""
    with (
        patch.object(USER_API, "current_user", SimpleNamespace(id=ADMIN)),
        patch.object(USER_API, "request", SimpleNamespace(path="/api/v1/users/me/models")),
        patch.object(USER_API, "get_request_json", _request_json(body)),
        patch.object(USER_API, "ensure_tenant_model_ids_for_params", lambda _tenant_id, params: params),
        patch.object(USER_API.TenantService, "update_by_id", lambda tenant_id, fields: written.append((tenant_id, fields))),
        patch.object(USER_API.UserTenantService, "can_manage_tenant", return_value=administers) as can_manage,
    ):
        return asyncio.run(SET_TENANT_MODELS()), can_manage


def test_an_administrator_writes_the_workspace_it_echoes_back():
    written = []

    response, can_manage = _call(BODY, administers=True, written=written)

    assert response["code"] == 0
    assert written == [(WORKSPACE, {k: v for k, v in BODY.items() if k != "tenant_id"})]
    can_manage.assert_called_once_with(ADMIN, WORKSPACE)


def test_a_workspace_the_caller_does_not_administer_is_refused():
    written = []

    response, can_manage = _call({**BODY, "tenant_id": OTHER_WORKSPACE}, administers=False, written=written)

    # A permission denial, reported as the code the frontend handles: 108.
    assert response["code"] == 108
    can_manage.assert_called_once_with(ADMIN, OTHER_WORKSPACE)
    assert written == [], "a workspace the caller cannot manage must not be written"


def test_the_json_contract_of_the_response_is_unchanged():
    written = []

    response, _can_manage = _call(BODY, administers=True, written=written)

    # The handler's own response is serializable as before ('data': True).
    assert json.loads(json.dumps(response))["data"] is True
