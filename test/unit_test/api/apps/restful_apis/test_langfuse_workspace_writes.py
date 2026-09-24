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
"""The Langfuse handlers store the keys under the workspace the guard admitted.

``@require_tenant_admin`` checks ``UserTenantService.can_manage_tenant`` against
``TenantService.resolve_active_tenant_id(user.id, requested_tenant_id())`` -- the
workspace named by ``X-Tenant-Id``. The handlers used ``current_user.id``
instead, so an admin of workspace X filed X's keys under its own id, where
``LLMBundle`` -- which resolves the workspace being used -- never looked.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ADMIN = "user-admin"
MEMBER = "user-member"
WORKSPACE = "tenant-workspace"
OTHER_WORKSPACE = "tenant-other"


class _DummyManager:
    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


class _FakeLangfuse:
    def __init__(self, **_kwargs):
        self.api = SimpleNamespace(
            projects=SimpleNamespace(get=lambda: SimpleNamespace(dict=lambda: {"data": [{"id": "project-id", "name": "project-name"}]})),
            core=SimpleNamespace(api_error=SimpleNamespace(ApiError=RuntimeError)),
        )

    def auth_check(self):
        return True


def _bare_identity(func):
    """A stand-in for a decorator used bare, as ``@login_required`` is."""
    return func


def _decorator_factory(*_args, **_kwargs):
    """A stand-in for a decorator used with arguments, as ``@validate_request(...)`` is."""
    return _bare_identity


def _stub(monkeypatch, name, **attrs):
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, name, mod)
    if "." in name:
        parent_name, _, child_name = name.rpartition(".")
        parent_mod = sys.modules.get(parent_name)
        if parent_mod is not None:
            monkeypatch.setattr(parent_mod, child_name, mod, raising=False)
    return mod


def _load_module(monkeypatch, *, memberships, user=ADMIN):
    """Load langfuse_api with recording Langfuse and TenantService stubs."""
    recorded = SimpleNamespace(
        resolve_calls=[],
        lookups=[],
        saves=[],
        updates=[],
        deletes=[],
    )
    header = SimpleNamespace(value=None)

    def _resolve_active_tenant_id(tenant_id, requested_tenant_id=None):
        recorded.resolve_calls.append((tenant_id, requested_tenant_id))
        if requested_tenant_id and requested_tenant_id in memberships.get(tenant_id, ()):
            return requested_tenant_id
        return tenant_id

    class _RecordingTenantLangfuse:
        @staticmethod
        def filter_by_tenant(tenant_id):
            recorded.lookups.append(tenant_id)
            return None

        @staticmethod
        def filter_by_tenant_with_info(tenant_id):
            recorded.lookups.append(tenant_id)
            return {"tenant_id": tenant_id, "host": "http://host", "secret_key": "sec", "public_key": "pub"}

        @staticmethod
        def save(**kwargs):
            recorded.saves.append(kwargs)

        @staticmethod
        def update_by_tenant(tenant_id, langfuse_keys):
            recorded.updates.append((tenant_id, langfuse_keys))

        @staticmethod
        def delete_model(_entry):
            recorded.deletes.append(True)

    stub_apps = _stub(
        monkeypatch,
        "api.apps",
        current_user=SimpleNamespace(id=user),
        login_required=_bare_identity,
        require_tenant_admin=_bare_identity,
    )
    _stub(monkeypatch, "langfuse", Langfuse=_FakeLangfuse)
    _stub(monkeypatch, "api.db.db_models", DB=SimpleNamespace(atomic=_nullcontext))
    _stub(monkeypatch, "api.db.services.langfuse_service", TenantLangfuseService=_RecordingTenantLangfuse)
    _stub(
        monkeypatch,
        "api.db.services.user_service",
        TenantService=SimpleNamespace(resolve_active_tenant_id=_resolve_active_tenant_id),
    )
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        get_error_data_result=lambda message="", **_k: {"code": 102, "message": message},
        get_json_result=lambda data=None, message="success", **_k: {"code": 0, "message": message, "data": data},
        get_request_json=_payload,
        requested_tenant_id=lambda: header.value,
        server_error_response=lambda error: {"code": 100, "message": str(error)},
        validate_request=_decorator_factory,
    )

    module_path = Path(__file__).resolve().parents[5] / "api" / "apps" / "restful_apis" / "langfuse_api.py"
    spec = importlib.util.spec_from_file_location("test_langfuse_workspace_writes_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    module.manager = _DummyManager()
    monkeypatch.setitem(sys.modules, "test_langfuse_workspace_writes_mod", module)
    spec.loader.exec_module(module)
    module.current_user = stub_apps.current_user
    return module, recorded, header


class _nullcontext:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


async def _payload():
    return {"secret_key": "sec", "public_key": "pub", "host": "http://host"}


def test_the_keys_are_stored_under_the_workspace_the_header_names(monkeypatch):
    module, recorded, header = _load_module(monkeypatch, memberships={ADMIN: [WORKSPACE]})
    header.value = WORKSPACE

    result = asyncio.run(module.set_api_key())

    assert result["code"] == 0
    assert recorded.saves[0]["tenant_id"] == WORKSPACE
    assert recorded.lookups == [WORKSPACE]
    assert (ADMIN, WORKSPACE) in recorded.resolve_calls, "the header must reach the resolver"


def test_an_existing_entry_is_updated_in_the_workspace_the_header_names(monkeypatch):
    module, recorded, header = _load_module(monkeypatch, memberships={ADMIN: [WORKSPACE]})
    header.value = WORKSPACE
    # An entry already exists for the administered workspace.
    module.TenantLangfuseService.filter_by_tenant = staticmethod(lambda tenant_id: recorded.lookups.append(tenant_id) or {"id": "existing"})

    result = asyncio.run(module.set_api_key())

    assert result["code"] == 0
    assert recorded.updates[0][0] == WORKSPACE
    assert recorded.saves == []


def test_the_read_and_the_delete_look_up_the_same_workspace_as_the_write(monkeypatch):
    module, recorded, header = _load_module(monkeypatch, memberships={ADMIN: [WORKSPACE]})
    header.value = WORKSPACE
    # An entry exists for the administered workspace, so the delete has one to remove.
    module.TenantLangfuseService.filter_by_tenant = staticmethod(lambda tenant_id: recorded.lookups.append(tenant_id) or {"id": "entry"})

    fetched = module.get_api_key()
    assert fetched["code"] == 0
    assert recorded.lookups == [WORKSPACE]

    deleted = module.delete_api_key()
    assert deleted["code"] == 0
    assert recorded.lookups == [WORKSPACE, WORKSPACE]
    assert recorded.deletes == [True]


def test_without_a_header_the_resolved_workspace_is_used(monkeypatch):
    module, recorded, header = _load_module(monkeypatch, memberships={ADMIN: [WORKSPACE]})

    result = asyncio.run(module.set_api_key())

    assert result["code"] == 0
    assert recorded.saves[0]["tenant_id"] == ADMIN
    assert (ADMIN, None) in recorded.resolve_calls


def test_a_header_the_caller_is_not_a_member_of_does_not_select_the_workspace(monkeypatch):
    module, recorded, header = _load_module(monkeypatch, memberships={MEMBER: [OTHER_WORKSPACE]}, user=MEMBER)
    header.value = WORKSPACE

    result = asyncio.run(module.set_api_key())

    assert result["code"] == 0
    assert recorded.saves[0]["tenant_id"] == MEMBER
