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
import asyncio
import logging
from typing import Set

from api.apps import current_user, login_required, requested_tenant_id
from api.db import UserTenantRole
from api.db.db_models import UserTenant
from api.db.services.user_service import TenantService, UserService, UserTenantService
from api.utils.api_utils import (
    get_data_error_result,
    get_error_permission_result,
    get_json_result,
    get_request_json,
    server_error_response,
    validate_request,
)
from api.utils.web_utils import send_invite_email
from common import settings
from common.constants import RetCode, StatusEnum
from common.misc_utils import get_uuid
from common.time_utils import delta_seconds

# Keeps strong references to fire-and-forget tasks so they are not GC'd before completion.
_background_tasks: Set[asyncio.Task] = set()

# A tenant owner is reached by creating a tenant, never by promotion, so the
# role endpoint only ever assigns these.
ASSIGNABLE_ROLES = (UserTenantRole.ADMIN, UserTenantRole.NORMAL)


def _require_membership(tenant_id):
    """Returns an error response unless the caller belongs to `tenant_id`."""
    if not UserTenantService.get_role(current_user.id, tenant_id):
        return get_error_permission_result("you are not a member of this workspace")
    return None


def _require_manager(tenant_id):
    """Returns an error response unless the caller may administer `tenant_id`."""
    if not UserTenantService.can_manage_tenant(current_user.id, tenant_id):
        return get_error_permission_result("admin role required for this workspace")
    return None


def _member_list(tenant_id):
    members = UserTenantService.get_by_tenant_id(tenant_id)
    owner_ids = [m["user_id"] for m in members if m["role"] == UserTenantRole.OWNER]
    for member in members:
        member["delta_seconds"] = delta_seconds(str(member["update_date"]))
        member["is_owner"] = member["user_id"] in owner_ids
    return members


@manager.route("/tenants/<tenant_id>/users", methods=["GET"])  # noqa: F821
@login_required
def user_list(tenant_id):
    """The roster of a workspace.

    Readable by every member, including a NORMAL one: the team page shows the
    roster to all and only hides the controls, and the server is what decides
    whether a control would work.
    """
    denied = _require_membership(tenant_id)
    if denied:
        return denied

    try:
        return get_json_result(data=_member_list(tenant_id))
    except Exception as exc:
        return server_error_response(exc)


@manager.route("/tenants/<tenant_id>/users", methods=["POST"])  # noqa: F821
@login_required
@validate_request("email")
async def create(tenant_id):
    """Add an existing account to the workspace with a role.

    The account must already exist (`UserService.query`): inviting an unknown
    address is the registration-invite flow, which is not this endpoint.
    """
    denied = _require_manager(tenant_id)
    if denied:
        return denied

    req = await get_request_json()
    invite_user_email = req["email"]
    role = req.get("role") or UserTenantRole.NORMAL
    if role not in ASSIGNABLE_ROLES:
        return get_data_error_result(message=f"role '{role}' cannot be assigned")

    invite_users = UserService.query(email=invite_user_email)
    if not invite_users:
        return get_data_error_result(message="User not found.")

    user_id_to_invite = invite_users[0].id
    if user_id_to_invite == current_user.id:
        return get_data_error_result(message="You are already in this team.")

    user_tenants = UserTenantService.query(user_id=user_id_to_invite, tenant_id=tenant_id)
    if user_tenants:
        user_tenant_role = user_tenants[0].role
        if user_tenant_role == UserTenantRole.OWNER:
            return get_data_error_result(message=f"{invite_user_email} is the owner of the team.")
        if user_tenant_role == role:
            return get_data_error_result(message=f"{invite_user_email} is already in the team as {user_tenant_role}.")
        # Re-inviting an existing member (including one who never accepted) is a
        # role change, which is what the caller asked for.
        UserTenantService.set_role(user_id_to_invite, tenant_id, role)
    else:
        UserTenantService.save(
            id=get_uuid(),
            user_id=user_id_to_invite,
            tenant_id=tenant_id,
            invited_by=current_user.id,
            role=role,
            status=StatusEnum.VALID.value,
        )

    try:
        user_name = ""
        _, user = UserService.get_by_id(current_user.id)
        if user:
            user_name = user.nickname

        def _on_invite_email_done(done_task: asyncio.Task) -> None:
            _background_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                logging.warning("Invite email task cancelled: tenant_id=%s to=%s", tenant_id, invite_user_email)
            except Exception:
                logging.exception("Invite email task failed: tenant_id=%s to=%s", tenant_id, invite_user_email)

        task = asyncio.create_task(
            send_invite_email(
                to_email=invite_user_email,
                invite_url=settings.MAIL_FRONTEND_URL,
                tenant_id=tenant_id,
                inviter=user_name or current_user.email,
            )
        )
        if isinstance(task, asyncio.Task):
            _background_tasks.add(task)
            task.add_done_callback(_on_invite_email_done)
    except Exception as exc:
        logging.exception(f"Failed to send invite email to {invite_user_email}: {exc}")
        return get_json_result(
            data=False,
            message="Failed to send invite email.",
            code=RetCode.SERVER_ERROR,
        )

    user = invite_users[0].to_dict()
    user = {k: v for k, v in user.items() if k in ["id", "avatar", "email", "nickname"]}
    return get_json_result(data=user)


@manager.route("/tenants/<tenant_id>/users", methods=["DELETE"])  # noqa: F821
@login_required
@validate_request("user_id")
async def rm(tenant_id):
    """Remove a member, or leave the workspace.

    A manager may remove anyone but the owner; anyone may remove themselves
    (`user_id == current_user.id`) except the owner, who cannot leave the
    workspace they own - it would be left without one.
    """
    req = await get_request_json()
    user_id = req["user_id"]

    leaving_self = user_id == current_user.id
    if not leaving_self and not UserTenantService.can_manage_tenant(current_user.id, tenant_id):
        return get_error_permission_result("admin role required for this workspace")

    role = UserTenantService.get_role(user_id, tenant_id)
    if role is None:
        return get_data_error_result(message="This user is not a member of the workspace.")
    if role == UserTenantRole.OWNER:
        return get_data_error_result(message="The owner cannot be removed from the workspace.")

    try:
        UserTenantService.filter_delete([UserTenant.tenant_id == tenant_id, UserTenant.user_id == user_id])
        # Do not leave the caller pointing at a workspace they just left.
        _, user = UserService.get_by_id(user_id)
        if user and user.current_tenant_id == tenant_id:
            UserService.update_by_id(user_id, {"current_tenant_id": None})
        return get_json_result(data=True)
    except Exception as exc:
        return server_error_response(exc)


@manager.route("/tenants/<tenant_id>/users/<user_id>/role", methods=["PUT"])  # noqa: F821
@login_required
@validate_request("role")
async def set_member_role(tenant_id, user_id):
    """Assign ADMIN or NORMAL to a member of the workspace.

    Only the workspace's managers reach this, the owner's role is never
    assignable (an owner is reached by creating a workspace, not by promotion),
    and nobody may change their own role - a manager demoting themselves would
    lock the workspace out of its own administration.
    """
    denied = _require_manager(tenant_id)
    if denied:
        return denied

    req = await get_request_json()
    role = req["role"]
    if role not in ASSIGNABLE_ROLES:
        return get_data_error_result(message=f"role '{role}' cannot be assigned")
    if user_id == current_user.id:
        return get_data_error_result(message="You cannot change your own role.")

    current_role = UserTenantService.get_role(user_id, tenant_id)
    if current_role is None:
        return get_data_error_result(message="This user is not a member of the workspace.")
    if current_role == UserTenantRole.OWNER:
        return get_data_error_result(message="The owner's role cannot be changed.")

    try:
        UserTenantService.set_role(user_id, tenant_id, role)
        return get_json_result(data={"user_id": user_id, "tenant_id": tenant_id, "role": role})
    except Exception as exc:
        return server_error_response(exc)


@manager.route("/tenants", methods=["GET"])  # noqa: F821
@login_required
def tenant_list():
    """Every workspace the caller belongs to, with the active one flagged."""
    try:
        tenants = UserTenantService.get_tenants_by_user_id(current_user.id)
        active_tenant_id = TenantService.resolve_active_tenant_id(current_user.id, requested_tenant_id())
        for tenant in tenants:
            tenant["delta_seconds"] = delta_seconds(str(tenant["update_date"]))
            tenant["is_active"] = tenant["tenant_id"] == active_tenant_id
        return get_json_result(data=tenants)
    except Exception as exc:
        return server_error_response(exc)


@manager.route("/tenants/<tenant_id>", methods=["PATCH"])  # noqa: F821
@login_required
def agree(tenant_id):
    """Accept a pending invitation, and switch to that workspace."""
    try:
        role = UserTenantService.get_role(current_user.id, tenant_id)
        if role != UserTenantRole.INVITE:
            return get_data_error_result(message="There is no invitation for this workspace.")
        UserTenantService.set_role(current_user.id, tenant_id, UserTenantRole.NORMAL)
        TenantService.set_active_tenant_id(current_user.id, tenant_id)
        return get_json_result(data=True)
    except Exception as exc:
        return server_error_response(exc)
