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
"""The P3-03 role x mode matrix, without a database.

The predicates are called unwrapped, past their connection context, and the four
seams that would query -- tenant role, membership, department placement and the
grant lookup -- are replaced with in-memory sets. That keeps the matrix fast and
deterministic; the SQL behind those seams is exercised against the live database
by the P3-03 integration checks.
"""

from types import SimpleNamespace

import pytest

from api.db import TenantPermission
from api.db.joint_services import kb_authorization_service as kbs
from api.db.joint_services.kb_authorization_service import SUBJECT_DEPARTMENT, SUBJECT_USER

pytestmark = pytest.mark.p1

TENANT = "tenant-a"
OTHER_TENANT = "tenant-b"
DEPT_FINANCE = "dept-finance"
DEPT_SALES = "dept-sales"

CREATOR = "user-creator"
OWNER = "user-owner"
ADMIN = "user-admin"
MEMBER = "user-member"
OUTSIDER = "user-outsider"

MODES = [TenantPermission.ME.value, TenantPermission.TEAM.value, TenantPermission.CUSTOM.value]


def make_kb(permission, *, tenant_id=TENANT, created_by=CREATOR, kb_id="kb-1"):
    return SimpleNamespace(id=kb_id, tenant_id=tenant_id, created_by=created_by, permission=permission)


def install(monkeypatch, *, managers=(), members=(), placements=None, grants=()):
    """Replace the querying seams with in-memory facts.

    `managers` and `members` are `(user_id, tenant_id)` pairs, `placements` maps
    such a pair to a department id, and `grants` holds `(kb_id, subject_type,
    subject_id)` triples.
    """
    managers = set(managers)
    members = set(members)
    placements = dict(placements or {})
    grants = set(grants)

    monkeypatch.setattr(kbs, "_can_manage_tenant", lambda user_id, tenant_id: (user_id, tenant_id) in managers)
    monkeypatch.setattr(kbs, "_membership_role", lambda user_id, tenant_id: "normal" if (user_id, tenant_id) in members else None)
    monkeypatch.setattr(kbs, "_department_id_of", lambda user_id, tenant_id: placements.get((user_id, tenant_id)))

    def fake_granted(kb_id, user_id, department_id):
        if not department_id:
            return (kb_id, SUBJECT_USER, user_id) in grants
        return (kb_id, SUBJECT_USER, user_id) in grants or (kb_id, SUBJECT_DEPARTMENT, department_id) in grants

    monkeypatch.setattr(kbs, "_is_granted", fake_granted)


def can_read(user_id, kb, active_tenant_id=TENANT):
    return kbs.can_read_dataset.__wrapped__(user_id, active_tenant_id, kb)


def can_write(user_id, kb, active_tenant_id=TENANT):
    return kbs.can_write_dataset.__wrapped__(user_id, active_tenant_id, kb)


# --------------------------------------------------------------------------- #
# can_read_dataset
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", MODES)
def test_creator_can_read_every_mode(monkeypatch, mode):
    install(monkeypatch, members=[(CREATOR, TENANT)])
    assert can_read(CREATOR, make_kb(mode)) is True


@pytest.mark.parametrize("mode", MODES)
def test_workspace_owner_can_read_every_mode(monkeypatch, mode):
    install(monkeypatch, managers=[(OWNER, TENANT)], members=[(OWNER, TENANT)])
    assert can_read(OWNER, make_kb(mode)) is True


@pytest.mark.parametrize("mode", MODES)
def test_workspace_admin_can_read_every_mode(monkeypatch, mode):
    install(monkeypatch, managers=[(ADMIN, TENANT)], members=[(ADMIN, TENANT)])
    assert can_read(ADMIN, make_kb(mode)) is True


def test_private_dataset_is_readable_by_creator_and_managers_only(monkeypatch):
    """`me` is the creator plus the workspace's managers, and nobody else."""
    install(
        monkeypatch,
        managers=[(OWNER, TENANT), (ADMIN, TENANT)],
        members=[(CREATOR, TENANT), (OWNER, TENANT), (ADMIN, TENANT), (MEMBER, TENANT), (OUTSIDER, OTHER_TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
    )
    kb = make_kb(TenantPermission.ME.value)

    assert can_read(CREATOR, kb) is True
    assert can_read(OWNER, kb) is True
    assert can_read(ADMIN, kb) is True
    assert can_read(MEMBER, kb) is False
    assert can_read(OUTSIDER, kb) is False


def test_team_dataset_is_readable_by_every_workspace_member(monkeypatch):
    install(
        monkeypatch,
        managers=[(OWNER, TENANT)],
        members=[(CREATOR, TENANT), (OWNER, TENANT), (MEMBER, TENANT), (OUTSIDER, OTHER_TENANT)],
    )
    kb = make_kb(TenantPermission.TEAM.value)

    assert can_read(CREATOR, kb) is True
    assert can_read(OWNER, kb) is True
    assert can_read(MEMBER, kb) is True
    # A member of another workspace holds no membership on the dataset's tenant.
    assert can_read(OUTSIDER, kb) is False


def test_custom_dataset_reaches_the_granted_department(monkeypatch):
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
        grants=[("kb-1", SUBJECT_DEPARTMENT, DEPT_FINANCE)],
    )
    kb = make_kb(TenantPermission.CUSTOM.value)

    assert can_read(CREATOR, kb) is True
    assert can_read(MEMBER, kb) is True


def test_custom_dataset_denies_a_member_of_an_ungranted_department(monkeypatch):
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT)],
        placements={(MEMBER, TENANT): DEPT_SALES},
        grants=[("kb-1", SUBJECT_DEPARTMENT, DEPT_FINANCE)],
    )
    assert can_read(MEMBER, make_kb(TenantPermission.CUSTOM.value)) is False


def test_custom_dataset_reaches_an_explicitly_granted_individual(monkeypatch):
    """An individual grant is honoured even outside the workspace membership."""
    install(monkeypatch, members=[(CREATOR, TENANT)], grants=[("kb-1", SUBJECT_USER, OUTSIDER)])
    assert can_read(OUTSIDER, make_kb(TenantPermission.CUSTOM.value)) is True


def test_custom_dataset_denies_an_unplaced_member(monkeypatch):
    """A member with no department is never captured by a department grant."""
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT)],
        placements={(MEMBER, TENANT): None},
        grants=[("kb-1", SUBJECT_DEPARTMENT, DEPT_FINANCE)],
    )
    assert can_read(MEMBER, make_kb(TenantPermission.CUSTOM.value)) is False


def test_department_grant_follows_the_current_placement(monkeypatch):
    """The grant is bound to the department, so a transfer changes the outcome.

    The grant set is identical in both halves; only the member's placement
    differs, which is what makes a department grant dynamic.
    """
    grants = [("kb-1", SUBJECT_DEPARTMENT, DEPT_SALES)]
    kb = make_kb(TenantPermission.CUSTOM.value)

    install(monkeypatch, members=[(CREATOR, TENANT), (MEMBER, TENANT)], placements={(MEMBER, TENANT): DEPT_FINANCE}, grants=grants)
    assert can_read(MEMBER, kb) is False

    install(monkeypatch, members=[(CREATOR, TENANT), (MEMBER, TENANT)], placements={(MEMBER, TENANT): DEPT_SALES}, grants=grants)
    assert can_read(MEMBER, kb) is True


def test_custom_grant_does_not_leak_across_datasets(monkeypatch):
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
        grants=[("kb-other", SUBJECT_DEPARTMENT, DEPT_FINANCE)],
    )
    assert can_read(MEMBER, make_kb(TenantPermission.CUSTOM.value, kb_id="kb-1")) is False


def test_manager_of_another_active_workspace_cannot_read(monkeypatch):
    """Administrating a different workspace grants nothing here."""
    install(monkeypatch, managers=[(ADMIN, OTHER_TENANT)], members=[(ADMIN, OTHER_TENANT)])
    kb = make_kb(TenantPermission.ME.value, tenant_id=TENANT)

    assert can_read(ADMIN, kb, active_tenant_id=OTHER_TENANT) is False
    assert can_read(ADMIN, kb, active_tenant_id=TENANT) is False


def test_manager_check_falls_back_to_the_dataset_tenant(monkeypatch):
    """With no active workspace supplied, the owning tenant is what counts."""
    install(monkeypatch, managers=[(ADMIN, TENANT)], members=[(ADMIN, TENANT)])
    assert can_read(ADMIN, make_kb(TenantPermission.ME.value), active_tenant_id=None) is True


def test_unknown_permission_is_denied(monkeypatch):
    install(monkeypatch, members=[(MEMBER, TENANT)])
    assert can_read(MEMBER, make_kb("something-new")) is False


def test_read_denies_missing_inputs(monkeypatch):
    install(monkeypatch)
    assert can_read(None, make_kb(TenantPermission.TEAM.value)) is False
    assert can_read("", make_kb(TenantPermission.TEAM.value)) is False
    assert can_read(MEMBER, None) is False


# --------------------------------------------------------------------------- #
# can_write_dataset
# --------------------------------------------------------------------------- #


@pytest.mark.p0
def test_custom_authorized_reader_is_never_an_editor(monkeypatch):
    """The whole point of the split: read access does not carry write access."""
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT), (OUTSIDER, TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
        grants=[
            ("kb-1", SUBJECT_DEPARTMENT, DEPT_FINANCE),
            ("kb-1", SUBJECT_USER, OUTSIDER),
        ],
    )
    kb = make_kb(TenantPermission.CUSTOM.value)

    assert can_read(MEMBER, kb) is True
    assert can_write(MEMBER, kb) is False

    # Individually granted, and not even a member of the workspace.
    assert can_read(OUTSIDER, kb) is True
    assert can_write(OUTSIDER, kb) is False


@pytest.mark.p0
@pytest.mark.parametrize("mode", MODES)
def test_grant_rows_never_confer_write_in_any_mode(monkeypatch, mode):
    """Grant rows are read-only affordances, and only `custom` reads them."""
    install(
        monkeypatch,
        members=[(CREATOR, TENANT), (MEMBER, TENANT), (OUTSIDER, TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
        grants=[
            ("kb-1", SUBJECT_DEPARTMENT, DEPT_FINANCE),
            ("kb-1", SUBJECT_USER, OUTSIDER),
        ],
    )
    kb = make_kb(mode)

    assert can_write(MEMBER, kb) is False
    assert can_write(OUTSIDER, kb) is False


@pytest.mark.parametrize("mode", MODES)
def test_write_matrix_by_role(monkeypatch, mode):
    install(
        monkeypatch,
        managers=[(OWNER, TENANT), (ADMIN, TENANT)],
        members=[(CREATOR, TENANT), (OWNER, TENANT), (ADMIN, TENANT), (MEMBER, TENANT), (OUTSIDER, OTHER_TENANT)],
        placements={(MEMBER, TENANT): DEPT_FINANCE},
    )
    kb = make_kb(mode)

    assert can_write(CREATOR, kb) is True
    assert can_write(OWNER, kb) is True
    assert can_write(ADMIN, kb) is True
    assert can_write(MEMBER, kb) is False
    assert can_write(OUTSIDER, kb) is False


def test_workspace_membership_does_not_confer_write(monkeypatch):
    """Team visibility is a read rule; it is not an editing rule."""
    install(monkeypatch, members=[(MEMBER, TENANT)])
    assert can_write(MEMBER, make_kb(TenantPermission.TEAM.value)) is False


def test_manager_of_another_active_workspace_cannot_write(monkeypatch):
    install(monkeypatch, managers=[(ADMIN, OTHER_TENANT)], members=[(ADMIN, OTHER_TENANT)])
    kb = make_kb(TenantPermission.TEAM.value, tenant_id=TENANT)
    assert can_write(ADMIN, kb, active_tenant_id=OTHER_TENANT) is False


def test_creator_keeps_write_access_in_a_shared_workspace(monkeypatch):
    """The creator writes without holding any role, and without a grant row."""
    install(monkeypatch, members=[(CREATOR, TENANT)])
    kb = make_kb(TenantPermission.ME.value, created_by=CREATOR)
    assert can_write(CREATOR, kb) is True


def test_write_denies_missing_inputs(monkeypatch):
    install(monkeypatch)
    assert can_write(None, make_kb(TenantPermission.TEAM.value)) is False
    assert can_write("", make_kb(TenantPermission.TEAM.value)) is False
    assert can_write(MEMBER, None) is False


# --------------------------------------------------------------------------- #
# subject normalization and the replace contract
# --------------------------------------------------------------------------- #


def test_normalize_subjects_collapses_duplicates():
    """A duplicate would collide with the unique index and fail the whole save."""
    subjects = [
        {"subject_type": SUBJECT_DEPARTMENT, "subject_id": DEPT_FINANCE},
        {"subject_type": SUBJECT_DEPARTMENT, "subject_id": DEPT_FINANCE},
        {"subject_type": SUBJECT_USER, "subject_id": DEPT_FINANCE},
        {"subject_type": SUBJECT_DEPARTMENT, "subject_id": DEPT_SALES},
    ]
    assert kbs._normalize_subjects(subjects) == [
        {"subject_type": SUBJECT_DEPARTMENT, "subject_id": DEPT_FINANCE},
        {"subject_type": SUBJECT_USER, "subject_id": DEPT_FINANCE},
        {"subject_type": SUBJECT_DEPARTMENT, "subject_id": DEPT_SALES},
    ]


def test_normalize_subjects_trims_and_accepts_empty():
    assert kbs._normalize_subjects(None) == []
    assert kbs._normalize_subjects([]) == []
    assert kbs._normalize_subjects([{"subject_type": " user ", "subject_id": " u-1 "}]) == [{"subject_type": SUBJECT_USER, "subject_id": "u-1"}]


@pytest.mark.parametrize(
    "subject",
    [
        {"subject_type": "tenant", "subject_id": "t-1"},
        {"subject_type": "", "subject_id": "t-1"},
        {"subject_type": SUBJECT_USER, "subject_id": ""},
        {"subject_type": SUBJECT_USER},
        "not-a-dict",
    ],
)
def test_normalize_subjects_rejects_bad_input(subject):
    with pytest.raises(ValueError):
        kbs._normalize_subjects([subject])


def test_replace_rejects_bad_input_before_touching_the_database():
    """Validation runs before the transaction opens, so nothing is deleted."""
    with pytest.raises(ValueError):
        kbs.replace_kb_authorizations.__wrapped__("kb-1", [{"subject_type": "tenant", "subject_id": "t-1"}])

    with pytest.raises(ValueError):
        kbs.replace_kb_authorizations.__wrapped__("", [{"subject_type": SUBJECT_USER, "subject_id": "u-1"}])


def test_get_authorizations_without_a_kb_returns_empty():
    assert kbs.get_kb_authorizations.__wrapped__("") == []
    assert kbs.get_kb_authorizations.__wrapped__(None) == []
