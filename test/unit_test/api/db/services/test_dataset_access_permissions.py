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
import sys
import types
import warnings
from types import SimpleNamespace

# xgboost imports pkg_resources and emits a deprecation warning that is promoted
# to error in our pytest configuration; ignore it for this unit test module.
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)


def _install_cv2_stub_if_unavailable():
    try:
        import cv2  # noqa: F401

        return
    except Exception:
        pass

    stub = types.ModuleType("cv2")

    stub.INTER_LINEAR = 1
    stub.INTER_CUBIC = 2
    stub.BORDER_CONSTANT = 0
    stub.BORDER_REPLICATE = 1
    stub.COLOR_BGR2RGB = 0
    stub.COLOR_BGR2GRAY = 1
    stub.COLOR_GRAY2BGR = 2
    stub.IMREAD_IGNORE_ORIENTATION = 128
    stub.IMREAD_COLOR = 1
    stub.RETR_LIST = 1
    stub.CHAIN_APPROX_SIMPLE = 2

    def _missing(*_args, **_kwargs):
        raise RuntimeError("cv2 runtime call is unavailable in this test environment")

    def _module_getattr(name):
        if name.isupper():
            return 0
        return _missing

    stub.__getattr__ = _module_getattr
    sys.modules["cv2"] = stub


_install_cv2_stub_if_unavailable()

from api.db import TenantPermission
from api.db.joint_services import kb_authorization_service as kbs
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService
from common.constants import StatusEnum


def _unwrapped_kb_accessible():
    return KnowledgebaseService.accessible.__func__.__wrapped__


def _unwrapped_doc_accessible():
    return DocumentService.accessible.__func__.__wrapped__


def _install_read_seams(monkeypatch, *, can_manage=False, member=False, department_id=None, granted=False, active_tenant_id="owner-1"):
    """Patch the seams `can_read_dataset` would otherwise query.

    `accessible` now delegates to the P3-03 predicate, so these tests replace the
    role, membership, placement and grant lookups rather than the old
    `get_joined_tenants_by_user_id` walk they used to stub.
    """
    monkeypatch.setattr(kbs, "_can_manage_tenant", lambda user_id, tenant_id: can_manage)
    monkeypatch.setattr(kbs, "_membership_role", lambda user_id, tenant_id: "normal" if member else None)
    monkeypatch.setattr(kbs, "_department_id_of", lambda user_id, tenant_id: department_id)
    monkeypatch.setattr(kbs, "_is_granted", lambda kb_id, user_id, dept_id: granted)
    monkeypatch.setattr(TenantService, "resolve_active_tenant_id", classmethod(lambda cls, user_id, requested_tenant_id=None: active_tenant_id))


def test_private_dataset_is_not_accessible_to_other_tenant_member(monkeypatch):
    kb = SimpleNamespace(
        id="kb-private",
        tenant_id="owner-1",
        created_by="owner-1",
        permission=TenantPermission.ME.value,
        status=StatusEnum.VALID.value,
    )

    monkeypatch.setattr(KnowledgebaseService, "get_by_id", classmethod(lambda cls, kb_id: (True, kb)))
    # The caller is a member of the owning workspace and still gets nothing: `me`
    # is the creator plus the workspace managers.
    _install_read_seams(monkeypatch, member=True)

    assert _unwrapped_kb_accessible()(KnowledgebaseService, "kb-private", "member-2") is False


def test_team_dataset_is_accessible_to_joined_tenant_member(monkeypatch):
    kb = SimpleNamespace(
        id="kb-team",
        tenant_id="owner-1",
        created_by="owner-1",
        permission=TenantPermission.TEAM.value,
        status=StatusEnum.VALID.value,
    )

    monkeypatch.setattr(KnowledgebaseService, "get_by_id", classmethod(lambda cls, kb_id: (True, kb)))
    _install_read_seams(monkeypatch, member=True)

    assert _unwrapped_kb_accessible()(KnowledgebaseService, "kb-team", "member-2") is True


def test_invalid_dataset_is_not_accessible(monkeypatch):
    kb = SimpleNamespace(
        id="kb-gone",
        tenant_id="owner-1",
        created_by="owner-1",
        permission=TenantPermission.TEAM.value,
        status="0",
    )

    monkeypatch.setattr(KnowledgebaseService, "get_by_id", classmethod(lambda cls, kb_id: (True, kb)))
    _install_read_seams(monkeypatch, member=True)

    assert _unwrapped_kb_accessible()(KnowledgebaseService, "kb-gone", "member-2") is False


def test_document_access_respects_dataset_permission(monkeypatch):
    doc = SimpleNamespace(id="doc-1", kb_id="kb-private")

    monkeypatch.setattr(DocumentService, "get_by_id", classmethod(lambda cls, doc_id: (True, doc)))
    monkeypatch.setattr(KnowledgebaseService, "accessible", classmethod(lambda cls, kb_id, user_id: False))

    assert _unwrapped_doc_accessible()(DocumentService, "doc-1", "member-2") is False
