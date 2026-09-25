"""Verify the P3-03 dataset authorization end to end, over HTTP.

Runs inside wenruo-rag-cpu against the live stack. Everything is done on a
throwaway dataset this script creates and removes, so the real fixtures are left
exactly as they were; owner/member tokens are borrowed and restored so no browser
session dies.

What it proves:
  * the listing is masked in SQL, so a dataset the caller may not read is absent
    rather than hidden by the frontend;
  * `custom` reaches the granted department and the granted individual, and
    nothing else;
  * a member who may read -- including one granted `custom` retrieval -- is
    refused every write endpoint with code=108;
  * the authorization API is manager-only and keeps grants inside the workspace;
  * switching away from `custom` clears the subject set;
  * X-Tenant-Id names the workspace for a manager acting through the API.
"""

import sys

sys.path.insert(0, "/ragflow")

import requests  # noqa: E402

from api.db.db_models import (  # noqa: E402
    DB,
    Department,
    Knowledgebase,
    KnowledgebaseAuthorization,
    UserTenant,
)
from api.db.services.user_service import UserService  # noqa: E402
from common.misc_utils import get_uuid  # noqa: E402

BASE = "http://127.0.0.1:9380/api/v1"
MEMBER = "0realannabelle0@gmail.com"
OWNER = "huizhu@arizona.edu"
ADMIN = "admin@ragflow.io"
MEMBER_ID = "94d8fff8b70d11f1b01f970a5de55a5f"
OWNER_ID = "a9e28731ab7011f19b833887d563fb04"
ADMIN_ID = "89a9df92b5bb11f182935728a82b1fe8"
TENANT = OWNER_ID
PERMISSION_CODE = 108

failures = []


class BorrowedToken:
    """A short-lived session token for one account, restored on exit."""

    def __init__(self, email):
        self.user = UserService.query(email=email)[0]
        self.original = self.user.access_token

    def __enter__(self):
        self.user.access_token = get_uuid()
        self.user.save()
        return self.user.get_id()

    def __exit__(self, *_exc):
        self.user.access_token = self.original
        self.user.save()
        return False


def call(method, path, token, body=None, tenant_header=None):
    headers = {"Authorization": token}
    if tenant_header:
        headers["X-Tenant-Id"] = tenant_header
    kwargs = {"headers": headers, "timeout": 60}
    if body is not None:
        kwargs["json"] = body
    resp = requests.request(method, BASE + path, **kwargs)
    try:
        return resp.json()
    except ValueError:
        return {"code": None, "message": resp.text[:120]}


def check(label, condition, detail):
    flag = "OK  " if condition else "FAIL"
    print(f"  {flag} {label}: {detail}")
    if not condition:
        failures.append(f"{label}: {detail}")


def code_of(payload):
    return payload.get("code")


def listed_ids(token, tenant_header=None):
    payload = call("GET", "/datasets", token, tenant_header=tenant_header)
    if code_of(payload) != 0:
        return None, payload
    # The listing answers `data` as the page itself (with `total_datasets` beside
    # it); the nested shape is tolerated so a contract change is visible here.
    data = payload.get("data")
    rows = data if isinstance(data, list) else (data or {}).get("data") or []
    return {row["id"] for row in rows}, payload


def grant_rows(kb_id):
    with DB.connection_context():
        return sorted((row.subject_type, row.subject_id) for row in KnowledgebaseAuthorization.select().where(KnowledgebaseAuthorization.kb_id == kb_id))


def dataset_exists(kb_id):
    with DB.connection_context():
        return Knowledgebase.select().where(Knowledgebase.id == kb_id).count() > 0


def write_attempts(token):
    """The mutating endpoints a member must never get through."""
    return (
        ("PUT /datasets/<id>", "PUT", "/datasets/{kb}", {"name": "renamed-by-e2e"}),
        ("POST /datasets/<id>/documents/parse", "POST", "/datasets/{kb}/documents/parse", {"document_ids": []}),
        ("POST /datasets/<id>/chunks", "POST", "/datasets/{kb}/chunks", {"document_ids": []}),
        ("DELETE /datasets/<id>/documents", "DELETE", "/datasets/{kb}/documents", {"ids": []}),
        ("DELETE /datasets (ids)", "DELETE", "/datasets", {"ids": ["{kb}"], "delete_all": False}),
        (
            "PUT /datasets/<id>/authorization",
            "PUT",
            "/datasets/{kb}/authorization",
            {"permission": "team", "department_ids": [], "user_ids": []},
        ),
    )


def render(value, kb_id):
    """Substitute the throwaway id, in a path or inside a body."""
    if isinstance(value, str):
        return value.replace("{kb}", kb_id)
    if isinstance(value, dict):
        return {key: render(item, kb_id) for key, item in value.items()}
    if isinstance(value, list):
        return [render(item, kb_id) for item in value]
    return value


def main():
    with (
        BorrowedToken(MEMBER) as member,
        BorrowedToken(OWNER) as owner,
        BorrowedToken(ADMIN) as admin,
    ):
        with DB.connection_context():
            original_placement = UserTenant.select(UserTenant.department_id, UserTenant.title).where((UserTenant.user_id == MEMBER_ID) & (UserTenant.tenant_id == TENANT)).first()
            original_department = original_placement.department_id
            original_title = original_placement.title

        print("=== fixture: a department the member is placed in, and one they are not ===")
        member_department = (call("POST", f"/tenants/{TENANT}/departments", owner, {"name": f"p3-03-e2e-member-dept-{get_uuid()[:6]}"}).get("data") or {}).get("id")
        other_department = (call("POST", f"/tenants/{TENANT}/departments", owner, {"name": f"p3-03-e2e-other-dept-{get_uuid()[:6]}"}).get("data") or {}).get("id")
        check("owner creates two departments", bool(member_department) and bool(other_department), f"member={member_department} other={other_department}")
        placed = call("PUT", f"/tenants/{TENANT}/users/{MEMBER_ID}/profile", owner, {"department_id": member_department})
        check("owner places the member in the first one", code_of(placed) == 0, f"code={code_of(placed)} msg={placed.get('message')!r}")

        created = call(
            "POST",
            "/datasets",
            owner,
            {"name": f"p3-03-e2e-{get_uuid()[:8]}", "permission": "team"},
        )
        check("owner creates the throwaway dataset", code_of(created) == 0, f"code={code_of(created)} msg={created.get('message')!r}")
        if code_of(created) != 0:
            return
        kb_id = (created.get("data") or {}).get("id")
        print(f"=== throwaway dataset {kb_id} ===")

        try:
            print("=== the authorization API is manager-only ===")
            payload = call("GET", f"/datasets/{kb_id}/authorization", owner)
            check("owner may read the authorization", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            check(
                "a new dataset starts as team with no subjects",
                (payload.get("data") or {}).get("permission") == "team" and (payload.get("data") or {}).get("department_ids") == [] and (payload.get("data") or {}).get("user_ids") == [],
                f"data={payload.get('data')}",
            )
            for label, payload in (
                ("member may not read it", call("GET", f"/datasets/{kb_id}/authorization", member)),
                ("member may not write it", call("PUT", f"/datasets/{kb_id}/authorization", member, {"permission": "custom", "department_ids": [], "user_ids": []})),
            ):
                check(label, code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== team mode: the workspace member may read, never write ===")
            ids, _ = listed_ids(member)
            check("member's list contains the team dataset", ids is not None and kb_id in ids, f"count={None if ids is None else len(ids)}")
            payload = call("GET", f"/datasets/{kb_id}", member)
            check("member reads the dataset by id", code_of(payload) == 0, f"code={code_of(payload)}")
            for label, method, path, body in write_attempts(member):
                payload = call(method, render(path, kb_id), member, render(body, kb_id))
                check(f"member {label} refused", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== custom mode: the granted department may read, never write ===")
            payload = call(
                "PUT",
                f"/datasets/{kb_id}/authorization",
                owner,
                {"permission": "custom", "department_ids": [member_department], "user_ids": []},
            )
            check("owner grants the member's department", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            check("the grant is stored", grant_rows(kb_id) == [("department", member_department)], f"rows={grant_rows(kb_id)}")
            payload = call("GET", f"/datasets/{kb_id}/authorization", owner)
            check("owner reads the grant back", (payload.get("data") or {}).get("department_ids") == [member_department], f"data={payload.get('data')}")

            ids, _ = listed_ids(member)
            check("granted department sees it in the list", ids is not None and kb_id in ids, f"count={None if ids is None else len(ids)}")
            payload = call("GET", f"/datasets/{kb_id}", member)
            check("granted department reads it by id", code_of(payload) == 0, f"code={code_of(payload)}")
            for label, method, path, body in write_attempts(member):
                payload = call(method, render(path, kb_id), member, render(body, kb_id))
                check(f"granted reader {label} still refused", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== custom mode: a department the member is not in grants nothing ===")
            payload = call(
                "PUT",
                f"/datasets/{kb_id}/authorization",
                owner,
                {"permission": "custom", "department_ids": [other_department], "user_ids": []},
            )
            check("owner grants the other department", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            ids, _ = listed_ids(member)
            check("it is absent from the member's list", ids is not None and kb_id not in ids, f"count={None if ids is None else len(ids)}")
            payload = call("GET", f"/datasets/{kb_id}", member)
            check("and refused by id", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== custom mode: an individual grant reaches exactly that person ===")
            payload = call(
                "PUT",
                f"/datasets/{kb_id}/authorization",
                owner,
                {"permission": "custom", "department_ids": [], "user_ids": [MEMBER_ID]},
            )
            check("owner grants the member individually", code_of(payload) == 0, f"code={code_of(payload)}")
            check("the previous department grant was replaced", grant_rows(kb_id) == [("user", MEMBER_ID)], f"rows={grant_rows(kb_id)}")
            ids, _ = listed_ids(member)
            check("the individual sees it in the list", ids is not None and kb_id in ids, f"count={None if ids is None else len(ids)}")
            for label, method, path, body in write_attempts(member):
                payload = call(method, render(path, kb_id), member, render(body, kb_id))
                check(f"individually granted reader {label} refused", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== the caller outside the workspace is refused ===")
            ids, _ = listed_ids(admin)
            check("outsider's list omits it", ids is not None and kb_id not in ids, f"count={None if ids is None else len(ids)}")
            payload = call("GET", f"/datasets/{kb_id}", admin)
            check("outsider refused by id", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== validation keeps grants inside the workspace ===")
            payload = call(
                "PUT",
                f"/datasets/{kb_id}/authorization",
                owner,
                {"permission": "custom", "department_ids": [], "user_ids": [ADMIN_ID]},
            )
            check("a non-member cannot be granted to", code_of(payload) != 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            check("nothing was stored by the refused request", grant_rows(kb_id) == [("user", MEMBER_ID)], f"rows={grant_rows(kb_id)}")
            payload = call(
                "PUT",
                f"/datasets/{kb_id}/authorization",
                owner,
                {"permission": "custom", "department_ids": ["dept-from-nowhere"], "user_ids": []},
            )
            check("an unknown department cannot be granted to", code_of(payload) != 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            payload = call("PUT", f"/datasets/{kb_id}/authorization", owner, {"permission": "public", "department_ids": [], "user_ids": []})
            check("an unknown mode is refused", code_of(payload) != 0, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== leaving custom clears the subject set ===")
            payload = call("PUT", f"/datasets/{kb_id}/authorization", owner, {"permission": "me", "department_ids": [], "user_ids": []})
            check("owner switches to me", code_of(payload) == 0, f"code={code_of(payload)}")
            check("the subjects are gone", grant_rows(kb_id) == [], f"rows={grant_rows(kb_id)}")
            ids, _ = listed_ids(member)
            check("a private dataset leaves the member's list", ids is not None and kb_id not in ids, f"count={None if ids is None else len(ids)}")
            ids, _ = listed_ids(owner)
            check("the creator still sees it", ids is not None and kb_id in ids, f"count={None if ids is None else len(ids)}")

            print("=== the creator writes freely ===")
            payload = call("PUT", f"/datasets/{kb_id}", owner, {"name": "p3-03-e2e-renamed"})
            check("owner renames it", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")

            print("=== X-Tenant-Id names the workspace for a manager acting through the API ===")
            with DB.connection_context():
                UserTenant.insert(
                    {
                        "id": get_uuid(),
                        "user_id": ADMIN_ID,
                        "tenant_id": TENANT,
                        "role": "admin",
                        "invited_by": OWNER_ID,
                        "status": "1",
                    }
                ).execute()
            try:
                payload = call("GET", f"/datasets/{kb_id}", admin)
                check("without the header the admin's own workspace is used", code_of(payload) == PERMISSION_CODE, f"code={code_of(payload)} msg={payload.get('message')!r}")
                payload = call("GET", f"/datasets/{kb_id}", admin, tenant_header=TENANT)
                check("with X-Tenant-Id the administered workspace is used", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
                payload = call("GET", f"/datasets/{kb_id}/authorization", admin, tenant_header=TENANT)
                check("and the authorization API follows the header", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            finally:
                with DB.connection_context():
                    UserTenant.delete().where((UserTenant.user_id == ADMIN_ID) & (UserTenant.tenant_id == TENANT)).execute()
        finally:
            print("=== cleanup ===")
            call("PUT", f"/datasets/{kb_id}/authorization", owner, {"permission": "team", "department_ids": [], "user_ids": []})
            payload = call("DELETE", "/datasets", owner, {"ids": [kb_id], "delete_all": False})
            check("owner removes the throwaway dataset", code_of(payload) == 0, f"code={code_of(payload)} msg={payload.get('message')!r}")
            check("the dataset row is gone", not dataset_exists(kb_id), f"exists={dataset_exists(kb_id)}")
            with DB.connection_context():
                KnowledgebaseAuthorization.delete().where(KnowledgebaseAuthorization.kb_id == kb_id).execute()
                remaining_admin_rows = UserTenant.select().where((UserTenant.user_id == ADMIN_ID) & (UserTenant.tenant_id == TENANT)).count()
            check("no grant rows remain", grant_rows(kb_id) == [], f"rows={grant_rows(kb_id)}")
            check(
                "the administered workspace membership was removed",
                remaining_admin_rows == 0,
                f"rows={remaining_admin_rows}",
            )

            # The member's own placement is put back, so the suite can be re-run in
            # any order and leaves the fixtures as it found them.
            restored = call(
                "PUT",
                f"/tenants/{TENANT}/users/{MEMBER_ID}/profile",
                owner,
                {"department_id": original_department, "title": original_title},
            )
            check("the member's placement is restored", code_of(restored) == 0, f"code={code_of(restored)} msg={restored.get('message')!r}")
            for department_id in (member_department, other_department):
                removed = call("DELETE", f"/tenants/{TENANT}/departments/{department_id}", owner)
                check(f"the temporary department {department_id} is removed", code_of(removed) == 0, f"code={code_of(removed)} msg={removed.get('message')!r}")
            with DB.connection_context():
                placed_now = UserTenant.select(UserTenant.department_id).where((UserTenant.user_id == MEMBER_ID) & (UserTenant.tenant_id == TENANT)).first().department_id
                # Deleting a department is a soft delete, so the check is on the
                # ones still in use, not on the rows.
                active_departments = {row.id for row in Department.select(Department.id).where((Department.tenant_id == TENANT) & (Department.status == "1"))}
            check("the member is back where they started", placed_now == original_department, f"department_id={placed_now} original={original_department}")
            check(
                "no temporary department is still in use",
                member_department not in active_departments and other_department not in active_departments,
                f"active departments={sorted(active_departments)}",
            )


if __name__ == "__main__":
    main()
    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)
    print("all P3-03 end-to-end checks passed")
