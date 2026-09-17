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
"""
Regression tests for rag_agent() forwarding message bookkeeping keys to the LLM.

Stored and client-supplied messages carry keys the chat schema does not define
(`id`, `created_at`, and `conversationId` from the web client). rag_agent() used
to deepcopy the message list wholesale, so providers that validate message
properties strictly, such as Groq, rejected the request.
"""

import asyncio
import sys
import types
import warnings
from copy import deepcopy
from types import SimpleNamespace

import pytest

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)


def _install_cv2_stub_if_unavailable():
    try:
        import cv2  # noqa: F401

        return
    except Exception:
        pass
    stub = types.ModuleType("cv2")
    stub.INTER_LINEAR = 1
    stub.INTER_CUBIC = 2
    stub.BORDER_CONSTANT = 0
    stub.BORDER_REPLICATE = 1
    stub.COLOR_BGR2RGB = 0
    stub.COLOR_BGR2GRAY = 1
    stub.COLOR_GRAY2BGR = 2
    stub.IMREAD_IGNORE_ORIENTATION = 128
    stub.IMREAD_COLOR = 1
    stub.RETR_LIST = 1
    stub.CHAIN_APPROX_SIMPLE = 2

    def _module_getattr(name):
        if name.isupper():
            return 0
        raise RuntimeError(f"cv2.{name} is unavailable in this test environment")

    stub.__getattr__ = _module_getattr
    sys.modules["cv2"] = stub


_install_cv2_stub_if_unavailable()

from api.db.services import dialog_service  # noqa: E402


_DIALOG = SimpleNamespace(
    id="dialog-1",
    tenant_id="tenant-1",
    kb_ids=["kb-1"],
    llm_id="gpt-4o@OpenAI",
    llm_setting={"temperature": 0.1},
    prompt_config={"reasoning": 1},
    meta_data_filter=None,
    similarity_threshold=0.2,
    vector_similarity_weight=0.3,
    top_n=6,
    rerank_candidates_count=64,
    top_k=1024,
)

_KB = SimpleNamespace(id="kb-1", tenant_id="tenant-1")


class _RecordingChatModel:
    """Records the message list rag_agent() hands to the provider."""

    def __init__(self):
        self.is_tools = True
        self.model_config = {"model_type": "chat", "llm_factory": "OpenAI"}
        self.mdl = None
        self.sent_messages = None

    def bind_tools(self, toolcall_session, tools):
        pass

    async def async_chat(self, system_prompt, messages, gen_conf, **_kwargs):
        self.sent_messages = messages
        return "RAGFlow is a RAG engine."


class _StubRAGTools:
    def __init__(self, *_args, **_kwargs):
        self.kbinfos = {"chunks": [], "doc_aggs": []}
        self.tools = []

    def sys_prompt(self):
        return "You are a helpful assistant."


def _run_rag_agent(monkeypatch, messages, rag_tools_cls=_StubRAGTools, chat_mdl=None):
    """Drives the non-streaming agentic path and returns (model, events)."""
    chat_mdl = _RecordingChatModel() if chat_mdl is None else chat_mdl
    monkeypatch.setattr(dialog_service, "get_models", lambda _dialog, **_kw: ([_KB], None, None, chat_mdl, None))
    monkeypatch.setattr(dialog_service, "RAGTools", rag_tools_cls)
    monkeypatch.setattr(dialog_service, "tts", lambda _mdl, _text: None)

    async def _run():
        return [ev async for ev in dialog_service.rag_agent(_DIALOG, messages, False, reasoning="2")]

    events = asyncio.run(_run())
    assert events, "rag_agent must yield an answer event"
    return chat_mdl, events


def _drive_rag_agent(monkeypatch, messages):
    chat_mdl, _events = _run_rag_agent(monkeypatch, messages)
    return chat_mdl


@pytest.mark.p2
def test_rag_agent_falls_back_to_retrieval_when_model_has_no_tools(monkeypatch):
    """Reasoning must not bypass KB retrieval for models without tool support."""

    class _NoToolsChatModel(_RecordingChatModel):
        def __init__(self):
            super().__init__()
            self.is_tools = False

    chat_mdl = _NoToolsChatModel()
    fallback_calls = []

    async def _fallback(_dialog, _messages, stream=True, **_kwargs):
        fallback_calls.append((stream, _kwargs))
        yield {"answer": "retrieved answer", "reference": {"chunks": [{"doc_id": "doc-1"}]}}

    monkeypatch.setattr(dialog_service, "get_models", lambda _dialog, **_kw: ([_KB], None, None, chat_mdl, None))
    monkeypatch.setattr(dialog_service, "async_chat", _fallback)

    async def _run():
        return [
            event
            async for event in dialog_service.rag_agent(
                _DIALOG,
                [{"role": "user", "content": "What is RAGFlow?"}],
                False,
                reasoning="2",
                doc_ids=["doc-1"],
            )
        ]

    events = asyncio.run(_run())

    assert fallback_calls == [(False, {"reasoning": "2", "doc_ids": "doc-1"})]
    assert events[0]["answer"] == "retrieved answer"


@pytest.mark.p2
def test_rag_agent_drops_bookkeeping_keys_before_the_provider_call(monkeypatch):
    """Groq rejects any message property the chat schema does not define."""
    messages = [
        {"role": "assistant", "content": "Hi! How can I help?", "id": "m-1", "created_at": 1755900000.0},
        {"role": "user", "content": "What is RAGFlow?", "id": "m-2", "conversationId": "conv-1", "doc_ids": ["doc-1"]},
    ]

    chat_mdl = _drive_rag_agent(monkeypatch, messages)

    assert chat_mdl.sent_messages == [
        {"role": "assistant", "content": "Hi! How can I help?"},
        {"role": "user", "content": "What is RAGFlow?"},
    ]


@pytest.mark.p2
def test_rag_agent_keeps_tool_call_protocol_fields(monkeypatch):
    """`tool_calls` and `tool_call_id` belong to the chat schema and pair the two messages together."""
    tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "weather", "arguments": "{}"}}]
    messages = [
        {"role": "user", "content": "Get the weather.", "id": "m-1"},
        {"role": "assistant", "content": None, "tool_calls": tool_calls, "id": "m-2"},
        {"role": "tool", "tool_call_id": "call_1", "content": '{"temp_c": 20}', "id": "m-3"},
        {"role": "user", "content": "Should I take a coat?", "id": "m-4"},
    ]

    chat_mdl = _drive_rag_agent(monkeypatch, messages)

    assert chat_mdl.sent_messages[1] == {"role": "assistant", "content": None, "tool_calls": tool_calls}
    assert chat_mdl.sent_messages[2] == {"role": "tool", "tool_call_id": "call_1", "content": '{"temp_c": 20}'}


@pytest.mark.p2
def test_rag_agent_leaves_the_caller_messages_untouched(monkeypatch):
    """chat_api persists the same dicts after the answer, so the keys must survive the call."""
    messages = [{"role": "user", "content": "What is RAGFlow?", "id": "m-1", "conversationId": "conv-1"}]

    _drive_rag_agent(monkeypatch, messages)

    assert messages[0]["id"] == "m-1"
    assert messages[0]["conversationId"] == "conv-1"


@pytest.mark.p2
def test_rag_agent_preserves_multimodal_content_parts(monkeypatch):
    """`/chat/completions` accepts content-part arrays, so content must be passed through as-is."""
    content = [{"type": "text", "text": "Describe this image"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]
    messages = [{"role": "user", "content": content, "id": "m-1"}]

    chat_mdl = _drive_rag_agent(monkeypatch, messages)

    assert chat_mdl.sent_messages[0]["content"] == content


@pytest.mark.p2
def test_render_reasoning_system_prompt_substitutes_date_and_knowledge(monkeypatch):
    """The reasoning path should honor the dialog system prompt like async_chat does.

    {knowledge} is trusted-template content only: mutable runtime data (bound
    dataset names) must NOT be injected into the reasoning system prompt
    through it. When the caller does not supply a value it renders empty —
    the bound dataset names are exposed through the agentic graph's untrusted
    evidence block instead (see rag/advanced_rag/agentic_rag_graph.py).
    """
    dialog = SimpleNamespace(kb_ids=["kb-1"])
    prompt_config = {"system": "Role: pirate. Date: {date}. Context: '{knowledge}'."}
    kwargs = {}
    monkeypatch.setattr(
        dialog_service.KnowledgebaseService,
        "get_by_ids",
        lambda ids: [SimpleNamespace(name="Pirate KB")],
    )

    rendered = dialog_service._render_reasoning_system_prompt(dialog, prompt_config, kwargs)

    assert rendered.startswith("Role: pirate. Date: 2")
    assert "Context: ''." in rendered
    assert "Pirate KB" not in rendered


@pytest.mark.p2
def test_render_reasoning_system_prompt_caller_supplied_knowledge_wins(monkeypatch):
    """A caller-supplied knowledge value must not be overwritten by the default."""
    dialog = SimpleNamespace(kb_ids=["kb-1"])
    prompt_config = {"system": "Context: '{knowledge}'."}
    kwargs = {"knowledge": "caller evidence"}
    monkeypatch.setattr(
        dialog_service.KnowledgebaseService,
        "get_by_ids",
        lambda ids: [SimpleNamespace(name="Pirate KB")],
    )

    rendered = dialog_service._render_reasoning_system_prompt(dialog, prompt_config, kwargs)

    assert rendered == "Context: 'caller evidence'."


@pytest.mark.p2
def test_render_reasoning_system_prompt_empty_knowledge_is_backward_compatible(monkeypatch):
    """A dialog without datasets (or unnamed ones) still renders the template.

    get_by_ids failures are swallowed: names are cosmetic and must never block
    the prompt render.
    """
    dialog = SimpleNamespace(kb_ids=["kb-1"])
    prompt_config = {"system": "Context: '{knowledge}'."}

    def _boom(ids):
        raise RuntimeError("no db in unit test")

    monkeypatch.setattr(dialog_service.KnowledgebaseService, "get_by_ids", _boom)

    rendered = dialog_service._render_reasoning_system_prompt(dialog, prompt_config, {})

    assert rendered == "Context: ''."

    no_kb = dialog_service._render_reasoning_system_prompt(SimpleNamespace(kb_ids=[]), prompt_config, {})
    assert no_kb == "Context: ''."


@pytest.mark.p2
def test_render_reasoning_system_prompt_replaces_optional_missing_parameters():
    """Optional parameters missing from kwargs are blanked out, not left as placeholders."""
    dialog = SimpleNamespace(kb_ids=[])
    prompt_config = {
        "system": "Lang: {language}.",
        "parameters": [{"key": "language", "optional": True}],
    }
    kwargs = {"date": "2026-08-27"}

    rendered = dialog_service._render_reasoning_system_prompt(dialog, prompt_config, kwargs)

    # Missing optional parameters are replaced with a space, matching async_chat.
    assert rendered == "Lang:  ."


_POOL_CHUNKS = [
    {
        "doc_id": "doc-1",
        "docnm_kwd": "柔性拖链技术规格书.pdf",
        "content_with_weight": "护套：PUR，紫色 RAL4001，外径 6.60 mm。",
        "img_id": "kb-1",
        "vector": [0.1, 0.2],
    },
    {
        "doc_id": "doc-1",
        "docnm_kwd": "柔性拖链技术规格书.pdf",
        "content_with_weight": "固定安装：-40 至 +80 ℃。",
        "vector": [0.3, 0.4],
    },
]


class _PoolStubRAGTools(_StubRAGTools):
    """Retrieval returned a pool, whatever the answer ends up citing."""

    def __init__(self, *_args, **_kwargs):
        super().__init__(*_args, **_kwargs)
        self.kbinfos = {
            "chunks": deepcopy(_POOL_CHUNKS),
            "doc_aggs": [{"doc_id": "doc-1", "doc_name": "柔性拖链技术规格书.pdf"}],
        }


class _MarkerZeroChatModel(_RecordingChatModel):
    """Answers with `[ID:0]`, which is not a valid 1-based citation."""

    async def async_chat(self, system_prompt, messages, gen_conf, **_kwargs):
        self.sent_messages = messages
        return "护套为 PUR 紫色 [ID:0]。"


@pytest.mark.p2
def test_rag_agent_returns_the_retrieved_pool_when_the_answer_cites_nothing(monkeypatch):
    """The pool is the client's only source for figures and document names.

    It used to be gated on the citation markers that resolved, so an answer with
    no citation persisted an empty `reference`: the client had no chunk to
    resolve a figure against and no document list to show.
    """
    _chat_mdl, events = _run_rag_agent(
        monkeypatch,
        [{"role": "user", "content": "护套是什么颜色？"}],
        rag_tools_cls=_PoolStubRAGTools,
    )

    final = events[0]
    assert final["answer"]
    chunks = final["reference"]["chunks"]
    assert chunks, "the retrieved pool must survive an answer that cites nothing"
    assert chunks[0]["content_with_weight"].startswith("护套")
    assert final["reference"]["doc_aggs"] == [{"doc_id": "doc-1", "doc_name": "柔性拖链技术规格书.pdf"}]
    # Query-specific vectors must not travel to the client.
    assert "vector" not in chunks[0]


@pytest.mark.p2
def test_rag_agent_returns_the_pool_when_every_citation_marker_is_unusable(monkeypatch):
    """`[ID:0]` resolves to no chunk, which must not empty the pool either."""
    _chat_mdl, events = _run_rag_agent(
        monkeypatch,
        [{"role": "user", "content": "护套是什么颜色？"}],
        rag_tools_cls=_PoolStubRAGTools,
        chat_mdl=_MarkerZeroChatModel(),
    )

    final = events[0]
    assert len(final["reference"]["chunks"]) == len(_POOL_CHUNKS)
    assert final["reference"]["doc_aggs"] == [{"doc_id": "doc-1", "doc_name": "柔性拖链技术规格书.pdf"}]
