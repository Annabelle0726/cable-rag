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
"""The P3-03 write gate: who may change a dataset, and what a denial looks like.

Two things are covered here. First the gate itself, against real rows on
in-memory SQLite: the creator and the workspace's managers may write, and a
member holding only read access -- including one granted `custom` retrieval --
may not. Second, a structural guard that the write endpoints actually call that
gate, so the enforcement cannot be dropped silently from a route later on.
"""

import ast
from contextlib import contextmanager
from pathlib import Path

import pytest
from peewee import SqliteDatabase

from api.db import TenantPermission
from api.db.db_models import Document, Knowledgebase, KnowledgebaseAuthorization, UserTenant
from api.db.services import knowledgebase_service as kb_service
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService
from api.utils.api_utils import get_error_permission_result
from common.constants import RetCode

pytestmark = pytest.mark.p1

REPO_ROOT = Path(__file__).resolve().parents[5]
T1 = "tenant-1"
T2 = "tenant-2"
DEPT_A = "dept-a"

OWNER = "user-owner"
ADMIN = "user-admin"
MEMBER = "user-member"
OUTSIDER = "user-outsider"

KB_TEAM = "kb-team"
KB_PRIVATE = "kb-private"
KB_CUSTOM = "kb-custom"
DOC_TEAM = "doc-team"
DOC_CUSTOM = "doc-custom"

MODELS = [Knowledgebase, Document, UserTenant, KnowledgebaseAuthorization]


def _kb(kb_id, permission, *, tenant_id=T1, created_by=OWNER):
    return {
        "id": kb_id,
        "tenant_id": tenant_id,
        "name": kb_id,
        "embd_id": "",
        "permission": permission,
        "created_by": created_by,
        "parser_id": "naive",
        "parser_config": {},
        "status": "1",
    }


def _doc(doc_id, kb_id):
    return {
        "id": doc_id,
        "kb_id": kb_id,
        "parser_id": "naive",
        "parser_config": {},
        "type": "pdf",
        "suffix": "pdf",
        "created_by": OWNER,
        "name": doc_id,
        "status": "1",
    }


def _membership(user_id, tenant_id, *, role="normal", department_id=None):
    return {
        "id": f"ut-{user_id}-{tenant_id}",
        "user_id": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "invited_by": OWNER,
        "department_id": department_id,
        "status": "1",
    }


def _grant(kb_id, subject_type, subject_id):
    return {"id": f"ka-{kb_id}-{subject_id}", "kb_id": kb_id, "subject_type": subject_type, "subject_id": subject_id, "create_time": 1, "update_time": 1}


def _seed():
    for row in (
        _kb(KB_TEAM, TenantPermission.TEAM.value),
        _kb(KB_PRIVATE, TenantPermission.ME.value),
        _kb(KB_CUSTOM, TenantPermission.CUSTOM.value),
    ):
        Knowledgebase.insert(row).execute()
    for row in (_doc(DOC_TEAM, KB_TEAM), _doc(DOC_CUSTOM, KB_CUSTOM)):
        Document.insert(row).execute()
    for row in (
        _membership(OWNER, T1, role="owner"),
        _membership(ADMIN, T1, role="admin"),
        _membership(MEMBER, T1, department_id=DEPT_A),
        _membership(OUTSIDER, T2),
    ):
        UserTenant.insert(row).execute()
    KnowledgebaseAuthorization.insert(_grant(KB_CUSTOM, "department", DEPT_A)).execute()


@contextmanager
def _bound(monkeypatch, active_tenant_id=T1):
    """Bind the models to a private in-memory database for the duration.

    `bind_ctx` binds the models to the database it is called on, so it has to be
    called on the SQLite handle; the assertion pins that down. The workspace the
    caller is operating in is pinned too, since the manager branch asks for the
    dataset's own workspace as the active one.
    """
    monkeypatch.setattr(TenantService, "resolve_active_tenant_id", classmethod(lambda cls, user_id, requested_tenant_id=None: active_tenant_id))
    sqlite = SqliteDatabase(":memory:")
    with sqlite.bind_ctx(MODELS):
        assert Knowledgebase._meta.database is sqlite
        sqlite.create_tables(MODELS)
        _seed()
        yield


@pytest.fixture
def db(monkeypatch):
    with _bound(monkeypatch):
        yield


# --------------------------------------------------------------------------- #
# who may write
# --------------------------------------------------------------------------- #


def test_the_creator_may_write_in_every_mode(db):
    for kb_id in (KB_TEAM, KB_PRIVATE, KB_CUSTOM):
        assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, kb_id, OWNER) is True


def test_a_workspace_manager_may_write_in_every_mode(db):
    for kb_id in (KB_TEAM, KB_PRIVATE, KB_CUSTOM):
        assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, kb_id, ADMIN) is True


def test_a_custom_authorized_reader_may_not_write(db):
    """The reason the two gates are separate: a reader is not an editor."""
    wrapped = KnowledgebaseService.writable.__func__.__wrapped__

    # The member reads KB_CUSTOM through their department grant...
    assert KnowledgebaseService.accessible.__func__.__wrapped__(KnowledgebaseService, KB_CUSTOM, MEMBER) is True
    # ...and still cannot change it.
    assert wrapped(KnowledgebaseService, KB_CUSTOM, MEMBER) is False


def test_a_team_member_may_not_write(db):
    wrapped = KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, MEMBER)
    assert KnowledgebaseService.accessible.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, MEMBER) is True
    assert wrapped is False


def test_an_outsider_may_not_write(db):
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, OUTSIDER) is False


def test_a_manager_of_another_workspace_may_not_write(monkeypatch, db):
    """Manager authority is scoped to the workspace that owns the dataset."""
    monkeypatch.setattr(TenantService, "resolve_active_tenant_id", classmethod(lambda cls, user_id, requested_tenant_id=None: T2))
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, ADMIN) is False


def test_the_x_tenant_id_header_names_the_workspace(monkeypatch, db):
    """An API/SDK caller reaches the workspace it names with `X-Tenant-Id`.

    The resolver only honours a workspace the caller holds a membership on, so
    honouring the header cannot widen access -- but ignoring it would refuse a
    manager working through the API rather than the UI.
    """
    memberships = {(ADMIN, T1), (ADMIN, T2)}

    def resolve(cls, user_id, requested_tenant_id=None):
        if requested_tenant_id and (user_id, requested_tenant_id) in memberships:
            return requested_tenant_id
        return T2  # the caller's own workspace

    monkeypatch.setattr(TenantService, "resolve_active_tenant_id", classmethod(resolve))
    monkeypatch.setattr(kb_service, "requested_tenant_id", lambda: None)
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, ADMIN) is False

    monkeypatch.setattr(kb_service, "requested_tenant_id", lambda: T1)
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, ADMIN) is True
    assert KnowledgebaseService.accessible.__func__.__wrapped__(KnowledgebaseService, KB_PRIVATE, ADMIN) is True

    # A header naming a workspace the caller has no membership on is ignored.
    monkeypatch.setattr(kb_service, "requested_tenant_id", lambda: "tenant-nowhere")
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, ADMIN) is False


def test_an_explicit_workspace_outranks_the_header(monkeypatch):
    monkeypatch.setattr(kb_service, "requested_tenant_id", lambda: T1)
    resolved = []
    monkeypatch.setattr(TenantService, "resolve_active_tenant_id", classmethod(lambda cls, user_id, requested_tenant_id=None: resolved.append(requested_tenant_id) or T2))

    assert kb_service._active_workspace(ADMIN, T2) == T2
    assert resolved == []


def test_the_header_reaches_the_resolver(monkeypatch):
    seen = {}
    monkeypatch.setattr(kb_service, "requested_tenant_id", lambda: T1)
    monkeypatch.setattr(
        TenantService,
        "resolve_active_tenant_id",
        classmethod(lambda cls, user_id, requested_tenant_id=None: seen.update(user_id=user_id, requested=requested_tenant_id) or T1),
    )

    assert kb_service._active_workspace(ADMIN) == T1
    assert seen == {"user_id": ADMIN, "requested": T1}


def test_an_invalid_dataset_is_never_writable(db):
    Knowledgebase.update(status="0").where(Knowledgebase.id == KB_TEAM).execute()
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, KB_TEAM, OWNER) is False
    assert KnowledgebaseService.writable.__func__.__wrapped__(KnowledgebaseService, "kb-missing", OWNER) is False


def test_a_document_inherits_its_datasets_write_rule(db):
    writable = DocumentService.writable.__func__.__wrapped__
    assert writable(DocumentService, DOC_TEAM, OWNER) is True
    assert writable(DocumentService, DOC_TEAM, ADMIN) is True
    assert writable(DocumentService, DOC_TEAM, MEMBER) is False
    assert writable(DocumentService, DOC_CUSTOM, MEMBER) is False
    assert writable(DocumentService, "doc-missing", OWNER) is False


def test_a_denial_carries_the_platform_permission_code():
    """HTTP 200 with code=108, the shape the frontend intercepts."""
    response = get_error_permission_result("You don't own the dataset kb-1.")
    payload = response.get_json() if hasattr(response, "get_json") else response
    assert payload["code"] == RetCode.PERMISSION_ERROR == 108
    assert payload["message"] == "You don't own the dataset kb-1."
    if hasattr(response, "status_code"):
        assert response.status_code == 200


# --------------------------------------------------------------------------- #
# the write endpoints call the gate
# --------------------------------------------------------------------------- #

#: Write handlers and the module that defines them. Each one must reach the
#: dataset write gate (directly, or through `DocumentService.writable`), so the
#: rule cannot be dropped from an endpoint without this test failing.
WRITE_HANDLERS = {
    "api/apps/restful_apis/chunk_api.py": ["parse", "stop_parsing", "delete_document_structure_graph", "add_chunk", "rm_chunk", "update_chunk", "switch_chunks"],
    "api/apps/restful_apis/document_api.py": ["upload_document", "metadata_batch_update", "delete_documents", "update_metadata", "update_metadata_config", "parse_documents", "stop_parse_documents"],
    "api/apps/restful_apis/dataset_api.py": [
        "delete",
        "update",
        "get_dataset_authorization",
        "update_dataset_authorization",
        "delete_tags",
        "rename_tag",
        "clear_wiki",
        "delete_dataset_structure",
        "delete_all_skills",
        "delete_skill_page",
        "delete_dataset_nav",
        "delete_dataset_nav_node",
        "generate_dataset_nav",
        "update_wiki_page",
        "run_index",
        "delete_index",
        "update_auto_metadata",
    ],
    "api/apps/restful_apis/file_commit_api.py": ["create_commit"],
}


def _calls_a_write_gate(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            text = ast.unparse(sub.func)
            if text.endswith(".writable"):
                return True
    return False


@pytest.mark.parametrize("relative_path,handlers", sorted(WRITE_HANDLERS.items()))
def test_every_write_handler_calls_the_write_gate(relative_path, handlers):
    tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    defined = {node.name: node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}

    missing = [name for name in handlers if name not in defined]
    assert not missing, f"{relative_path} no longer defines {missing}"

    ungated = [name for name in handlers if not _calls_a_write_gate(defined[name])]
    assert not ungated, f"{relative_path}: these write handlers no longer call the write gate: {ungated}"
