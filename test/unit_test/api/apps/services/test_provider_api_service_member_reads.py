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
"""A member reads the model configuration of the tenant it joined.

The mutating provider routes are admin-only on the caller's own tenant, so a
member who owns no tenant has nothing of its own to read either. These tests pin
the read side of that pairing: the provider-configuration readers resolve the
tenant through ``TenantService.resolve_active_tenant_id`` instead of using the
caller's id directly, which is what lets a member see the shared configuration
read-only.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

PROVIDER = "OpenAI"
MEMBER = "user-member"
SHARED_TENANT = "tenant-shared"


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


def _load_service(monkeypatch, *, resolution, instances):
    """Load provider_api_service with a recording TenantService.

    ``resolution`` maps a caller id to the tenant its model configuration is
    read from; ``instances`` is what the shared provider holds.
    """
    recorded = SimpleNamespace(
        resolve_calls=[],
        provider_lookups=[],
        instance_lookups=[],
    )

    def _resolve_active_tenant_id(tenant_id):
        recorded.resolve_calls.append(tenant_id)
        return resolution.get(tenant_id, tenant_id)

    _stub(monkeypatch, "common.settings", FACTORY_LLM_INFOS=[{"name": PROVIDER, "llm": [], "url": ""}])
    _stub(monkeypatch, "api.db.db_models", DB=SimpleNamespace())
    _stub(
        monkeypatch,
        "api.db.services.user_service",
        TenantService=SimpleNamespace(resolve_active_tenant_id=_resolve_active_tenant_id),
    )
    _stub(
        monkeypatch,
        "api.db.joint_services.tenant_model_service",
        resolve_model_config=lambda *_a, **_k: {},
        delete_models_by_instance_ids=lambda *_a, **_k: None,
        delete_instances_by_provider_ids=lambda *_a, **_k: None,
    )

    def _provider_by_id(tenant_id, provider_id):
        recorded.provider_lookups.append((tenant_id, provider_id))
        return None

    def _provider_by_name(tenant_id, provider_name):
        recorded.provider_lookups.append((tenant_id, provider_name))
        if tenant_id != SHARED_TENANT or provider_name != PROVIDER:
            return None
        return SimpleNamespace(id="provider-shared", provider_name=provider_name, tenant_id=tenant_id)

    def _instances_by_provider_id(provider_id):
        recorded.instance_lookups.append(provider_id)
        return list(instances) if provider_id == "provider-shared" else []

    _stub(
        monkeypatch,
        "api.db.services.tenant_model_provider_service",
        TenantModelProviderService=SimpleNamespace(
            get_by_tenant_id_and_provider_id=_provider_by_id,
            get_by_tenant_id_and_provider_name=_provider_by_name,
            get_by_id=lambda _id: (False, None),
        ),
    )
    _stub(
        monkeypatch,
        "api.db.services.tenant_model_instance_service",
        TenantModelInstanceService=SimpleNamespace(
            get_all_by_provider_id=_instances_by_provider_id,
            get_by_id=lambda instance_id: (True, next((i for i in instances if i.id == instance_id), None)),
            get_by_provider_id_and_instance_name=lambda provider_id, instance_name: next(
                (i for i in instances if i.provider_id == provider_id and i.instance_name == instance_name),
                None,
            ),
        ),
    )
    _stub(monkeypatch, "api.db.services.tenant_model_service", TenantModelService=SimpleNamespace())
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
    spec = importlib.util.spec_from_file_location("test_provider_api_service_member_reads_mod", module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "test_provider_api_service_member_reads_mod", module)
    spec.loader.exec_module(module)
    return module, recorded


def _shared_instance():
    return SimpleNamespace(
        id="instance-shared",
        instance_name="shared-primary",
        provider_id="provider-shared",
        api_key="sk-shared-tenant-key",
        status="active",
        create_time=1,
        extra="{}",
    )


def test_a_member_lists_the_instances_of_the_tenant_it_joined(monkeypatch):
    module, recorded = _load_service(
        monkeypatch,
        resolution={MEMBER: SHARED_TENANT},
        instances=[_shared_instance()],
    )

    success, instances = module.list_provider_instances(MEMBER, PROVIDER)

    assert success is True
    assert [i["instance_name"] for i in instances] == ["shared-primary"]
    assert recorded.resolve_calls == [MEMBER], "the raw caller id must be resolved, not assumed to be a tenant"
    assert (SHARED_TENANT, PROVIDER) in recorded.provider_lookups


def test_a_member_reads_the_shared_instance_details(monkeypatch):
    module, recorded = _load_service(
        monkeypatch,
        resolution={MEMBER: SHARED_TENANT},
        instances=[_shared_instance()],
    )

    success, detail = module.show_provider_instance(MEMBER, PROVIDER, "shared-primary")

    assert success is True
    assert detail["instance_name"] == "shared-primary"
    # The credential is masked on the way out even when it belongs to the shared
    # tenant, so a member can see that a key exists without reading it.
    assert detail["api_key"] == module.mask_secret("sk-shared-tenant-key")
    assert "sk-shared-tenant-key" not in detail["api_key"]
    assert (SHARED_TENANT, PROVIDER) in recorded.provider_lookups


def test_a_provider_the_shared_tenant_does_not_have_is_still_missing(monkeypatch):
    # Resolution must not turn into "search every tenant": an unconfigured
    # provider stays a not-found, exactly as it does for an owner.
    module, _recorded = _load_service(
        monkeypatch,
        resolution={MEMBER: SHARED_TENANT},
        instances=[],
    )

    success, message = module.list_provider_instances(MEMBER, "SomeOtherProvider")

    assert success is False
    assert "No provider found" in message
