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
"""The dataset authorization API: reading and replacing visibility and subjects.

Real rows on in-memory SQLite, with the write gate stubbed: the gate's own
behaviour is covered by `test_dataset_write_authorization.py`, so what is under
test here is the API's contract -- which mode and subjects come back, that the
subject set is replaced rather than appended, that a non-custom mode clears it,
and that a subject set cannot reach outside the workspace that owns the dataset.
"""

import asyncio
from contextlib import contextmanager

import pytest
from peewee import SqliteDatabase

from api.apps.services import dataset_api_service
from api.db import TenantPermission
from api.db.db_models import Department, Knowledgebase, KnowledgebaseAuthorization, UserTenant
from api.db.services.knowledgebase_service import KnowledgebaseService

pytestmark = pytest.mark.p1

TENANT = "tenant-1"
OTHER_TENANT = "tenant-2"
DEPT_A = "dept-a"
DEPT_B = "dept-b"
DEPT_OTHER_WORKSPACE = "dept-other"

MEMBER = "user-member"
OTHER_MEMBER = "user-other-member"
INVITEE = "user-invitee"
OUTSIDER = "user-outsider"
ADMIN = "user-admin"
KB_ID = "kb-1"

MODELS = [Knowledgebase, KnowledgebaseAuthorization, UserTenant, Department]


def _kb(permission=TenantPermission.ME.value):
    return {
        "id": KB_ID,
        "tenant_id": TENANT,
        "name": "dataset",
        "embd_id": "",
        "permission": permission,
        "created_by": ADMIN,
        "parser_id": "naive",
        "parser_config": {},
        "status": "1",
    }


def _department(department_id, tenant_id=TENANT, name=None):
    return {"id": department_id, "tenant_id": tenant_id, "name": name or department_id, "status": "1"}


def _membership(user_id, tenant_id=TENANT, role="normal"):
    return {"id": f"ut-{user_id}", "user_id": user_id, "tenant_id": tenant_id, "role": role, "invited_by": ADMIN, "status": "1"}


def _grant(subject_type, subject_id):
    return {"id": f"ka-{subject_type}-{subject_id}", "kb_id": KB_ID, "subject_type": subject_type, "subject_id": subject_id, "create_time": 1, "update_time": 1}


def _seed(kb_permission=TenantPermission.ME.value, grants=()):
    Knowledgebase.insert(_kb(kb_permission)).execute()
    for row in (
        _department(DEPT_A),
        _department(DEPT_B),
        _department(DEPT_OTHER_WORKSPACE, tenant_id=OTHER_TENANT),
    ):
        Department.insert(row).execute()
    for row in (
        _membership(ADMIN, role="admin"),
        _membership(MEMBER),
        _membership(OTHER_MEMBER),
        _membership(INVITEE, role="invite"),
        _membership(OUTSIDER, tenant_id=OTHER_TENANT),
    ):
        UserTenant.insert(row).execute()
    for row in grants:
        KnowledgebaseAuthorization.insert(row).execute()


@contextmanager
def _bound(monkeypatch, *, kb_permission=TenantPermission.ME.value, grants=(), writable=True):
    """Private in-memory database, with the write gate stubbed.

    `bind_ctx` binds the models to the database it is called on, so it has to be
    called on the SQLite handle; the assertion pins that down.
    """
    monkeypatch.setattr(KnowledgebaseService, "writable", staticmethod(lambda kb_id, user_id, active_tenant_id=None: writable))
    sqlite = SqliteDatabase(":memory:")
    with sqlite.bind_ctx(MODELS):
        assert Knowledgebase._meta.database is sqlite
        sqlite.create_tables(MODELS)
        _seed(kb_permission, grants)
        yield


@pytest.fixture
def api(monkeypatch):
    with _bound(monkeypatch):
        yield


def _put(req):
    return asyncio.run(dataset_api_service.update_dataset_authorization(KB_ID, ADMIN, req))


def _get():
    return dataset_api_service.get_dataset_authorization(KB_ID, ADMIN)


def _stored_subjects():
    rows = KnowledgebaseAuthorization.select().where(KnowledgebaseAuthorization.kb_id == KB_ID)
    return sorted((row.subject_type, row.subject_id) for row in rows)


def _stored_permission():
    return Knowledgebase.select(Knowledgebase.permission).where(Knowledgebase.id == KB_ID).first().permission


# --------------------------------------------------------------------------- #
# reading
# --------------------------------------------------------------------------- #


def test_get_echoes_the_mode_and_subjects(monkeypatch):
    with _bound(
        monkeypatch,
        kb_permission=TenantPermission.CUSTOM.value,
        grants=[_grant("department", DEPT_A), _grant("user", MEMBER)],
    ):
        ok, result = _get()

    assert ok is True
    assert result["permission"] == "custom"
    assert result["department_ids"] == [DEPT_A]
    assert result["user_ids"] == [MEMBER]


def test_get_reports_an_empty_subject_set_for_a_private_dataset(api):
    ok, result = _get()
    assert ok is True
    assert result == {"permission": "me", "department_ids": [], "user_ids": []}


def test_get_denies_a_caller_who_may_not_write(monkeypatch):
    with _bound(monkeypatch, writable=False):
        ok, result = _get()
    assert ok is False
    assert result == "no authorization"


# --------------------------------------------------------------------------- #
# replacing
# --------------------------------------------------------------------------- #


def test_put_custom_writes_the_subject_set(api):
    ok, result = _put({"permission": "custom", "department_ids": [DEPT_A], "user_ids": [MEMBER]})
    assert ok is True, result
    assert _stored_permission() == "custom"
    assert _stored_subjects() == [("department", DEPT_A), ("user", MEMBER)]


def test_put_replaces_the_subject_set_instead_of_appending(api):
    _put({"permission": "custom", "department_ids": [DEPT_A], "user_ids": [MEMBER]})
    _put({"permission": "custom", "department_ids": [DEPT_B], "user_ids": []})

    assert _stored_permission() == "custom"
    assert _stored_subjects() == [("department", DEPT_B)]


def test_put_with_a_non_custom_mode_clears_the_subjects(api):
    _put({"permission": "custom", "department_ids": [DEPT_A], "user_ids": [MEMBER]})
    ok, result = _put({"permission": "team", "department_ids": [DEPT_A], "user_ids": [MEMBER]})

    assert ok is True, result
    assert _stored_permission() == "team"
    # `team` and `me` are decided by the dataset row alone, so storing subjects
    # for them would be dead data.
    assert _stored_subjects() == []


def test_put_private_mode_clears_the_subjects(api):
    _put({"permission": "custom", "department_ids": [DEPT_A], "user_ids": []})
    _put({"permission": "me"})

    assert _stored_permission() == "me"
    assert _stored_subjects() == []


def test_put_deduplicates_repeated_ids(api):
    ok, _ = _put({"permission": "custom", "department_ids": [DEPT_A, DEPT_A, "  "], "user_ids": [MEMBER, MEMBER]})
    assert ok is True
    assert _stored_subjects() == [("department", DEPT_A), ("user", MEMBER)]


def test_put_denies_a_caller_who_may_not_write(monkeypatch):
    with _bound(monkeypatch, kb_permission=TenantPermission.ME.value, writable=False):
        ok, result = _put({"permission": "custom", "department_ids": [DEPT_A], "user_ids": []})
        stored = _stored_subjects()

    assert ok is False
    assert result == "no authorization"
    assert stored == []


# --------------------------------------------------------------------------- #
# validation: a subject set may not reach outside the owning workspace
# --------------------------------------------------------------------------- #


def test_put_rejects_an_unknown_mode(api):
    ok, result = _put({"permission": "public", "department_ids": [], "user_ids": []})
    assert ok is False
    assert "permission" in result
    assert _stored_permission() == "me"


def test_put_rejects_a_department_from_another_workspace(api):
    ok, result = _put({"permission": "custom", "department_ids": [DEPT_OTHER_WORKSPACE], "user_ids": []})
    assert ok is False
    assert DEPT_OTHER_WORKSPACE in result
    # Nothing is stored, and the mode is untouched: the request was refused, not
    # partially applied.
    assert _stored_subjects() == []
    assert _stored_permission() == "me"


def test_put_rejects_a_missing_department(api):
    ok, result = _put({"permission": "custom", "department_ids": ["dept-does-not-exist"], "user_ids": []})
    assert ok is False
    assert "dept-does-not-exist" in result


def test_put_rejects_a_user_who_is_not_a_member(api):
    ok, result = _put({"permission": "custom", "department_ids": [], "user_ids": [OUTSIDER]})
    assert ok is False
    assert OUTSIDER in result
    assert _stored_subjects() == []


def test_put_rejects_a_pending_invitation(api):
    """An invite row is not a membership, so it cannot be granted to."""
    ok, result = _put({"permission": "custom", "department_ids": [], "user_ids": [INVITEE]})
    assert ok is False
    assert INVITEE in result


def test_put_reads_a_bare_string_as_a_single_id(api):
    ok, _ = _put({"permission": "custom", "department_ids": DEPT_A, "user_ids": MEMBER})
    assert ok is True
    assert _stored_subjects() == [("department", DEPT_A), ("user", MEMBER)]


@pytest.mark.parametrize("value", [{"a": 1}, 7, [1], ["dept-a", 2]])
def test_put_rejects_malformed_id_lists(api, value):
    with pytest.raises(ValueError):
        _put({"permission": "custom", "department_ids": value, "user_ids": []})


def test_put_accepts_an_individual_alongside_a_department(api):
    ok, _ = _put({"permission": "custom", "department_ids": [DEPT_A, DEPT_B], "user_ids": [MEMBER, OTHER_MEMBER]})
    assert ok is True
    assert _stored_subjects() == [
        ("department", DEPT_A),
        ("department", DEPT_B),
        ("user", MEMBER),
        ("user", OTHER_MEMBER),
    ]
