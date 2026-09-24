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
"""An admin working in a shared workspace saves its default models into it.

``GET /models/default`` resolved the workspace while ``PATCH /models/default``
wrote the caller's own tenant: an admin of workspace X saved X's default into
its own tenant row, and the UI showed the old value again after a reload.

These tests pin the write side: the default-model write resolves the workspace
exactly as the listings do, a model belonging to another workspace is refused as
a permission denial, and the listing and the write land on the same workspace.
"""

import importlib.util
import sys
from enum import IntEnum
from pathlib import Path
from types import ModuleType, SimpleNamespace

ADMIN = "user-admin"
MEMBER = "user-member"
WORKSPACE = "tenant-workspace"
OTHER_WORKSPACE = "tenant-other"
PROVIDER = "OpenAI"


class _StubActiveStatus(IntEnum):
    ACTIVE = 1
    INACTIVE = 0


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


def _load_module(monkeypatch, *, memberships, provider_tenant_id, model_id="model-ws"):
    """Load models_api_service with recording stubs.

    ``provider_tenant_id`` is the workspace the model's provider row belongs to,
    which is what the write compares the resolved workspace against.
    """
    recorded = SimpleNamespace(
        resolve_calls=[],
        tenant_reads=[],
        tenant_writes=[],
        model_reads=[],
    )
    # The value the client sends as X-Tenant-Id; a test flips it mid-run.
    header = SimpleNamespace(value=None)

    tenant = SimpleNamespace(id=WORKSPACE, name=WORKSPACE)
    provider = SimpleNamespace(id="provider-ws", provider_name=PROVIDER, tenant_id=provider_tenant_id)
    instance = SimpleNamespace(id="instance-default", provider_id=provider.id, instance_name="default")
    model = SimpleNamespace(
        id=model_id,
        provider_id=provider.id,
        instance_id=instance.id,
        model_name="gpt-4",
        model_type=_StubActiveStatus.ACTIVE.value,
        status=_StubActiveStatus.ACTIVE.value,
    )

    def _resolve_active_tenant_id(tenant_id, requested_tenant_id=None):
        recorded.resolve_calls.append((tenant_id, requested_tenant_id))
        if requested_tenant_id and requested_tenant_id in memberships.get(tenant_id, ()):
            return requested_tenant_id
        return tenant_id

    def _get_tenant(tenant_id):
        recorded.tenant_reads.append(tenant_id)
        return True, tenant

    def _update_tenant(tenant_id, fields):
        recorded.tenant_writes.append((tenant_id, fields))
        return True

    _stub(
        monkeypatch,
        "api.db.services.user_service",
        TenantService=SimpleNamespace(
            get_by_id=_get_tenant,
            update_by_id=_update_tenant,
            resolve_active_tenant_id=_resolve_active_tenant_id,
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_provider_service",
        TenantModelProviderService=SimpleNamespace(
            get_by_id=lambda provider_id: (provider_id == provider.id, provider if provider_id == provider.id else None),
            get_by_tenant_id_and_provider_name=lambda tenant_id, provider_name: provider if tenant_id == provider.tenant_id and provider_name == PROVIDER else None,
            get_by_tenant_id=lambda tenant_id: [provider] if tenant_id == provider.tenant_id else [],
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_instance_service",
        TenantModelInstanceService=SimpleNamespace(
            get_by_id=lambda instance_id: (instance_id == instance.id, instance if instance_id == instance.id else None),
            get_by_provider_ids=lambda provider_ids: [instance] if provider.id in provider_ids else [],
            get_by_provider_id_and_instance_name=lambda provider_id, instance_name: instance if (provider_id == instance.provider_id and instance_name == instance.instance_name) else None,
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_service",
        TenantModelService=SimpleNamespace(
            get_by_id=lambda requested_id: (requested_id == model.id, model if requested_id == model.id else None),
            get_models_by_provider_ids_and_instance_ids=lambda *_a, **_k: [],
            get_by_provider_id_and_instance_id_and_model_name=lambda *_a, **_k: SimpleNamespace(status=_StubActiveStatus.ACTIVE.value, model_type=model.model_type),
        ),
    )
    # joint_services.tenant_model_service is imported at module load for the
    # ensure_* helpers and for the model-id resolution.
    _stub(
        monkeypatch,
        "api.db.joint_services.tenant_model_service",
        ensure_mineru_from_env=lambda *_a, **_k: None,
        ensure_paddleocr_from_env=lambda *_a, **_k: None,
        ensure_opendataloader_from_env=lambda *_a, **_k: None,
        resolve_model_id=lambda *_a, **_k: None,
        ensure_tenant_model_ids_for_params=lambda _tenant_id, params: params,
    )
    _stub(monkeypatch, "api.db.joint_services", tenant_model_service=sys.modules["api.db.joint_services.tenant_model_service"])
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        requested_tenant_id=lambda: header.value,
        PermissionDeniedMessage=type("PermissionDeniedMessage", (str,), {"code": 108}),
    )
    _stub(monkeypatch, "api.utils.model_utils", get_model_type_human=lambda *_a, **_k: ["chat"], calculate_model_type=lambda *_a, **_k: 0)
    _stub(
        monkeypatch,
        "common.constants",
        ActiveStatusEnum=_StubActiveStatus.ACTIVE,
        LLMType=SimpleNamespace(EMBEDDING=SimpleNamespace(value="embedding"), CHAT="chat"),
    )
    _stub(monkeypatch, "common.settings", FACTORY_LLM_INFOS=[{"name": PROVIDER, "llm": [{"llm_name": "gpt-4", "model_type": "chat"}]}])

    module_path = Path(__file__).resolve().parents[5] / "api" / "apps" / "services" / "models_api_service.py"
    spec = importlib.util.spec_from_file_location("test_models_api_service_workspace_writes_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "test_models_api_service_workspace_writes_mod", module)
    spec.loader.exec_module(module)
    return module, recorded, header


def test_the_default_model_is_written_into_the_workspace_the_header_names(monkeypatch):
    module, recorded, header = _load_module(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        provider_tenant_id=WORKSPACE,
    )
    header.value = WORKSPACE

    success, message = module.set_tenant_default_models(ADMIN, "", "", "", "chat", "model-ws")

    assert success is True, message
    assert recorded.tenant_writes == [(WORKSPACE, {"llm_id": "gpt-4@default@OpenAI", "tenant_llm_id": "model-ws"})]
    assert (ADMIN, WORKSPACE) in recorded.resolve_calls, "the header must reach the resolver"


def test_the_listing_and_the_write_resolve_the_same_workspace(monkeypatch):
    """Read and write agree on the workspace, which is what made the UI lie."""
    module, recorded, header = _load_module(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        provider_tenant_id=WORKSPACE,
    )
    header.value = WORKSPACE

    listed, payload = module.list_tenant_default_models(ADMIN)
    assert listed is True
    assert payload == {"models": []}
    assert recorded.tenant_reads == [WORKSPACE]

    success, _message = module.set_tenant_default_models(ADMIN, "", "", "", "chat")

    assert success is True
    assert recorded.tenant_writes[0][0] == WORKSPACE, "the write must land where the read looked"


def test_a_model_of_another_workspace_is_refused_as_a_permission_denial(monkeypatch):
    module, recorded, header = _load_module(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        provider_tenant_id=OTHER_WORKSPACE,
    )
    header.value = WORKSPACE

    success, message = module.set_tenant_default_models(ADMIN, "", "", "", "chat", "model-ws")

    assert success is False
    # The denial carries code 108 rather than the data-error code a plain string
    # would be reported as.
    assert getattr(message, "code", None) == 108, message
    assert recorded.tenant_writes == []


def test_the_header_cannot_name_a_workspace_the_caller_is_not_a_member_of(monkeypatch):
    module, recorded, header = _load_module(
        monkeypatch,
        memberships={},
        provider_tenant_id=MEMBER,
    )
    header.value = WORKSPACE

    success, _message = module.set_tenant_default_models(MEMBER, "", "", "", "chat")

    assert success is True
    assert recorded.tenant_writes[0][0] == MEMBER, "a header the resolver refused must not select the workspace"
