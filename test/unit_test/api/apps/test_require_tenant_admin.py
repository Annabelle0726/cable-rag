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
    return asyncio.new_event_loop().run_until_complete(coro)


async def _invoke(wrapper, **kwargs):
    """Call a decorated view inside a real Quart application context."""
    async with apps_module.app.app_context():
        return await wrapper(**kwargs)


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
    with patch.object(apps_module, "current_user", FakeUser(USER_ID)), patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage:
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


def test_explicit_tenant_id_is_the_subject_of_the_check():
    """A route carrying someone else's tenant id must be checked against it."""
    record = []
    view = require_tenant_admin(_make_view(record))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False) as can_manage,
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED),
    ):
        assert _run(_invoke(view, tenant_id=OTHER_TENANT_ID)) is DENIED
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    assert record == []


def test_missing_tenant_id_falls_back_to_the_callers_own_tenant():
    record = []
    view = require_tenant_admin(_make_view(record))
    with patch.object(apps_module, "current_user", FakeUser(USER_ID)), patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=True) as can_manage:
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

    With this decorator OUTSIDE add_tenant_id_to_kwargs, the guard reads the
    kwargs it was handed. A tenant id supplied by the caller is still checked,
    so the inverted order stays safe; the fallback only hides the injected
    value, it does not skip the check.
    """
    record = []
    view = require_tenant_admin(add_tenant_id_to_kwargs(_make_view(record)))
    with (
        patch.object(apps_module, "current_user", FakeUser(USER_ID)),
        patch("api.db.services.user_service.UserTenantService.can_manage_tenant", return_value=False) as can_manage,
        patch("api.utils.api_utils.get_error_permission_result", return_value=DENIED),
    ):
        assert _run(_invoke(view, tenant_id=OTHER_TENANT_ID)) is DENIED
    can_manage.assert_called_once_with(USER_ID, OTHER_TENANT_ID)
    assert record == []


def test_metadata_is_preserved():
    record = []
    view = require_tenant_admin(_make_view(record))
    assert view.__name__ == "view"


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
