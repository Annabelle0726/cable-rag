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
"""Guards the RBAC split on the provider / model / langfuse routes.

The failure mode this exists for is a *missing* decorator, not a wrong one: a
route added later without ``@require_tenant_admin`` silently re-opens the curl
bypass that P4-02 closed. Enumerating the endpoints here means adding a route
forces a deliberate decision about which side it belongs on.

The expected sets are declared explicitly rather than derived, so the test fails
when the code and the policy diverge in either direction.

This is a static check: it reads the route tables, so it runs without a live
server and without a database.
"""

import ast
from pathlib import Path

import pytest

RESTFUL = Path(__file__).resolve().parents[4] / "api" / "apps" / "restful_apis"

DECORATOR = "require_tenant_admin"

# Endpoints that mutate credential or tenant-wide model configuration, or that
# spend the administrator's key. Normal members must not reach these.
MUST_BE_ADMIN_ONLY = {
    ("provider_api.py", "/providers", ("PUT",)),
    ("provider_api.py", "/providers/<provider_id_or_name>", ("DELETE",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/connection", ("POST",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances", ("POST",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances", ("DELETE",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>", ("PUT",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models", ("PUT",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models", ("POST",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models", ("DELETE",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models/<path:model_name>", ("PATCH",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models/<path:model_name>", ("POST",)),
    ("models_api.py", "/models/default", ("PATCH",)),
    ("langfuse_api.py", "/langfuse/api-key", ("POST", "PUT")),
    ("langfuse_api.py", "/langfuse/api-key", ("DELETE",)),
    # Read, but returns the Langfuse secret key in cleartext.
    ("langfuse_api.py", "/langfuse/api-key", ("GET",)),
}

# Read paths a normal member needs for the read-only view. Requiring admin here
# would break that view, so the test fails if one gains the decorator.
MUST_STAY_OPEN = {
    ("provider_api.py", "/providers", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/models", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/models/<path:model_name>", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>", ("GET",)),
    ("provider_api.py", "/providers/<provider_id_or_name>/instances/<instance_id_or_name>/models", ("GET",)),
    ("models_api.py", "/models", ("GET",)),
    ("models_api.py", "/models/default", ("GET",)),
}


def _decorator_name(node: ast.AST) -> str | None:
    """Return the bare name of a decorator, whether or not it is called."""
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Name):
        return target.id
    if isinstance(target, ast.Attribute):
        return target.attr
    return None


def _routes(filename: str) -> dict[tuple[str, tuple[str, ...]], set[str]]:
    """Map (route path, methods) -> set of decorator names on that handler."""
    tree = ast.parse((RESTFUL / filename).read_text(encoding="utf-8"))
    found: dict[tuple[str, tuple[str, ...]], set[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = {_decorator_name(d) for d in node.decorator_list}
        for dec in node.decorator_list:
            if _decorator_name(dec) != "route" or not isinstance(dec, ast.Call):
                continue
            path = dec.args[0].value if dec.args else None
            methods: tuple[str, ...] = ("GET",)
            for kw in dec.keywords:
                if kw.arg == "methods":
                    methods = tuple(sorted(elt.value for elt in kw.value.elts))
            assert path is not None, f"{filename}:{node.name} has a route without a path"
            key = (path, methods)
            assert key not in found, f"{filename}: duplicate route {key}"
            found[key] = names
    return found


@pytest.mark.parametrize("filename,path,methods", sorted(MUST_BE_ADMIN_ONLY))
def test_write_endpoints_require_tenant_admin(filename, path, methods):
    routes = _routes(filename)
    names = routes.get((path, methods))
    assert names is not None, f"{filename} {methods} {path} no longer exists -- update this test"
    assert DECORATOR in names, f"{filename} {methods} {path} is missing @{DECORATOR}"


@pytest.mark.parametrize("filename,path,methods", sorted(MUST_STAY_OPEN))
def test_read_endpoints_stay_open(filename, path, methods):
    routes = _routes(filename)
    names = routes.get((path, methods))
    assert names is not None, f"{filename} {methods} {path} no longer exists -- update this test"
    assert DECORATOR not in names, f"{filename} {methods} {path} gained @{DECORATOR}; normal members need this for the read-only view"


def test_every_route_is_classified():
    """No route may sit outside the two sets above."""
    classified = MUST_BE_ADMIN_ONLY | MUST_STAY_OPEN
    for filename in {entry[0] for entry in classified}:
        for path, methods in _routes(filename):
            assert (filename, path, methods) in classified, f"{filename} {methods} {path} is unclassified -- decide whether it is admin-only"
