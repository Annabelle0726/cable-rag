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
"""Unit tests for ``require_tenant_admin``.

The decorator is exercised with the database predicate and the current-user
proxy stubbed out, so these cases cover the guard's own logic: which tenant is
checked, what happens when the predicate denies, and how the decorator composes
with ``add_tenant_id_to_kwargs``.

Runnable directly (``python test/unit_test/api/apps/test_require_tenant_admin.py``)
as well as under pytest, because the module it lives in pulls in the whole
application at import time and is easiest to run where the app config exists.
"""

import asyncio
import json
import sys
from unittest.mock import patch

import api.apps as apps_module
from api.apps import require_tenant_admin
from api.utils.api_utils import add_tenant_id_to_kwargs
from quart_auth import Unauthorized

USER_ID = "a9e28731ab7011f19b833887d563fb04"
OTHER_TENANT_ID = "someone-elses-tenant-id"
DENIED = object()


class FakeUser:
    def __init__(self, user_id):
        self.id = user_id


def _run(coro):
    """Run a coroutine on a fresh loop, and close it rather than leaking it.

    Each case needs its own loop, and a loop that is only collected leaks the
    socket pair it opened; with warnings configured as errors that surfaced as
    an unraisable-exception failure in whichever case triggered the collection.
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _invoke(wrapper, **kwargs):
    """Call a decorated view inside a real Quart application context."""
    async with apps_module.app.app_context():
        return await wrapper(**kwargs)


async def _invoke_code(wrapper, **kwargs):
    """Call a decorated view and read the RetCode off the JSON body it returned."""
    async with apps_module.app.app_context():
        response = await wrapper(**kwargs)
        return json.loads(await response.get_data())["code"]


def _make_view(record):
    async def view(**kwargs):
        record.append(kwargs)
        return "VIEW_RAN"

    return view


# ---------------------------------------------------------------------------
# Authorisation outcome
# ---------------------------------------------------------------------------


def test_allowed_caller_reaches_the_view():
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        # Stubbed so the guard's own logic is under test rather than the
        # database the resolver would read.
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=USER_ID),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage,
    ):
        assert _run(_invoke(view)) == "VIEW_RAN"
    # tenant_id is absent, so the caller's own tenant is the subject.
    can_manage.assert_called_once_with(USER_ID, USER_ID)
    assert len(record) == 1


def test_denied_caller_does_not_reach_the_view():
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False),
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED) as denied,
    ):
        assert _run(_invoke(view)) is DENIED
    denied.assert_called_once()
    assert record == [], "the view must not run when the guard denies"


def test_unauthenticated_caller_is_rejected():
    record = []
    view = require_tenant_admin(_make_view(record))
    with patch.object(apps_module, "current_user", None):
        try:
            _run(_invoke(view))
        except Unauthorized:
            pass
        else:
            raise AssertionError("expected Unauthorized when there is no current user")
    assert record == []


# ---------------------------------------------------------------------------
# Which tenant is checked
# ---------------------------------------------------------------------------


def test_an_injected_tenant_id_kwarg_is_not_the_subject_of_the_check():
    """``add_tenant_id_to_kwargs`` fills ``tenant_id`` with the caller's USER id.

    Reading that value as a workspace is what the guard must not do, so the
    workspace the resolver names is what gets checked, whatever the kwarg holds.
    """
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=OTHER_TENANT_ID) as resolve,
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False) as can_manage,
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED),
    ):
        assert _run(_invoke(view, tenant_id=USER_ID)) is DENIED
    resolve.assert_called_once()
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    assert record == []


def test_a_norm_member_that_owns_a_personal_workspace_is_not_authorised():
    """The escalation the injected kwarg used to allow.

    A registered user owns a workspace whose id IS its own user id, so checking
    ``can_manage_tenant(user.id, kwargs["tenant_id"])`` answered "yes, you are an
    owner" for a caller that is only a NORMAL member of the workspace the request
    actually acts in. The predicate here models exactly that: managing is true for
    the caller's own workspace and false for the one it is acting in.
    """
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=OTHER_TENANT_ID),
        patch(
            "api.db.services.user_service.UserTenantService.can_manage_tenant",
            side_effect=lambda _user_id, tenant_id: tenant_id == USER_ID,
        ) as can_manage,
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED),
    ):
        assert _run(_invoke(view, tenant_id=USER_ID)) is DENIED
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    assert record == [], "a NORMAL member must not reach an admin-only view"


def test_missing_tenant_id_falls_back_to_the_callers_own_tenant():
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        # The resolver is the subject of its own test
        # (test/unit_test/api/db/services/test_resolve_active_tenant_id.py).
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=USER_ID),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage,
    ):
        _run(_invoke(view))
    can_manage.assert_called_once_with(USER_ID, USER_ID)


# ---------------------------------------------------------------------------
# Composition with add_tenant_id_to_kwargs
# ---------------------------------------------------------------------------


def test_add_tenant_id_to_kwargs_outside_supplies_the_checked_tenant():
    """The documented order: add_tenant_id_to_kwargs wraps this decorator."""
    record = []
    view = add_tenant_id_to_kwargs(require_tenant_admin(_make_view(record)))
    with patch.object(apps_module, "current_user", FakeUser(USER_ID)), patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage:
        assert _run(_invoke(view)) == "VIEW_RAN"
    # The injected value is read by the guard rather than the fallback path.
    can_manage.assert_called_once_with(USER_ID, USER_ID)
    assert record == [{"tenant_id": USER_ID}]


def test_inverted_order_still_denies_a_tenant_the_caller_cannot_manage():
    """Documents the degraded order rather than trusting it silently.

    With this decorator OUTSIDE add_tenant_id_to_kwargs the guard runs first, so
    it cannot read the injected kwarg — but it no longer depends on it either:
    the workspace is resolved from the caller and the header, so the inverted
    order reaches the same decision as the documented one.
    """
    record = []
    view = require_tenant_admin(add_tenant_id_to_kwargs(_make_view(record)))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch.object(apps_module, "requested_tenant_id", lambda: OTHER_TENANT_ID),
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=OTHER_TENANT_ID) as resolve,
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False) as can_manage,
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED),
    ):
        assert _run(_invoke(view, tenant_id=OTHER_TENANT_ID)) is DENIED
    resolve.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    assert record == []


def test_metadata_is_preserved():
    record = []
    view = require_tenant_admin(_make_view(record))
    assert view.__name__ == "view"


# ---------------------------------------------------------------------------
# The workspace a route without an injected tenant_id is checked against
# ---------------------------------------------------------------------------


def test_the_header_names_the_workspace_the_guard_checks():
    """A route with no injected tenant_id is checked against X-Tenant-Id."""
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch.object(apps_module, "requested_tenant_id", lambda: OTHER_TENANT_ID),
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=OTHER_TENANT_ID) as resolve,
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage,
    ):
        assert _run(_invoke(view)) == "VIEW_RAN"
    # The header reaches the resolver, and what it resolves is what is checked.
    resolve.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)


def test_a_member_of_the_named_workspace_is_still_denied_with_code_108():
    """Holding a membership is not holding a role: the denial is a 108.

    This is the outcome a NORMAL member gets from the guarded provider, model
    and Langfuse write routes, whatever workspace it names.
    """
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch.object(apps_module, "requested_tenant_id", lambda: OTHER_TENANT_ID),
        patch("api.db.services.user_service.TenantService.resolve_active_tenant_id", return_value=OTHER_TENANT_ID),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False),
    ):
        code = _run(_invoke_code(view))
    assert code == 108
    assert record == [], "the view must not run when the guard denies"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failed += 1
            print(f"FAIL  {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"=== {len(tests) - failed}/{len(tests)} passed ===")
    sys.exit(1 if failed else 0)
