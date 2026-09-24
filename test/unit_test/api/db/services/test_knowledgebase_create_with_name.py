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
"""The dataset-create payload contract (tenant context).

Two properties are covered here.

`created_by` is the dataset's *author*: it equals `tenant_id` only for an owner,
whose tenant id IS their user id. A member creating a dataset in a workspace it
joined must be recorded as the author by its own user id, otherwise the dataset
is attributed to the workspace and -- since a `permission='me'` dataset is
readable and writable by its creator and the workspace's managers alone -- the
member can neither see nor edit what it just created.

The explicit fields (`id`, `name`, `tenant_id`, `created_by`, `parser_id`) also
have to outrank the optional fields a caller passes through `**kwargs`, and every
failure has to come back as a plain string: the route re-wraps a service message
with `get_error_data_result(message=...)`, and a Quart `Response` there makes
`jsonify` fail with `code=101 "Unable to serialize unknown type: Response"`.
"""

from types import SimpleNamespace

import pytest

from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService

pytestmark = pytest.mark.p2

WORKSPACE = "workspace-tenant"
OWNER = "owner-user"
MEMBER = "member-user"


def _create(**kwargs):
    """Call the undecorated create path, so no database is needed."""
    return KnowledgebaseService.create_with_name.__func__.__wrapped__(KnowledgebaseService, **kwargs)


@pytest.fixture
def stubbed_db(monkeypatch):
    """Stub the two lookups `create_with_name` makes; nothing else is touched.

    `query` answers "no dataset with that name yet", so the name is kept as the
    caller wrote it, and the tenant exists so the create path is not refused.
    """
    monkeypatch.setattr(KnowledgebaseService, "query", classmethod(lambda cls, **_kwargs: []))
    monkeypatch.setattr(TenantService, "get_by_id", classmethod(lambda cls, _tenant_id: (True, SimpleNamespace(llm_id="llm-1"))))


def test_created_by_defaults_to_the_tenant_for_an_owner(stubbed_db):
    """An owner's tenant id IS its user id, so the fallback is already the author."""
    ok, payload = _create(name="kb", tenant_id=OWNER)

    assert ok is True
    assert payload["tenant_id"] == OWNER
    assert payload["created_by"] == OWNER


def test_created_by_is_the_author_not_the_workspace(stubbed_db):
    """A member's dataset belongs to the workspace and is authored by the member."""
    ok, payload = _create(name="kb", tenant_id=WORKSPACE, created_by=MEMBER)

    assert ok is True
    assert payload["tenant_id"] == WORKSPACE
    assert payload["created_by"] == MEMBER


def test_the_explicit_fields_outrank_the_optional_kwargs(stubbed_db):
    """`id` reaches the payload through `**kwargs` and must not win."""
    ok, payload = _create(name="kb", tenant_id=WORKSPACE, created_by=MEMBER, id="forced-id", description="described")

    assert ok is True
    assert payload["id"] != "forced-id"
    assert payload["name"] == "kb"
    assert payload["tenant_id"] == WORKSPACE
    assert payload["created_by"] == MEMBER
    # The optional fields still pass through.
    assert payload["description"] == "described"


@pytest.mark.parametrize("field", ["name", "tenant_id", "created_by"])
def test_the_kwargs_cannot_carry_an_explicit_field(stubbed_db, field):
    """A caller cannot smuggle one of them into `**kwargs`: it is a parameter.

    This is what keeps the request body from setting the dataset's workspace or
    author -- the field would have to be declared, and a declared field is
    rejected as a duplicate keyword argument before any payload is built.
    """
    with pytest.raises(TypeError):
        _create(name="kb", tenant_id=WORKSPACE, created_by=MEMBER, **{field: "attacker"})


def test_a_missing_tenant_is_a_plain_message(stubbed_db, monkeypatch):
    """Never a Response: the route wraps this string in its own error result."""
    monkeypatch.setattr(TenantService, "get_by_id", classmethod(lambda cls, _tenant_id: (False, None)))

    ok, message = _create(name="kb", tenant_id="tenant-nowhere")

    assert ok is False
    assert message == "Tenant not found."
    assert type(message) is str


@pytest.mark.parametrize(
    "name,expected",
    [
        (None, "Dataset name must be string."),
        ("  ", "dataset name can't be empty"),
        ("x" * 200, "Dataset name length is 200 which is large than 128"),
    ],
)
def test_a_rejected_name_is_a_plain_message(stubbed_db, name, expected):
    ok, message = _create(name=name, tenant_id=WORKSPACE)

    assert ok is False
    assert message == expected
    assert type(message) is str
