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
"""Model-configuration read resolution.

A member that owns no tenant of its own has no model configuration to read:
the credentials live in the tenant it joined. These tests pin that a member
falls back to the shared tenant while anyone holding a membership on their own
id keeps reading their own, which is what keeps an owner and a delegated admin
unaffected by the fallback.
"""

import pytest

from api.db import UserTenantRole
from api.db.services.user_service import TenantService, UserTenantService


def _resolve(monkeypatch, own_role, joined):
    """Call the resolver without a database connection.

    ``resolve_config_tenant_id`` is wrapped by ``DB.connection_context()``, so
    the undecorated function is reached the same way the neighbouring
    dataset-access tests reach ``KnowledgebaseService.accessible``.
    """
    monkeypatch.setattr(UserTenantService, "get_role", classmethod(lambda cls, user_id, tenant_id: own_role))
    monkeypatch.setattr(TenantService, "get_joined_tenants_by_user_id", classmethod(lambda cls, user_id: joined))
    return TenantService.resolve_config_tenant_id.__func__.__wrapped__


@pytest.mark.parametrize("role", [UserTenantRole.OWNER, UserTenantRole.ADMIN, UserTenantRole.NORMAL])
def test_a_caller_with_a_membership_on_its_own_id_keeps_reading_its_own_tenant(monkeypatch, role):
    def _must_not_consult_joined(cls, user_id):
        raise AssertionError("a caller with its own tenant must not fall back to a joined tenant")

    monkeypatch.setattr(UserTenantService, "get_role", classmethod(lambda cls, user_id, tenant_id: role))
    monkeypatch.setattr(TenantService, "get_joined_tenants_by_user_id", classmethod(_must_not_consult_joined))

    resolved = TenantService.resolve_config_tenant_id.__func__.__wrapped__(TenantService, "tenant-self")

    assert resolved == "tenant-self"


def test_a_member_without_a_tenant_of_its_own_reads_the_tenant_it_joined(monkeypatch):
    resolve = _resolve(monkeypatch, None, [{"tenant_id": "tenant-shared", "role": UserTenantRole.NORMAL}])

    assert resolve(TenantService, "user-member") == "tenant-shared"


def test_a_member_of_several_tenants_reads_the_oldest_membership(monkeypatch):
    # `get_joined_tenants_by_user_id` orders by tenant create_time, so the first
    # entry is the stable choice rather than whichever row the database returns
    # first.
    resolve = _resolve(
        monkeypatch,
        None,
        [
            {"tenant_id": "tenant-first", "role": UserTenantRole.NORMAL},
            {"tenant_id": "tenant-second", "role": UserTenantRole.NORMAL},
        ],
    )

    assert resolve(TenantService, "user-member") == "tenant-first"


def test_a_caller_with_neither_membership_reads_its_own_id(monkeypatch):
    resolve = _resolve(monkeypatch, None, [])

    assert resolve(TenantService, "user-orphan") == "user-orphan"
