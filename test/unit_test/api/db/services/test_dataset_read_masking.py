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
"""The P3-03 listing mask, exercised on in-memory SQLite.

The models are bound to a temporary SQLite database for the duration of each
test, so the real `_readable_filter` expression and the real listing queries run
against real rows -- the matrix here is query behaviour, not a string match on
generated SQL. The service methods are called through ``__wrapped__`` because
their ``@DB.connection_context()`` manages the pool connection of the configured
database rather than the bound one; only connection management is bypassed.
"""

from contextlib import contextmanager

import pytest
from peewee import SqliteDatabase

from api.db import TenantPermission
from api.db.db_models import Knowledgebase, KnowledgebaseAuthorization, UserTenant
from api.db.joint_services.kb_authorization_service import can_read_dataset
from api.db.services.knowledgebase_service import KnowledgebaseService as K

pytestmark = pytest.mark.p1

T1 = "tenant-1"
T2 = "tenant-2"
DEPT_A = "dept-a"
DEPT_B = "dept-b"

OWNER = "user-owner"
ADMIN = "user-admin"
MEMBER = "user-member"
OTHER_DEPT = "user-other-dept"
UNPLACED = "user-unplaced"
OUTSIDER = "user-outsider"

KB_TEAM = "kb-team"
KB_PRIVATE = "kb-private"
KB_CUSTOM_DEPT_A = "kb-custom-dept-a"
KB_CUSTOM_DEPT_B = "kb-custom-dept-b"
KB_CUSTOM_USER = "kb-custom-user"
KB_CUSTOM_EMPTY = "kb-custom-empty"
KB_MEMBER_OWN = "kb-member-own"
KB_OTHER_WORKSPACE = "kb-other-workspace"

MODELS = [Knowledgebase, UserTenant, KnowledgebaseAuthorization]


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
    return {
        "id": f"ka-{kb_id}-{subject_type}-{subject_id}",
        "kb_id": kb_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "create_time": 1,
        "update_time": 1,
    }


def _seed():
    for row in (
        _kb(KB_TEAM, TenantPermission.TEAM.value),
        _kb(KB_PRIVATE, TenantPermission.ME.value),
        _kb(KB_CUSTOM_DEPT_A, TenantPermission.CUSTOM.value),
        _kb(KB_CUSTOM_DEPT_B, TenantPermission.CUSTOM.value),
        _kb(KB_CUSTOM_USER, TenantPermission.CUSTOM.value),
        _kb(KB_CUSTOM_EMPTY, TenantPermission.CUSTOM.value),
        _kb(KB_MEMBER_OWN, TenantPermission.ME.value, created_by=MEMBER),
        _kb(KB_OTHER_WORKSPACE, TenantPermission.TEAM.value, tenant_id=T2, created_by=ADMIN),
    ):
        Knowledgebase.insert(row).execute()

    for row in (
        _membership(OWNER, T1, role="owner"),
        _membership(ADMIN, T1, role="admin"),
        _membership(MEMBER, T1, department_id=DEPT_A),
        _membership(OTHER_DEPT, T1, department_id=DEPT_B),
        _membership(UNPLACED, T1),
        _membership(OUTSIDER, T2),
    ):
        UserTenant.insert(row).execute()

    for row in (
        _grant(KB_CUSTOM_DEPT_A, "department", DEPT_A),
        _grant(KB_CUSTOM_DEPT_B, "department", DEPT_B),
        _grant(KB_CUSTOM_USER, "user", MEMBER),
    ):
        KnowledgebaseAuthorization.insert(row).execute()


class Api:
    """The listing paths under test, as the callers use them."""

    def listed(self, user_id, active_tenant_id):
        """The ids the dataset page returns for one workspace."""
        kbs, _total = K.get_list.__func__.__wrapped__(K, user_id, active_tenant_id, 1, 50, "create_time", True, None, None, "", None, None)
        return {kb["id"] for kb in kbs}

    def accessible_ids(self, user_id, active_tenant_id, ids):
        """The ids the `ids=` filter admits out of a requested set."""
        return K.get_accessible_ids.__func__.__wrapped__(K, user_id, active_tenant_id, ids)

    def may_read(self, user_id, active_tenant_id, kb_id):
        return can_read_dataset.__wrapped__(user_id, active_tenant_id, Knowledgebase.get_by_id(kb_id))


@contextmanager
def _bound():
    """Bind the models to a private in-memory database for the duration.

    `bind_ctx` binds the models to the database it is *called on*, so it has to
    be called on the SQLite handle rather than on `DB`. The assertion pins that
    down: getting it backwards binds the models to the configured database, and
    the seed below would then write to it instead of to the temporary one.
    """
    sqlite = SqliteDatabase(":memory:")
    with sqlite.bind_ctx(MODELS):
        assert Knowledgebase._meta.database is sqlite
        sqlite.create_tables(MODELS)
        _seed()
        yield Api()


@pytest.fixture
def api():
    with _bound() as bound_api:
        yield bound_api


# --------------------------------------------------------------------------- #
# the visibility matrix
# --------------------------------------------------------------------------- #


def test_workspace_manager_sees_every_dataset_of_the_workspace(api):
    expected = {KB_TEAM, KB_PRIVATE, KB_CUSTOM_DEPT_A, KB_CUSTOM_DEPT_B, KB_CUSTOM_USER, KB_CUSTOM_EMPTY, KB_MEMBER_OWN}
    assert api.listed(OWNER, T1) == expected
    assert api.listed(ADMIN, T1) == expected


def test_normal_member_sees_only_team_own_and_granted_datasets(api):
    """The core of P3-03: nothing private, nothing unshared, nothing ungranted."""
    assert api.listed(MEMBER, T1) == {KB_TEAM, KB_MEMBER_OWN, KB_CUSTOM_DEPT_A, KB_CUSTOM_USER}


def test_private_dataset_is_hidden_from_a_workspace_member(api):
    assert KB_PRIVATE not in api.listed(MEMBER, T1)
    assert api.may_read(MEMBER, T1, KB_PRIVATE) is False


def test_a_custom_grant_for_a_department_reaches_only_that_department(api):
    assert KB_CUSTOM_DEPT_A in api.listed(MEMBER, T1)
    assert KB_CUSTOM_DEPT_A not in api.listed(OTHER_DEPT, T1)
    assert KB_CUSTOM_DEPT_B in api.listed(OTHER_DEPT, T1)
    assert KB_CUSTOM_DEPT_B not in api.listed(MEMBER, T1)


def test_an_unplaced_member_is_never_captured_by_a_department_grant(api):
    listed = api.listed(UNPLACED, T1)
    assert KB_CUSTOM_DEPT_A not in listed
    assert KB_CUSTOM_DEPT_B not in listed
    # Team sharing is a membership rule and still applies.
    assert listed == {KB_TEAM}


def test_an_individual_grant_reaches_exactly_one_member(api):
    assert KB_CUSTOM_USER in api.listed(MEMBER, T1)
    assert KB_CUSTOM_USER not in api.listed(OTHER_DEPT, T1)
    assert KB_CUSTOM_USER not in api.listed(UNPLACED, T1)


def test_a_custom_dataset_without_grants_reaches_no_member(api):
    for user_id in (MEMBER, OTHER_DEPT, UNPLACED):
        assert KB_CUSTOM_EMPTY not in api.listed(user_id, T1)


def test_a_creator_keeps_their_own_dataset_in_every_mode(api):
    assert KB_MEMBER_OWN in api.listed(MEMBER, T1)
    assert api.may_read(MEMBER, T1, KB_MEMBER_OWN) is True


def test_department_grant_follows_a_transfer(api):
    """A standing grant: moving the member changes what it reaches."""
    assert KB_CUSTOM_DEPT_A in api.listed(MEMBER, T1)

    UserTenant.update(department_id=DEPT_B).where((UserTenant.user_id == MEMBER) & (UserTenant.tenant_id == T1)).execute()

    listed = api.listed(MEMBER, T1)
    assert KB_CUSTOM_DEPT_A not in listed
    assert KB_CUSTOM_DEPT_B in listed


def test_a_pending_invitation_is_not_a_membership(api):
    """An `invite` row is a pending invitation, so it carries no workspace access.

    Accepting it rewrites that same row as NORMAL, which is when the workspace's
    shared datasets become readable.
    """
    UserTenant.insert(_membership("invitee", T1, role="invite", department_id=DEPT_A)).execute()

    assert api.listed("invitee", T1) == set()
    assert api.may_read("invitee", T1, KB_TEAM) is False
    # Nor does a department grant reach a pending invitee.
    assert api.may_read("invitee", T1, KB_CUSTOM_DEPT_A) is False

    UserTenant.update(role="normal").where(UserTenant.user_id == "invitee").execute()
    assert KB_TEAM in api.listed("invitee", T1)


def test_a_foreign_scope_reveals_nothing(api):
    """A membership on the dataset's workspace is required, not just a scope id."""
    assert api.listed(OUTSIDER, T1) == set()
    assert api.listed(MEMBER, T2) == set()
    assert api.listed(OUTSIDER, T2) == {KB_OTHER_WORKSPACE}


def test_an_empty_scope_or_caller_lists_nothing(api):
    assert api.listed(MEMBER, "") == set()
    assert api.listed(MEMBER, None) == set()
    assert api.listed("", T1) == set()
    assert api.listed(None, T1) == set()


def test_a_bare_tenant_id_is_treated_as_one_workspace(api):
    assert K._readable_filter(MEMBER, T1).__sql__ is not None
    assert api.listed(MEMBER, T1) == api.listed(MEMBER, [T1])


def test_an_unknown_permission_is_hidden_from_a_member(api):
    Knowledgebase.update(permission="something-new").where(Knowledgebase.id == KB_TEAM).execute()
    assert KB_TEAM not in api.listed(MEMBER, T1)
    assert KB_TEAM in api.listed(OWNER, T1)


def test_an_invalid_dataset_is_never_listed(api):
    Knowledgebase.update(status="0").where(Knowledgebase.id == KB_TEAM).execute()
    assert KB_TEAM not in api.listed(MEMBER, T1)
    assert KB_TEAM not in api.listed(OWNER, T1)


# --------------------------------------------------------------------------- #
# the other listing paths use the same mask
# --------------------------------------------------------------------------- #


def test_the_ids_filter_admits_only_readable_datasets(api):
    requested = [KB_TEAM, KB_PRIVATE, KB_CUSTOM_DEPT_A, KB_OTHER_WORKSPACE]
    assert api.accessible_ids(MEMBER, T1, requested) == {KB_TEAM, KB_CUSTOM_DEPT_A}
    assert api.accessible_ids(OWNER, T1, requested) == {KB_TEAM, KB_PRIVATE, KB_CUSTOM_DEPT_A}


def test_the_ids_filter_masks_a_denied_id_rather_than_erroring(api):
    """A denied id must disappear, so a listing cannot confirm it exists."""
    assert api.accessible_ids(OUTSIDER, T1, [KB_PRIVATE, KB_TEAM]) == set()


def test_listing_and_by_id_agree_for_datasets_in_scope(api):
    """A dataset the list hides must not be openable by id, and vice versa."""
    for user_id, active in ((OWNER, T1), (ADMIN, T1), (MEMBER, T1), (OTHER_DEPT, T1), (UNPLACED, T1), (OUTSIDER, T1), (OUTSIDER, T2)):
        listed = api.listed(user_id, active)
        for row in Knowledgebase.select().where(Knowledgebase.status == "1"):
            if row.tenant_id != active or not active:
                continue
            assert (row.id in listed) is api.may_read(user_id, active, row.id), (user_id, active, row.id)
