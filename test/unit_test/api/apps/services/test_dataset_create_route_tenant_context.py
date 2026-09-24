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
"""The dataset-create path's tenant context, for a NORMAL member.

`@add_tenant_id_to_kwargs` gives the route the caller's *user id* under the
legacy name `tenant_id` (see `api/utils/api_utils.py`), and a NORMAL member owns
no tenant of its own. Passing that id straight into the create path therefore
looked up a tenant that does not exist, and the `(False, Response)` it answered
made the route's `get_error_data_result` fail with
`code=101 "Unable to serialize unknown type: ... Response"`.

Two things are pinned here. The workspace is resolved from the caller with the
`X-Tenant-Id` contract (`TenantService.resolve_active_tenant_id`), and the author
is recorded as the caller -- not as the workspace -- because a `permission='me'`
dataset is readable and writable by its creator and the workspace's managers
alone, so attributing one to the workspace would hide it from the member that
just created it.

The route is loaded with a stubbed DB layer, so no MySQL is needed.
"""

import functools
import importlib.util
import sys
from enum import IntEnum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = [
    pytest.mark.p2,
    # `filterwarnings = error` turns pytest's unraisable-exception warning into a
    # failure, and the sqlite connections / event loops other suites leak are then
    # attributed to whichever test runs next. Nothing here leaks one.
    pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning"),
]

MEMBER_USER_ID = "member-user"
JOINED_WORKSPACE = "workspace-tenant"
REQUESTED_WORKSPACE = "workspace-requested"
OTHER_WORKSPACE = "workspace-other"

REPO_ROOT = Path(__file__).resolve().parents[5]


class _StubModelTypeBinary(IntEnum):
    CHAT = 1
    EMBEDDING = 2
    ASR = 4
    VISION = 8
    RERANK = 16
    TTS = 32
    OCR = 64


class _PermissionDeniedMessage(str):
    """The real denial message carries the code its caller has to report."""

    code = 108


class _DummyManager:
    """Stand-in for the blueprint: `@manager.route(...)` becomes a no-op."""

    def route(self, *_args, **_kwargs):
        def decorator(func):
            return func

        return decorator


def _stub(monkeypatch, name, **attrs):
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, name, mod)
    if "." in name:
        parent_name, _, child_name = name.rpartition(".")
        parent_mod = sys.modules.get(parent_name)
        if parent_mod is not None:
            monkeypatch.setattr(parent_mod, child_name, mod, raising=False)
    return mod


def _load_create_paths(monkeypatch, *, resolve_active_tenant_id, requested_tenant_id=None, create_with_name=None):
    """Load `dataset_api.create` and the real `dataset_api_service` behind it.

    Both are loaded with the database layer stubbed out, and the route's own
    `dataset_api_service` name is bound to that fresh service instance, so the
    two always agree. Returns the route module plus the mocks the create path
    talks to.
    """
    if create_with_name is None:
        create_with_name = MagicMock(
            side_effect=lambda *, name, tenant_id, parser_id=None, created_by=None, **kwargs: (
                True,
                {"id": "kb-1", "name": name, "tenant_id": tenant_id, "created_by": created_by, "parser_id": parser_id, **kwargs},
            )
        )

    tenant_get_by_id = MagicMock(return_value=(True, SimpleNamespace(embd_id="embd-model")))
    verify_embedding_availability = MagicMock(return_value=(True, None))
    resolve_active_tenant_id = MagicMock(side_effect=resolve_active_tenant_id)

    _stub(
        monkeypatch,
        "api.apps",
        # `__path__` lets `api.apps.services` be imported through this stub.
        __path__=[str(REPO_ROOT / "api" / "apps")],
        current_user=SimpleNamespace(id=MEMBER_USER_ID),
        login_required=lambda func: func,
    )

    def _add_tenant_id_to_kwargs(func):
        """The real decorator injects the caller's user id under `tenant_id`."""

        @functools.wraps(func)
        async def wrapper(**_kwargs):
            return await func(tenant_id=MEMBER_USER_ID)

        return wrapper

    _stub(
        monkeypatch,
        "api.db.services.knowledgebase_service",
        KnowledgebaseService=SimpleNamespace(
            create_with_name=create_with_name,
            save=MagicMock(return_value=True),
            get_by_id=MagicMock(return_value=(True, SimpleNamespace(to_dict=lambda: {"id": "kb-1", "name": "kb"}))),
        ),
        validate_dataset_embedding_models=lambda kbs: None,
    )
    _stub(
        monkeypatch,
        "api.db.services.user_service",
        TenantService=SimpleNamespace(
            get_by_id=tenant_get_by_id,
            resolve_active_tenant_id=resolve_active_tenant_id,
        ),
        UserService=SimpleNamespace(),
        UserTenantService=SimpleNamespace(),
    )
    _stub(monkeypatch, "api.db.services.document_service", DocumentService=SimpleNamespace(), queue_raptor_o_graphrag_tasks=MagicMock())
    _stub(monkeypatch, "api.db.services.file2document_service", File2DocumentService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.file_service", FileService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.connector_service", Connector2KbService=SimpleNamespace(), SyncLogsService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.task_service", TaskService=SimpleNamespace(), GRAPH_RAPTOR_FAKE_DOC_ID="fake-doc")
    _stub(monkeypatch, "api.db.services.tenant_model_service", TenantModelService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.tenant_llm_service", TenantLLMService=SimpleNamespace())
    _stub(
        monkeypatch,
        "api.db.joint_services.tenant_model_service",
        get_composite_model_name_by_ids=MagicMock(),
        get_model_config_from_provider_instance=MagicMock(),
        resolve_model_config=MagicMock(),
        resolve_model_id=MagicMock(),
    )
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        PermissionDeniedMessage=_PermissionDeniedMessage,
        add_tenant_id_to_kwargs=_add_tenant_id_to_kwargs,
        deep_merge=MagicMock(),
        get_error_argument_result=lambda message="": {"code": 101, "message": message, "data": None},
        get_error_data_result=_get_error_data_result,
        get_error_permission_result=lambda message="": {"code": 108, "message": message, "data": None},
        get_json_result=lambda *, data=None, message="", code=0, total=None: {"code": code, "message": message, "data": data},
        get_parser_config=MagicMock(),
        get_result=lambda *, data=None, message="", code=0, total=None: {"code": code, "message": message, "data": data},
        remap_dictionary_keys=lambda source_data, key_aliases=None: dict(source_data),
        requested_tenant_id=lambda: requested_tenant_id,
        verify_embedding_availability=verify_embedding_availability,
    )
    _stub(
        monkeypatch,
        "api.utils.pagination_utils",
        DEFAULT_PAGE=1,
        DEFAULT_PAGE_SIZE=30,
        validate_rest_api_ids=lambda ids, field: None,
        validate_rest_api_page=lambda page: page,
        validate_rest_api_page_size=lambda size: size,
    )
    _stub(
        monkeypatch,
        "api.utils.validation_utils",
        CreateDatasetReq=object,
        DeleteDatasetReq=object,
        ListDatasetReq=object,
        UpdateDatasetReq=object,
        validate_and_parse_json_request=_parse_json_request,
        validate_and_parse_request_args=lambda *_args, **_kwargs: ({}, None),
    )
    _stub(monkeypatch, "common.settings", docStoreConn=SimpleNamespace())
    _stub(
        monkeypatch,
        "api.db.db_models",
        DB=SimpleNamespace(connection_context=lambda: lambda func: func),
        TenantModel=SimpleNamespace(),
        Connector2Kb=SimpleNamespace(kb_id="kb_id"),
        Department=SimpleNamespace(),
        Document=SimpleNamespace(kb_id="kb_id"),
        File=SimpleNamespace(source_type="source_type", id="id", type="type", name="name"),
        Knowledgebase=SimpleNamespace(),
        KnowledgebaseAuthorization=SimpleNamespace(),
        SyncLogs=SimpleNamespace(kb_id="kb_id", status=SimpleNamespace(in_=lambda _values: None)),
        UserTenant=SimpleNamespace(),
    )
    _stub(
        monkeypatch,
        "common.constants",
        PAGERANK_FLD="pagerank",
        TAG_FLD="tag",
        FileSource=SimpleNamespace(KNOWLEDGEBASE="knowledgebase"),
        PipelineTaskType=SimpleNamespace(
            PARSE="parse",
            DOWNLOAD="download",
            RAPTOR="raptor",
            GRAPH_RAG="graph_rag",
            MINDMAP="mindmap",
            ARTIFACT="artifact",
            SKILL="skill",
        ),
        StatusEnum=SimpleNamespace(),
        LLMType=SimpleNamespace(EMBEDDING="embedding"),
        RetCode=SimpleNamespace(SUCCESS=0, ARGUMENT_ERROR=101, DATA_ERROR=102, PERMISSION_ERROR=108),
        TaskStatus=SimpleNamespace(SCHEDULE="schedule", RUNNING="running", CANCEL="cancel"),
        ModelTypeBinary=_StubModelTypeBinary,
    )
    _stub(monkeypatch, "rag.advanced_rag", __path__=[])
    _stub(monkeypatch, "rag.advanced_rag.knowlege_compile", __path__=[])
    _stub(monkeypatch, "rag.advanced_rag.knowlege_compile.wiki", WIKI_PAGE_COMPILE_KWD="wiki", _chunk_hash=lambda content: "stub-hash")
    _stub(monkeypatch, "rag.nlp.search", index_name=lambda tenant_id: f"idx-{tenant_id}")

    service_mod = _load_module(monkeypatch, "test_create_path_dataset_api_service_module", REPO_ROOT / "api" / "apps" / "services" / "dataset_api_service.py")

    # The route's `from api.apps.services import dataset_api_service` is answered by
    # the stub package, and then re-pointed at the fresh service instance.
    route_module = _load_module(
        monkeypatch,
        "test_create_path_dataset_api_route_module",
        REPO_ROOT / "api" / "apps" / "restful_apis" / "dataset_api.py",
        extra_modules={"api.apps.services": _stub(monkeypatch, "api.apps.services", __path__=[], dataset_api_service=ModuleType("api.apps.services.dataset_api_service"))},
        module_attrs={"manager": _DummyManager()},
    )
    monkeypatch.setattr(route_module, "dataset_api_service", service_mod)

    return route_module, create_with_name, resolve_active_tenant_id, tenant_get_by_id, verify_embedding_availability


def _get_error_data_result(message="Sorry! Data missing!", code=102):
    """Mirror the real helper: a message may carry the code to report."""
    carried_code = getattr(message, "code", None)
    if carried_code is not None:
        code = carried_code
    return {"code": code, "message": message, "data": None}


def _load_module(monkeypatch, module_name, module_path, *, extra_modules=None, module_attrs=None):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    for name, value in (module_attrs or {}).items():
        setattr(module, name, value)
    for name, mod in (extra_modules or {}).items():
        parent_name, _, child_name = name.rpartition(".")
        parent_mod = sys.modules.get(parent_name)
        if parent_mod is not None:
            setattr(parent_mod, child_name, mod)
    spec.loader.exec_module(module)
    return module


async def _parse_json_request(*_args, **_kwargs):
    return {"name": "kb"}, None


def _resolver(workspace):
    """The resolved workspace for the caller, as the real resolver computes it."""

    def _resolve(user_id, requested_tenant_id=None):
        return workspace

    return _resolve


# --------------------------------------------------------------------------- #
# the create route
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_create_route_scopes_a_members_dataset_to_its_workspace(monkeypatch):
    """The caller id is an identity; the dataset belongs to the joined workspace."""
    module, create_with_name, resolve, get_by_id, verify_embedding = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=_resolver(JOINED_WORKSPACE),
        requested_tenant_id=JOINED_WORKSPACE,
    )

    # `add_tenant_id_to_kwargs` supplies the caller's user id, as in production.
    res = await module.create()

    assert res["code"] == 0, res
    assert create_with_name.call_args.kwargs["tenant_id"] == JOINED_WORKSPACE, create_with_name.call_args.kwargs
    assert create_with_name.call_args.kwargs["created_by"] == MEMBER_USER_ID, create_with_name.call_args.kwargs
    assert create_with_name.call_args.kwargs["name"] == "kb", create_with_name.call_args.kwargs
    # The workspace, not the caller, answers the tenant-scoped model lookups.
    assert resolve.call_args_list[0].args == (MEMBER_USER_ID, JOINED_WORKSPACE), resolve.call_args_list
    assert get_by_id.call_args_list[0].args == (JOINED_WORKSPACE,), get_by_id.call_args_list
    assert verify_embedding.call_args_list == [], verify_embedding.call_args_list


@pytest.mark.asyncio
async def test_the_create_route_checks_the_embedding_against_the_workspace(monkeypatch):
    """A member holds no model configuration of its own."""
    module, create_with_name, _resolve, _get_by_id, verify_embedding = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=_resolver(JOINED_WORKSPACE),
        requested_tenant_id=JOINED_WORKSPACE,
        create_with_name=MagicMock(
            side_effect=lambda *, name, tenant_id, parser_id=None, created_by=None, **kwargs: (
                True,
                {"id": "kb-1", "name": name, "tenant_id": tenant_id, "created_by": created_by, "parser_id": parser_id, "embd_id": "embd-chosen", **kwargs},
            )
        ),
    )

    res = await module.create()

    assert res["code"] == 0, res
    assert verify_embedding.call_args_list[0].args == ("embd-chosen", JOINED_WORKSPACE), verify_embedding.call_args_list


@pytest.mark.asyncio
async def test_the_create_route_never_trusts_the_header_itself(monkeypatch):
    """A header naming a workspace the caller holds no membership on is ignored.

    The resolver is the only authority: whatever it returns is the workspace,
    even when the request asked for another one.
    """
    module, create_with_name, resolve, _get_by_id, _verify = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=lambda user_id, requested_tenant_id=None: OTHER_WORKSPACE,
        requested_tenant_id=REQUESTED_WORKSPACE,
    )

    res = await module.create()

    assert res["code"] == 0, res
    assert create_with_name.call_args.kwargs["tenant_id"] == OTHER_WORKSPACE, create_with_name.call_args.kwargs
    assert create_with_name.call_args.kwargs["created_by"] == MEMBER_USER_ID, create_with_name.call_args.kwargs
    # The request was offered to the resolver, never applied by the route.
    assert resolve.call_args_list[0].args == (MEMBER_USER_ID, REQUESTED_WORKSPACE), resolve.call_args_list


@pytest.mark.asyncio
async def test_the_create_route_reports_a_service_failure_as_a_plain_message(monkeypatch):
    """The `code=101` regression: the route must wrap a string, not a Response."""
    module, _create_with_name, _resolve, _get_by_id, _verify = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=_resolver(JOINED_WORKSPACE),
        requested_tenant_id=JOINED_WORKSPACE,
        create_with_name=MagicMock(return_value=(False, "Tenant not found.")),
    )

    res = await module.create()

    assert res["code"] == 102, res
    assert res["message"] == "Tenant not found.", res
    assert isinstance(res["message"], str), res


@pytest.mark.asyncio
async def test_the_create_route_reports_a_denial_as_code_108(monkeypatch):
    module, _create_with_name, _resolve, _get_by_id, _verify = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=_resolver(JOINED_WORKSPACE),
        requested_tenant_id=JOINED_WORKSPACE,
        create_with_name=MagicMock(return_value=(False, _PermissionDeniedMessage("no authorization"))),
    )

    res = await module.create()

    assert res["code"] == 108, res
    assert res["message"] == "no authorization", res


# --------------------------------------------------------------------------- #
# the service behind the route
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_a_two_argument_call_records_the_caller_as_the_author(monkeypatch):
    """Existing 2-arg call sites keep working and stay attributed to the caller."""
    module, create_with_name, resolve, _get_by_id, _verify = _load_create_paths(
        monkeypatch,
        resolve_active_tenant_id=_resolver(JOINED_WORKSPACE),
        requested_tenant_id=JOINED_WORKSPACE,
    )
    service_mod = module.dataset_api_service

    await service_mod.create_dataset(MEMBER_USER_ID, {"name": "kb"})

    assert resolve.call_args_list[0].args == (MEMBER_USER_ID, JOINED_WORKSPACE), resolve.call_args_list
    assert create_with_name.call_args.kwargs["tenant_id"] == JOINED_WORKSPACE, create_with_name.call_args.kwargs
    assert create_with_name.call_args.kwargs["created_by"] == MEMBER_USER_ID, create_with_name.call_args.kwargs
