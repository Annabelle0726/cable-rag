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
"""`retrieval_test` must resolve its models in the dataset's workspace.

`add_tenant_id_to_kwargs` injects the caller's USER id under the legacy name
`tenant_id`, and a user id is a tenant id only for the workspace it owns. With
`meta_data_filter.method` set to `auto`/`semi_auto` and no `chat_id`, the route
handed that user id to `get_tenant_default_model_by_type`/`resolve_model_config`
/`LLMBundle`, which look a Tenant row up by primary key: for a NORMAL member the
lookup raised `LookupError("Tenant not found")` and the blanket handler turned
it into an HTTP 500. The filter's chat model is a workspace asset, so it now
resolves against the workspace owning the searched dataset — the same one the
embedding model already came from.

The tests drive the real handler with the HTTP/service layer stubbed; no live
database, doc store or model provider is involved.
"""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

DATASET_ID = "kb-1"
DOCUMENT_ID = "doc-1"
#: A NORMAL member: the injected id is a user id, not the workspace's id.
MEMBER = "user-member"
#: The workspace owning the dataset.
WORKSPACE = "ws-owner"


class _PassthroughManager:
    def route(self, *_args, **_kwargs):
        return lambda func: func


class _LenientModule(ModuleType):
    """A stub module that answers any attribute with a no-op placeholder.

    chunk_api.py's top-level imports only need every name to exist; symbols this
    suite never reaches can safely be no-ops, which keeps the harness from
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


class _Awaitable:
    def __init__(self, value):
        self._value = value

    def __await__(self):
        async def _co():
            return self._value

        return _co().__await__()


class _FakeRetriever:
    """Records what the handler asked for and returns one chunk."""

    def __init__(self, calls):
        self._calls = calls

    async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, *args, **kwargs):
        self._calls.append({"question": question, "tenant_ids": tenant_ids, "kb_ids": kb_ids, "args": args, "kwargs": kwargs})
        return {
            "total": 1,
            "chunks": [{"chunk_id": "c1", "doc_id": DOCUMENT_ID, "kb_id": DATASET_ID, "content_with_weight": "text", "docnm_kwd": "doc"}],
            "doc_aggs": {},
        }

    def retrieval_by_children(self, chunks, _tenant_ids):
        return chunks


def _load_chunk_api(monkeypatch, *, payload, user_id=MEMBER, workspace=WORKSPACE, known_tenants=(WORKSPACE,), dataset_found=True):
    """Load chunk_api with the minimum stubs to drive `retrieval_test`.

    `user_id` is what the tenant-id decorator injects (the caller's user id);
    `workspace` is the tenant owning the dataset; `known_tenants` is the set the
    model resolvers accept, so a user id that is not a tenant raises the same
    `LookupError("Tenant not found")` the real resolver raises.
    """
    model_lookups: list[tuple[str, str]] = []
    llm_bundles: list[str] = []
    retrieval_calls: list[dict] = []

    def _model_config(tenant_id, requested):
        model_lookups.append((tenant_id, requested))
        if tenant_id not in known_tenants:
            raise LookupError("Tenant not found")
        return {}

    def _llm_bundle(tenant_id, model_config, *args, **kwargs):
        llm_bundles.append(tenant_id)
        return SimpleNamespace()

    kb = SimpleNamespace(tenant_id=workspace, embd_id="embd-1", tenant_embd_id=None)
    knowledgebase_service = SimpleNamespace(
        accessible=lambda kb_id, user_id: True,
        writable=lambda kb_id, user_id: True,
        get_by_ids=lambda kb_ids: [kb],
        get_by_id=lambda kb_id: (dataset_found, kb if dataset_found else None),
        list_documents_by_ids=lambda kb_ids: [DOCUMENT_ID],
    )

    async def _thread_pool_exec(func, *args, **kwargs):
        return func(*args, **kwargs)

    _stub(
        monkeypatch,
        "api.apps",
        current_user=SimpleNamespace(id=user_id),
        login_required=lambda func=None, **_kwargs: (lambda f: f) if func is None else func,
    )
    _stub(monkeypatch, "api.apps.services.structure_graph_common")
    _stub(monkeypatch, "api.db", cable_defaults=SimpleNamespace(search_config_with_defaults=lambda config: config or {}))
    _stub(monkeypatch, "api.db.db_models", Document=SimpleNamespace(id=None, kb_id=None, run=None), Task=SimpleNamespace(doc_id=None))
    _stub(
        monkeypatch,
        "api.db.joint_services.tenant_model_service",
        **{
            "get_tenant_default_model_by_type": lambda tenant_id, model_type: _model_config(tenant_id, f"default:{model_type}"),
            "resolve_model_config": lambda tenant_id, model_type, model_ref: _model_config(tenant_id, str(model_ref)),
            "get_default_rerank_model_config": lambda *_a, **_k: None,
        },
    )
    _stub(
        monkeypatch,
        "api.db.services.doc_metadata_service",
        DocMetadataService=SimpleNamespace(get_flatted_meta_by_kbs=lambda *_a, **_k: [], get_metadata_for_documents=lambda *_a, **_k: {}),
    )
    _stub(monkeypatch, "api.db.services.document_counter_service", release_reparse_counters=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.db.services.document_service", DocumentService=SimpleNamespace(query=lambda **_k: [], get_by_id=lambda *_a, **_k: (False, None), run=lambda *_a, **_k: None))
    _stub(monkeypatch, "api.db.services.knowledgebase_service", KnowledgebaseService=knowledgebase_service, validate_dataset_embedding_models=lambda _kbs: None)
    _stub(monkeypatch, "api.db.services.llm_service", LLMBundle=_llm_bundle)
    _stub(monkeypatch, "api.db.services.search_service", SearchService=SimpleNamespace())
    _stub(monkeypatch, "api.db.services.task_service", TaskService=SimpleNamespace(), cancel_all_task_of=lambda *_a, **_k: None)
    _stub(monkeypatch, "api.db.services.tenant_llm_service", TenantLLMService=SimpleNamespace())
    _stub(monkeypatch, "common.settings", retriever=_FakeRetriever(retrieval_calls), kg_retriever=SimpleNamespace(), docStoreConn=SimpleNamespace(), STORAGE_IMPL=SimpleNamespace())
    _stub(
        monkeypatch,
        "common.constants",
        LLMType=SimpleNamespace(CHAT="chat", EMBEDDING="embedding", RERANK="rerank"),
        ParserType=SimpleNamespace(NAIVE="naive", QA="qa"),
        RetCode=SimpleNamespace(SUCCESS=0, ARGUMENT_ERROR=101, DATA_ERROR=102, EXCEPTION_ERROR=500, PERMISSION_ERROR=108),
        TaskStatus=SimpleNamespace(UNSTART=SimpleNamespace(value="0"), RUNNING=SimpleNamespace(value="1"), CANCEL=SimpleNamespace(value="2"), DONE=SimpleNamespace(value="3")),
    )
    _stub(monkeypatch, "common.doc_store.doc_store_base", OrderByExpr=SimpleNamespace)
    _stub(monkeypatch, "common.llm_request_context", normalize_llm_user_id=lambda value: value, set_llm_request_context=lambda **_k: None, reset_llm_request_context=lambda *_a: None)
    _stub(monkeypatch, "common.metadata_utils", apply_meta_data_filter=None, convert_conditions=lambda value: value, filter_doc_ids_by_metadata=lambda *_a, **_k: [])
    _stub(monkeypatch, "common.misc_utils", thread_pool_exec=_thread_pool_exec)
    _stub(monkeypatch, "common.string_utils", is_content_empty=lambda value: value is None or not str(value).strip(), remove_redundant_spaces=lambda value: " ".join(str(value).split()))
    _stub(monkeypatch, "common.tag_feature_utils", validate_tag_features=lambda value: value)
    _stub(
        monkeypatch,
        "api.utils.api_utils",
        add_tenant_id_to_kwargs=lambda func: func,
        check_duplicate_ids=lambda ids, _kind="item": (ids, []),
        construct_json_result=lambda code=0, message="success", data=None: {"code": code, "message": message, "data": data},
        get_request_json=lambda: _Awaitable(payload),
        get_result=lambda code=0, message="", data=None, total=None: {key: value for key, value in {"code": code, "message": message, "data": data, "total": total}.items() if value is not None},
        get_error_data_result=lambda message="", code=102: {"code": code, "message": message},
        get_error_permission_result=lambda message="", code=108: {"code": code, "message": message},
        server_error_response=lambda e: {"code": 500, "message": repr(e)},
    )
    _stub(
        monkeypatch,
        "api.utils.image_utils",
        IMAGE_UPDATE_MODE_REMOVE="remove",
        IMAGE_UPDATE_MODES=frozenset({"append", "replace", "remove"}),
        remove_chunk_image=lambda *_a, **_k: None,
        store_chunk_image=lambda *_a, **_k: None,
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
        monkeypatch, "api.utils.reference_metadata_utils", resolve_reference_metadata_preferences=lambda req, _config=None: (False, None), enrich_chunks_with_document_metadata=lambda *_a, **_k: None
    )
    _stub(monkeypatch, "rag.app.tag", label_question=lambda *_a, **_k: {})
    _stub(monkeypatch, "rag.nlp", search=SimpleNamespace(index_name=lambda tenant_id: f"idx-{tenant_id}"))
    _stub(monkeypatch, "rag.nlp.search", search=SimpleNamespace(index_name=lambda tenant_id: f"idx-{tenant_id}"))
    _stub(monkeypatch, "rag.prompts.generator", cross_languages=lambda *_a, **_k: "", keyword_extraction=lambda *_a, **_k: "")

    quart_stub = _LenientModule("quart")
    quart_stub.request = SimpleNamespace(args={}, headers={})
    monkeypatch.setitem(sys.modules, "quart", quart_stub)

    # parents[5] = repo root from test/unit_test/api/apps/restful_apis/<file>
    repo_root = Path(__file__).resolve().parents[5]
    module_path = repo_root / "api" / "apps" / "restful_apis" / "chunk_api.py"
    spec = importlib.util.spec_from_file_location("test_retrieval_workspace_scope_module", module_path)
    module = importlib.util.module_from_spec(spec)
    module.manager = _PassthroughManager()
    monkeypatch.setitem(sys.modules, "test_retrieval_workspace_scope_module", module)
    spec.loader.exec_module(module)

    # Pin the globals the handler resolves at call time: a full environment may
    # have the real modules loaded already, which would bypass the stubs.
    module.settings = sys.modules["common.settings"]
    module.KnowledgebaseService = knowledgebase_service
    module.LLMBundle = _llm_bundle
    module.DocMetadataService = sys.modules["api.db.services.doc_metadata_service"].DocMetadataService
    api_utils = sys.modules["api.utils.api_utils"]
    module.get_request_json = api_utils.get_request_json
    module.get_result = api_utils.get_result
    module.get_error_data_result = api_utils.get_error_data_result
    module.get_error_permission_result = api_utils.get_error_permission_result
    module.server_error_response = api_utils.server_error_response
    module.label_question = sys.modules["rag.app.tag"].label_question
    module.search = sys.modules["rag.nlp"].search

    return module, model_lookups, llm_bundles, retrieval_calls


def _run(coro):
    return asyncio.run(coro)


def _payload(**extra):
    base = {"dataset_ids": [DATASET_ID], "question": "what is ragflow", "page": 1, "page_size": 10}
    base.update(extra)
    return base


def _auto_filter(**extra):
    return _payload(meta_data_filter={"method": "auto"}, **extra)


def _stub_apply_meta_data_filter(monkeypatch, module):
    """Stand in for the LLM-backed filter so the test stops at model wiring."""
    applied: dict = {}

    async def _apply(meta_data_filter, *_args, **_kwargs):
        applied.update(meta_data_filter)
        return None

    monkeypatch.setattr(module, "apply_meta_data_filter", _apply)
    return applied


@pytest.mark.p1
class TestRetrievalModelResolutionWorkspaceScope:
    """`meta_data_filter.method=auto` resolves its chat model in the workspace."""

    def test_the_member_user_id_is_not_a_tenant(self, monkeypatch):
        """The mechanism behind the bug: this lookup is what a user id fails."""
        module, _, _, _ = _load_chunk_api(monkeypatch, payload=_auto_filter())

        with pytest.raises(LookupError, match="Tenant not found"):
            module.get_tenant_default_model_by_type(MEMBER, module.LLMType.CHAT)

    def test_auto_filter_without_chat_id_resolves_in_the_dataset_workspace(self, monkeypatch):
        """The member's request must not fail the tenant lookup (pre-fix: 500)."""
        module, model_lookups, llm_bundles, _ = _load_chunk_api(monkeypatch, payload=_auto_filter())
        applied = _stub_apply_meta_data_filter(monkeypatch, module)

        res = _run(module.retrieval_test(MEMBER))

        assert res["code"] == 0, res
        assert applied == {"method": "auto"}
        assert model_lookups[0] == (WORKSPACE, "default:chat"), model_lookups
        assert {tenant for tenant, _ in model_lookups} == {WORKSPACE}, model_lookups
        assert llm_bundles and all(tenant == WORKSPACE for tenant in llm_bundles), llm_bundles
        assert MEMBER not in llm_bundles

    def test_auto_filter_with_a_chat_id_resolves_in_the_dataset_workspace(self, monkeypatch):
        module, model_lookups, _, _ = _load_chunk_api(monkeypatch, payload=_auto_filter(chat_id="model-1"))
        _stub_apply_meta_data_filter(monkeypatch, module)

        res = _run(module.retrieval_test(MEMBER))

        assert res["code"] == 0, res
        assert model_lookups[0] == (WORKSPACE, "model-1"), model_lookups
        assert {tenant for tenant, _ in model_lookups} == {WORKSPACE}, model_lookups

    def test_a_missing_dataset_answers_an_error_instead_of_failing_the_lookup(self, monkeypatch):
        """No owning dataset means no workspace to resolve the model in."""
        module, model_lookups, llm_bundles, _ = _load_chunk_api(monkeypatch, payload=_auto_filter(), dataset_found=False)
        _stub_apply_meta_data_filter(monkeypatch, module)

        res = _run(module.retrieval_test(MEMBER))

        assert res["code"] == 102, res
        assert res["message"] == "Dataset not found!"
        assert model_lookups == []
        assert llm_bundles == []

    def test_the_search_is_scoped_to_the_dataset_workspace(self, monkeypatch):
        module, _, _, retrieval_calls = _load_chunk_api(monkeypatch, payload=_auto_filter(document_ids=[DOCUMENT_ID]))
        _stub_apply_meta_data_filter(monkeypatch, module)

        res = _run(module.retrieval_test(MEMBER))

        assert res["code"] == 0, res
        assert retrieval_calls[0]["tenant_ids"] == [WORKSPACE], retrieval_calls[0]
        assert retrieval_calls[0]["kb_ids"] == [DATASET_ID], retrieval_calls[0]
