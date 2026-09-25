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
"""The document write paths resolve the workspace instead of assuming user.id is one.

`add_tenant_id_to_kwargs` injects the caller's USER id under the legacy name
`tenant_id`, and a user id is a tenant id only for the workspace it owns. These
routes compared that value to the dataset's own `tenant_id`, so for a NORMAL
member — who owns no tenant — the comparison never matched and the request was
refused with code 102 ("you don't own the dataset"); a workspace ADMIN was
refused the same way. The routes now ask `KnowledgebaseService.writable`, which
scopes itself to the workspace owning the dataset, and hand the dataset's own
tenant id to the doc-store helpers (`search.index_name` is keyed by the tenant
owning the dataset, never by the caller).

The tests drive the real handlers with the HTTP/service layer stubbed; no live
database or doc store is involved.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

DATASET_ID = "kb-1"
DOCUMENT_ID = "doc-1"
#: A workspace member: the injected id is a user id, not the workspace's id.
MEMBER = "user-member"
#: A workspace manager (ADMIN): same shape, no tenant of their own either.
ADMIN = "user-admin"
#: The workspace owning the dataset.
WORKSPACE = "ws-owner"


class _PassthroughManager:
    def route(self, *_args, **_kwargs):
        return lambda func: func


class _LenientModule(ModuleType):
    """A stub module that answers any attribute with a no-op placeholder.

    document_api.py's top-level imports only need every name to exist; symbols
    this suite never reaches can safely be no-ops, which keeps the harness from
    rotting each time the module grows an import. Dunders are deliberately not
    answered, so the import machinery still sees a normal module (``__path__``,
    ``__spec__``, ...) instead of a placeholder.
    """

    def __getattr__(self, _name):
        if _name.startswith("__") and _name.endswith("__"):
            raise AttributeError(_name)
        return lambda *_a, **_k: None


def _stub(monkeypatch, name, **attrs):
    """Install `name` as a stub module, keeping its parents importable.

    A stub has to look like a (namespace) package: `from a.b import c` imports
    the intermediate `a.b` first, so a parent without a usable ``__path__``
    makes the import machinery raise `TypeError`. Parents that are missing are
    stubbed too; parents already loaded for real are left alone.
    """
    mod = _LenientModule(name)
    mod.__path__ = []
    for key, value in attrs.items():
        setattr(mod, key, value)
    monkeypatch.setitem(sys.modules, name, mod)

    parts = name.split(".")
    for index in range(1, len(parts)):
        parent = ".".join(parts[:index])
        existing = sys.modules.get(parent)
        if isinstance(existing, _LenientModule):
            existing.__path__ = []
        elif not isinstance(getattr(existing, "__path__", None), (list, tuple)):
            parent_mod = _LenientModule(parent)
            parent_mod.__path__ = []
            monkeypatch.setitem(sys.modules, parent, parent_mod)
    return mod


class _Doc:
    def __init__(self, *, doc_id=DOCUMENT_ID, kb_id=DATASET_ID, parser_id="naive", status="0", chunk_num=0):
        self.id = doc_id
        self.kb_id = kb_id
        self.name = "doc.txt"
        self.parser_id = parser_id
        self.type = "other"
        self.status = status
        self.run = "0"
        self.chunk_num = chunk_num
        self.progress_msg = ""
        self.pipeline_id = None

    def to_dict(self):
        return {"id": self.id, "kb_id": self.kb_id, "name": self.name, "parser_id": self.parser_id, "status": self.status}


class _UpdateDocumentReq:
    """Stand-in for the validated pydantic body: only these fields are read."""

    def __init__(self, **kwargs):
        self.chunk_method = kwargs.get("chunk_method")
        self.parser_config = kwargs.get("parser_config")
        self.pipeline_id = kwargs.get("pipeline_id")
        self.meta_fields = kwargs.get("meta_fields")


class _Recorded:
    """Call log for the stubs a test asserts on."""

    def __init__(self):
        self.writable_calls: list[tuple[str, str]] = []
        self.get_by_id_calls: list[str] = []
        self.query_calls: list[dict] = []
        self.reset_reparse_calls: list[tuple] = []
        self.chunk_method_calls: list[tuple] = []
        self.nav_calls: list[tuple] = []
        self.run_calls: list[tuple] = []
        self.index_exist_calls: list[tuple] = []
        self.index_delete_calls: list[tuple] = []
        self.index_update_calls: list[tuple] = []


def _load_document_api(monkeypatch, *, payload, writable=True, index_exists=True, doc=None):
    """Load document_api.py with the minimum stubs to drive its write routes.

    `writable` is what the dataset write gate answers; the recorder keeps every
    gate call, the dataset tenant handed to the doc-store helpers, and every
    dataset lookup so a test can prove the caller's user id scoped nothing.
    """
    recorded = _Recorded()
    document = doc or _Doc()

    async def _thread_pool_exec(func, *args, **kwargs):
        return func(*args, **kwargs)

    async def _thread_pool_exec_long_time(func, *args, **kwargs):
        return func(*args, **kwargs)

    docstore = SimpleNamespace(
        index_exist=lambda index, kb_id: recorded.index_exist_calls.append((index, kb_id)) or index_exists,
        delete=lambda condition, index, kb_id: recorded.index_delete_calls.append((condition, index, kb_id)) or True,
        update=lambda condition, body, index, kb_id: recorded.index_update_calls.append((condition, body, index, kb_id)) or True,
        search=lambda *_a, **_k: {},
        get_doc_ids=lambda *_a, **_k: [],
    )
    settings = SimpleNamespace(docStoreConn=docstore, STORAGE_IMPL=SimpleNamespace(get=lambda *_a, **_k: b"", rm=lambda *_a, **_k: None, obj_exist=lambda *_a, **_k: False))

    def _knowledgebase_query(**kwargs):
        recorded.query_calls.append(kwargs)
        # Scope a dataset lookup by `tenant_id` only when it is the dataset's
        # own workspace; anything else is the assumption this suite forbids.
        if kwargs.get("tenant_id") not in (None, WORKSPACE):
            raise AssertionError(f"dataset lookup scoped by a non-tenant id: {kwargs!r}")
        return [SimpleNamespace(id=kwargs.get("id"))]

    kb = SimpleNamespace(id=DATASET_ID, tenant_id=WORKSPACE, name="kb", parser_config={})
    knowledgebase_service = SimpleNamespace(
        writable=lambda kb_id, user_id: recorded.writable_calls.append((kb_id, user_id)) or writable,
        accessible=lambda *_a, **_k: True,
        query=_knowledgebase_query,
        get_by_id=lambda kb_id: recorded.get_by_id_calls.append(kb_id) or (True, kb),
    )
    document_service = SimpleNamespace(
        query=lambda **_kwargs: [document],
        get_by_id=lambda _doc_id: (True, document),
        update_by_id=lambda *_a, **_k: True,
        clear_chunk_num_when_rerun=lambda *_a, **_k: None,
        increment_chunk_num=lambda *_a, **_k: None,
        run=lambda tenant_id, *_a, **_k: recorded.run_calls.append((tenant_id,)),
    )

    _stub(
        monkeypatch,
        "api.apps",
        AUTH_JWT="jwt",
        AUTH_API="api",
        AUTH_BETA="beta",
        current_user=SimpleNamespace(id=MEMBER),
        login_required=lambda func=None, **_kwargs: (lambda f: f) if func is None else func,
    )
    _stub(monkeypatch, "api.constants", FILE_NAME_LEN_LIMIT=255, IMG_BASE64_PREFIX="data:image/")
    _stub(
        monkeypatch,
        "api.apps.services.document_api_service",
        validate_document_update_fields=lambda *_a, **_k: (None, None),
        map_doc_keys=lambda doc: doc.to_dict(),
        map_doc_keys_with_run_status=lambda doc, run_status="0": doc.to_dict(),
        update_document_name_only=lambda *_a, **_k: None,
        update_chunk_method=lambda req, doc, tenant_id: recorded.chunk_method_calls.append((doc.id, tenant_id)) or None,
        update_document_status_only=lambda *_a, **_k: None,
        reset_document_for_reparse=lambda doc, tenant_id, **_kwargs: recorded.reset_reparse_calls.append((doc.id, tenant_id, _kwargs)) or None,
    )
    _stub(
        monkeypatch,
        "api.db",
        VALID_FILE_TYPES=(),
        FileType=SimpleNamespace(VISUAL="visual", FOLDER="folder", VIRTUAL="virtual", OTHER="other", PDF="pdf"),
    )
    _stub(
        monkeypatch,
        "api.db.db_models",
        API4Conversation=SimpleNamespace(),
        Task=SimpleNamespace(doc_id=None),
        DB=SimpleNamespace(connection_context=lambda *_a, **_k: (lambda func: func)),
    )
    _stub(monkeypatch, "api.db.services", duplicate_name=lambda *_a, **_k: "")
    _stub(monkeypatch, "api.db.services.doc_metadata_service", DocMetadataService=SimpleNamespace(update_document_metadata=lambda *_a, **_k: True))
    _stub(monkeypatch, "api.db.services.document_counter_service", release_reparse_counters=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.db.services.document_service", DocumentService=document_service)
    _stub(monkeypatch, "api.db.services.file2document_service", File2DocumentService=SimpleNamespace(get_by_document_id=lambda *_a, **_k: []))
    _stub(monkeypatch, "api.db.services.file_service", FileService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.knowledgebase_service", KnowledgebaseService=knowledgebase_service)
    _stub(monkeypatch, "api.db.services.canvas_service", UserCanvasService=SimpleNamespace())
    _stub(
        monkeypatch,
        "api.db.services.task_service",
        TaskService=SimpleNamespace(filter_delete=lambda *_a, **_k: None, query=lambda **_k: [SimpleNamespace(progress=0.5)]),
        cancel_all_task_of=lambda *_a, **_k: None,
    )
    _stub(monkeypatch, "api.db.services.llm_service", LLMBundle=lambda *_a, **_k: SimpleNamespace())
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        add_tenant_id_to_kwargs=lambda func: func,
        get_request_json=lambda: _Awaitable(payload),
        get_result=lambda code=0, message="success", data=None: {"code": code, "message": message, "data": data},
        get_json_result=lambda code=0, message="success", data=None, **_kwargs: {"code": code, "message": message, "data": data},
        get_data_error_result=lambda message="", code=102: {"code": code, "message": message},
        get_error_data_result=lambda message="", code=102: {"code": code, "message": message},
        get_error_permission_result=lambda message="", code=108: {"code": code, "message": message},
        get_error_argument_result=lambda message="", code=101: {"code": code, "message": message},
        server_error_response=lambda e: {"code": 500, "message": repr(e)},
        check_duplicate_ids=lambda ids, _kind="item": (ids, []),
        strip_graphrag_raptor_config=lambda value: value,
        get_parser_config=lambda *_a, **_k: {},
    )
    _stub(
        monkeypatch,
        "api.utils.pagination_utils",
        DEFAULT_PAGE=1,
        DEFAULT_PAGE_SIZE=30,
        validate_rest_api_ids=lambda *_a, **_k: None,
        validate_rest_api_page=lambda value: int(value),
        validate_rest_api_page_size=lambda value: int(value),
    )
    _stub(
        monkeypatch,
        "api.utils.validation_utils",
        UpdateDocumentReq=_UpdateDocumentReq,
        DeleteDocumentReq=_UpdateDocumentReq,
        format_validation_error_message=lambda e: str(e),
        validate_and_parse_json_request=lambda *_a, **_k: ({}, None),
    )
    _stub(monkeypatch, "common.settings", **vars(settings))
    _stub(
        monkeypatch,
        "common.constants",
        ParserType=SimpleNamespace(NAIVE="naive", QA="qa", TABLE="table"),
        RetCode=SimpleNamespace(SUCCESS=0, ARGUMENT_ERROR=101, DATA_ERROR=102, EXCEPTION_ERROR=500, PERMISSION_ERROR=108),
        TaskStatus=SimpleNamespace(
            UNSTART=SimpleNamespace(value="0"), RUNNING=SimpleNamespace(value="1"), CANCEL=SimpleNamespace(value="2"), DONE=SimpleNamespace(value="3"), FAIL=SimpleNamespace(value="4")
        ),
        SANDBOX_ARTIFACT_BUCKET="artifact",
    )
    _stub(monkeypatch, "common.llm_request_context", normalize_llm_user_id=lambda value: value)
    _stub(monkeypatch, "common.metadata_utils", convert_conditions=lambda value: value, meta_filter=lambda *_a, **_k: [], turn2jsonschema=lambda value: value)
    _stub(monkeypatch, "common.misc_utils", get_uuid=lambda: "uuid-1", thread_pool_exec=_thread_pool_exec, thread_pool_exec_long_time=_thread_pool_exec_long_time)
    _stub(monkeypatch, "common.ssrf_guard", assert_url_is_safe=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.utils.file_utils", filename_type=lambda *_a, **_k: None, thumbnail=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.utils.file_response", apply_preview_file_response_headers=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.utils.office_conversion", convert_legacy_office_to_pdf=lambda *_a, **_k: None, is_legacy_office_document=lambda *_a, **_k: False)
    _stub(monkeypatch, "api.utils.web_utils", CONTENT_TYPE_MAP={}, html2pdf=lambda *_a, **_k: b"", is_valid_url=lambda *_a, **_k: True, apply_safe_file_response_headers=lambda *_a, **_k: None)
    _stub(monkeypatch, "rag.nlp", search=SimpleNamespace(index_name=lambda tenant_id: f"idx-{tenant_id}"))
    _stub(monkeypatch, "rag.advanced_rag.knowlege_compile.dataset_nav", remove_dataset_nav_doc_sync=lambda tenant_id, kb_id, doc_id: recorded.nav_calls.append((tenant_id, kb_id, doc_id)))

    quart_stub = _LenientModule("quart")
    quart_stub.request = SimpleNamespace(args={}, headers={}, method="POST")
    monkeypatch.setitem(sys.modules, "quart", quart_stub)

    # parents[5] = repo root from test/unit_test/api/apps/restful_apis/<file>
    repo_root = Path(__file__).resolve().parents[5]
    module_path = repo_root / "api" / "apps" / "restful_apis" / "document_api.py"
    spec = importlib.util.spec_from_file_location("test_document_workspace_scope_module", module_path)
    module = importlib.util.module_from_spec(spec)
    module.manager = _PassthroughManager()
    monkeypatch.setitem(sys.modules, "test_document_workspace_scope_module", module)
    spec.loader.exec_module(module)

    # Pin the globals the handlers resolve at call time: a full environment may
    # have the real modules loaded already, which would bypass the stubs.
    module.settings = sys.modules["common.settings"]
    module.KnowledgebaseService = knowledgebase_service
    module.DocumentService = document_service
    module.TaskService = sys.modules["api.db.services.task_service"].TaskService
    module.cancel_all_task_of = sys.modules["api.db.services.task_service"].cancel_all_task_of
    module.release_reparse_counters = sys.modules["api.db.services.document_counter_service"].release_reparse_counters
    module.Task = sys.modules["api.db.db_models"].Task
    module.search = sys.modules["rag.nlp"].search
    module.thread_pool_exec = _thread_pool_exec
    api_utils = sys.modules["api.utils.api_utils"]
    module.get_result = api_utils.get_result
    module.get_error_data_result = api_utils.get_error_data_result
    module.get_error_permission_result = api_utils.get_error_permission_result
    module.get_error_argument_result = api_utils.get_error_argument_result
    module.server_error_response = api_utils.server_error_response
    module.check_duplicate_ids = api_utils.check_duplicate_ids
    return module, recorded


class _Awaitable:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.p1
class TestUpdateDocumentWorkspaceScope:
    """PATCH /datasets/<id>/documents/<id> must scope to the dataset's workspace."""

    def test_the_gate_is_asked_about_the_caller_and_the_dataset(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"chunk_method": "manual"})

        res = _run(module.update_document(MEMBER, DATASET_ID, DOCUMENT_ID))

        assert res["code"] == 0, res
        assert recorded.writable_calls == [(DATASET_ID, MEMBER)], recorded.writable_calls
        assert not recorded.query_calls, "the dataset must not be looked up by the caller's user id as a tenant"

    def test_a_workspace_manager_passes_and_the_reparse_gets_the_dataset_tenant(self, monkeypatch):
        """A member of the workspace with write authority is not the tenant owner."""
        module, recorded = _load_document_api(monkeypatch, payload={"chunk_method": "manual"})
        assert ADMIN != WORKSPACE

        res = _run(module.update_document(ADMIN, DATASET_ID, DOCUMENT_ID))

        assert res["code"] == 0, res
        # update_chunk_method is handed the dataset's workspace, not the caller.
        assert recorded.chunk_method_calls == [(DOCUMENT_ID, WORKSPACE)], recorded.chunk_method_calls

    def test_a_pipeline_change_repares_within_the_dataset_tenant(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"pipeline_id": "flow-1"})

        res = _run(module.update_document(MEMBER, DATASET_ID, DOCUMENT_ID))

        assert res["code"] == 0, res
        assert recorded.reset_reparse_calls == [(DOCUMENT_ID, WORKSPACE, {"pipeline_id": "flow-1"})], recorded.reset_reparse_calls

    def test_a_member_without_write_access_is_still_refused(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"chunk_method": "manual"}, writable=False)

        res = _run(module.update_document(MEMBER, DATASET_ID, DOCUMENT_ID))

        assert res["code"] == 102, res
        assert res["message"] == "you don't own the dataset"
        assert recorded.chunk_method_calls == []
        assert recorded.reset_reparse_calls == []


@pytest.mark.p1
class TestBatchUpdateDocumentStatusWorkspaceScope:
    """POST /datasets/<id>/documents/batch-update-status shares the same gate."""

    def test_the_gate_is_asked_about_the_caller_and_the_dataset(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"doc_ids": [DOCUMENT_ID], "status": "1"})

        res = _run(module.batch_update_document_status(MEMBER, DATASET_ID))

        assert res["code"] == 0, res
        assert recorded.writable_calls == [(DATASET_ID, MEMBER)], recorded.writable_calls
        assert not recorded.query_calls, "the dataset must not be looked up by the caller's user id as a tenant"

    def test_the_doc_store_update_uses_the_dataset_tenant(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"doc_ids": [DOCUMENT_ID], "status": "1"}, doc=_Doc(status="0", chunk_num=3))

        res = _run(module.batch_update_document_status(ADMIN, DATASET_ID))

        assert res["code"] == 0, res
        assert recorded.index_update_calls == [({"doc_id": DOCUMENT_ID}, {"available_int": 1}, f"idx-{WORKSPACE}", DATASET_ID)], recorded.index_update_calls


@pytest.mark.p1
class TestDocumentParseWorkspaceScope:
    """The parse routes need the dataset's index, which is keyed by its tenant."""

    def test_parse_documents_cleans_and_queues_in_the_dataset_tenant(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"document_ids": [DOCUMENT_ID]})

        res = _run(module.parse_documents(ADMIN, DATASET_ID))

        assert res["code"] == 0, res
        assert recorded.writable_calls == [(DATASET_ID, ADMIN)], recorded.writable_calls
        assert recorded.nav_calls == [(WORKSPACE, DATASET_ID, DOCUMENT_ID)], recorded.nav_calls
        assert recorded.index_exist_calls == [(f"idx-{WORKSPACE}", DATASET_ID)], recorded.index_exist_calls
        assert recorded.index_delete_calls == [({"doc_id": DOCUMENT_ID}, f"idx-{WORKSPACE}", DATASET_ID)], recorded.index_delete_calls
        assert recorded.run_calls == [(WORKSPACE,)], recorded.run_calls

    def test_stop_parse_documents_cleans_in_the_dataset_tenant(self, monkeypatch):
        module, recorded = _load_document_api(monkeypatch, payload={"document_ids": [DOCUMENT_ID]}, doc=_Doc(status="1"))

        res = _run(module.stop_parse_documents(ADMIN, DATASET_ID))

        assert res["code"] == 0, res
        assert recorded.writable_calls == [(DATASET_ID, ADMIN)], recorded.writable_calls
        assert recorded.index_exist_calls == [(f"idx-{WORKSPACE}", DATASET_ID)], recorded.index_exist_calls
        assert recorded.index_delete_calls == [({"doc_id": DOCUMENT_ID}, f"idx-{WORKSPACE}", DATASET_ID)], recorded.index_delete_calls
