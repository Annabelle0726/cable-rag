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
"""An admin working in a shared workspace writes its provider configuration there.

The mutating provider functions used to take the id ``add_tenant_id_to_kwargs``
injects -- the caller's USER id, which is a workspace of its own only for the
tenant it created. An admin working in workspace X therefore listed X's
providers through the resolved read path and then had its save land in its own
tenant, which the UI reported as ``Provider '<x>' does not exist``.

These tests pin the write side: every lookup and every insert resolves the
workspace the same way the reads do, the ``X-Tenant-Id`` header decides it when
the caller is a member of the workspace it names, and a header naming a
workspace the caller holds no membership on is ignored rather than trusted.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

ADMIN = "user-admin"
MEMBER = "user-member"
WORKSPACE = "tenant-workspace"
OTHER_WORKSPACE = "tenant-other"
PROVIDER = "OpenAI"


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


def _provider(tenant_id):
    return SimpleNamespace(id=f"provider-{tenant_id}", provider_name=PROVIDER, tenant_id=tenant_id)


def _instance():
    return SimpleNamespace(
        id="instance-default",
        instance_name="default",
        provider_id=f"provider-{WORKSPACE}",
        api_key="sk-workspace-key",
        status="active",
        create_time=1,
        extra="{}",
    )


def _load_service(monkeypatch, *, memberships, providers, instances=None):
    """Load provider_api_service with a recording provider service.

    ``memberships`` maps a user id to the workspaces it belongs to, standing in
    for ``UserTenantService.get_role`` inside the real resolver; ``providers``
    maps a workspace id to the provider row it has configured.
    """
    recorded = SimpleNamespace(
        resolve_calls=[],
        provider_lookups=[],
        inserts=[],
        deletes=[],
        model_inserts=[],
    )
    # The value the client sends as X-Tenant-Id; a test flips it mid-run.
    header = SimpleNamespace(value=None)

    def _resolve_active_tenant_id(tenant_id, requested_tenant_id=None):
        recorded.resolve_calls.append((tenant_id, requested_tenant_id))
        if requested_tenant_id and requested_tenant_id in memberships.get(tenant_id, ()):
            return requested_tenant_id
        return tenant_id

    def _provider_by_id(tenant_id, provider_id):
        recorded.provider_lookups.append((tenant_id, provider_id))
        return None

    def _provider_by_name(tenant_id, provider_name):
        recorded.provider_lookups.append((tenant_id, provider_name))
        provider = providers.get(tenant_id)
        return provider if provider and provider.provider_name == provider_name else None

    def _insert(**kwargs):
        recorded.inserts.append(kwargs)

    def _delete_by_tenant_and_name(tenant_id, provider_name):
        recorded.deletes.append((tenant_id, provider_name))

    def _model_insert(**kwargs):
        recorded.model_inserts.append(kwargs)

    _stub(monkeypatch, "common.settings", FACTORY_LLM_INFOS=[{"name": PROVIDER, "llm": [{"llm_name": "gpt-4", "model_type": "chat", "max_tokens": 8192}], "url": ""}])
    _stub(monkeypatch, "api.db.db_models", DB=SimpleNamespace())
    _stub(
        monkeypatch,
        "api.db.services.user_service",
        TenantService=SimpleNamespace(resolve_active_tenant_id=_resolve_active_tenant_id),
    )
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        requested_tenant_id=lambda: header.value,
    )
    _stub(
        monkeypatch,
        "api.db.joint_services.tenant_model_service",
        resolve_model_config=lambda *_a, **_k: {},
        delete_models_by_instance_ids=lambda *_a, **_k: None,
        delete_instances_by_provider_ids=lambda *_a, **_k: None,
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_provider_service",
        TenantModelProviderService=SimpleNamespace(
            get_by_tenant_id_and_provider_id=_provider_by_id,
            get_by_tenant_id_and_provider_name=_provider_by_name,
            get_by_id=lambda _id: (False, None),
            list_provider_names_by_tenant_id=lambda tenant_id: [PROVIDER] if tenant_id in providers else [],
            insert=_insert,
            delete_by_tenant_id_and_provider_name=_delete_by_tenant_and_name,
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_instance_service",
        TenantModelInstanceService=SimpleNamespace(
            get_all_by_provider_id=lambda provider_id: [i for i in (instances or []) if i.provider_id == provider_id],
            get_by_id=lambda instance_id: (True, next((i for i in (instances or []) if i.id == instance_id), None)),
            get_by_provider_id_and_instance_name=lambda provider_id, instance_name: next(
                (i for i in (instances or []) if i.provider_id == provider_id and i.instance_name == instance_name),
                None,
            ),
            create_instance=lambda **_kwargs: None,
            delete_by_ids=lambda *_a, **_k: None,
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_service",
        TenantModelService=SimpleNamespace(
            insert=_model_insert,
            get_by_provider_id_and_instance_id_and_model_name=lambda *_a, **_k: None,
            get_models_by_instance_id=lambda *_a, **_k: [],
        ),
    )
    _stub(monkeypatch, "api.utils.model_utils", get_model_type_human=lambda *_a, **_k: "", calculate_model_type=lambda *_a, **_k: 0)
    _stub(
        monkeypatch,
        "rag.llm",
        ChatModel={},
        CvModel={},
        EmbeddingModel={},
        ModelMeta={},
        OcrModel={},
        RerankModel={},
        Seq2txtModel={},
        TTSModel={},
    )

    repo_root = Path(__file__).resolve().parents[5]
    module_path = repo_root / "api" / "apps" / "services" / "provider_api_service.py"
    spec = importlib.util.spec_from_file_location("test_provider_api_service_workspace_writes_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "test_provider_api_service_workspace_writes_mod", module)
    spec.loader.exec_module(module)
    return module, recorded, header


def test_adding_a_provider_writes_into_the_workspace_the_header_names(monkeypatch):
    module, recorded, header = _load_service(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        providers={},
    )
    header.value = WORKSPACE

    success, message = module.add_provider(ADMIN, PROVIDER)

    assert success is True, message
    # The row is written for the administered workspace, not for the caller.
    assert recorded.inserts == [{"tenant_id": WORKSPACE, "provider_name": PROVIDER}]
    assert (ADMIN, WORKSPACE) in recorded.resolve_calls, "the header must reach the resolver"


def test_the_listing_and_the_write_resolve_the_same_workspace(monkeypatch):
    """Read and write agree: the provider X lists is the provider X deletes."""
    module, recorded, header = _load_service(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        providers={WORKSPACE: _provider(WORKSPACE)},
    )
    header.value = WORKSPACE

    listed, instances = module.list_provider_instances(ADMIN, PROVIDER)
    assert listed is True
    assert instances == []
    assert (WORKSPACE, PROVIDER) in recorded.provider_lookups

    deleted, _message = module.delete_provider(ADMIN, PROVIDER)

    assert deleted is True
    assert recorded.deletes == [(WORKSPACE, PROVIDER)]
    assert recorded.provider_lookups[-1] == (WORKSPACE, PROVIDER), "the write must resolve what the read resolved"


def test_a_provider_of_the_callers_own_workspace_is_not_used_for_the_administered_one(monkeypatch):
    """Resolution must not fall back to the caller's own tenant on a miss."""
    module, recorded, header = _load_service(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        providers={ADMIN: _provider(ADMIN)},
    )
    header.value = WORKSPACE

    deleted, message = module.delete_provider(ADMIN, PROVIDER)

    assert deleted is False
    assert "not found" in message
    assert recorded.deletes == []


def test_the_header_cannot_name_a_workspace_the_caller_is_not_a_member_of(monkeypatch):
    module, recorded, header = _load_service(
        monkeypatch,
        memberships={MEMBER: [OTHER_WORKSPACE]},
        providers={},
    )
    header.value = WORKSPACE

    success, _message = module.add_provider(MEMBER, PROVIDER)

    assert success is True
    # The resolver refused the header, so the write lands in the workspace the
    # caller does hold.
    assert recorded.inserts == [{"tenant_id": MEMBER, "provider_name": PROVIDER}]


def test_adding_a_model_writes_through_the_workspace_the_header_names(monkeypatch):
    module, recorded, header = _load_service(
        monkeypatch,
        memberships={ADMIN: [WORKSPACE]},
        providers={WORKSPACE: _provider(WORKSPACE)},
        instances=[_instance()],
    )
    header.value = WORKSPACE

    success, message = module.add_model_to_instance(ADMIN, PROVIDER, "default", model_name="gpt-4", model_type="chat")

    assert success is True, message
    assert (WORKSPACE, PROVIDER) in recorded.provider_lookups
    assert recorded.model_inserts, "the model must be created under the workspace's provider"
    assert recorded.model_inserts[0]["provider_id"] == f"provider-{WORKSPACE}"
