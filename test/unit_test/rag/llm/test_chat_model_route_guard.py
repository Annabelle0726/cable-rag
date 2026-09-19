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

"""The route guard must retrieve before the model is asked.

`decorate_answer` and the citation pool are useless if the turn never
retrieved, and the tool loop used to accept a direct answer at step 1
("Answering directly at step 1 — no tool needed"). These tests pin the guard
into every entry point of the loop: when a caller arms `mandatory_retrieval`,
the composing tool runs and the model is never asked.
"""

import logging
from types import SimpleNamespace

import pytest

from rag.llm import SupportedLiteLLMProvider, chat_model
from rag.llm.chat_model import Base, LiteLLMBase
from rag.llm.retrieval_guard import mandatory_retrieval

pytestmark = pytest.mark.p1

QUESTION = "请把 YZ 系列与 YJV 系列的技术参数差异整理成一张对照表"
COMPOSED = "[ID:1] YZ 系列为中型橡套软电缆，YJV 为交联聚乙烯绝缘电力电缆。"


class _RecordingToolSession:
    """Stands in for the bound tool session (``tool_call_async``)."""

    def __init__(self, result=COMPOSED, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def tool_call_async(self, name, arguments, **_kwargs):
        self.calls.append((name, arguments))
        if self.error is not None:
            raise self.error
        return self.result


def _tool_schema(name):
    return {
        "type": "function",
        "function": {"name": name, "parameters": {"type": "object", "properties": {"question": {"type": "string"}}}},
    }


def _make_model(model_cls, *, tools=(), session=None):
    model = model_cls.__new__(model_cls)
    model.model_name = "test-model"
    model.provider = SupportedLiteLLMProvider.OpenAI
    model.api_key = "test-key"
    model.base_url = "https://example.test/v1"
    model.max_retries = 0
    model.max_rounds = 3
    model.timeout = 1
    model.tools = list(tools)
    model.toolcall_session = session
    model.last_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return model


def _chunk(content=""):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content, reasoning_content=None, reasoning=None, tool_calls=None), finish_reason=None)],
        usage=None,
    )


def _stream(chunks):
    async def _iterate():
        for chunk in chunks:
            yield chunk

    return _iterate()


def _model_replies(monkeypatch, calls, content="model answer"):
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        return _stream([_chunk(content=content)])

    monkeypatch.setattr(chat_model.litellm, "acompletion", fake_acompletion)


def _model_is_forbidden(monkeypatch, calls):
    async def fake_acompletion(**kwargs):
        calls.append(kwargs)
        raise AssertionError("the route guard must answer without asking the model")

    monkeypatch.setattr(chat_model.litellm, "acompletion", fake_acompletion)


@pytest.mark.asyncio
@pytest.mark.parametrize("model_cls", [LiteLLMBase, Base])
@pytest.mark.parametrize("streaming", [True, False])
async def test_guarded_turn_retrieves_without_asking_the_model(monkeypatch, caplog, model_cls, streaming):
    calls = []
    _model_is_forbidden(monkeypatch, calls)
    session = _RecordingToolSession()
    model = _make_model(model_cls, tools=[_tool_schema("rag")], session=session)
    model.mandatory_retrieval = mandatory_retrieval(QUESTION)
    history = [{"role": "user", "content": QUESTION}]

    with caplog.at_level(logging.INFO):
        if streaming:
            events = [event async for event in model.async_chat_streamly_with_tools("sys", history, {})]
            assert COMPOSED in events
            assert events[-1] == 0
        else:
            answer, tokens = await model.async_chat_with_tools("sys", history, {})
            assert answer == COMPOSED
            assert tokens == 0

    assert session.calls == [("rag", {"question": QUESTION})]
    assert calls == []
    # The line an operator greps for when asking "did this turn retrieve?".
    assert "Route guard: running rag before the model answers" in caplog.text


@pytest.mark.asyncio
async def test_guard_answers_the_stream_with_the_tool_result(monkeypatch):
    calls = []
    _model_is_forbidden(monkeypatch, calls)
    model = _make_model(LiteLLMBase, tools=[_tool_schema("rag")], session=_RecordingToolSession())
    model.mandatory_retrieval = mandatory_retrieval(QUESTION)

    events = [event async for event in model.async_chat_streamly_with_tools("sys", [{"role": "user", "content": QUESTION}], {})]

    # The composed answer, then the token count the bundle stops the stream on.
    assert events == [COMPOSED, 0]
    assert calls == []


@pytest.mark.asyncio
async def test_unbound_tool_leaves_the_turn_to_the_model(monkeypatch, caplog):
    calls = []
    _model_replies(monkeypatch, calls)
    session = _RecordingToolSession()
    model = _make_model(LiteLLMBase, tools=[_tool_schema("summarize_document")], session=session)
    model.mandatory_retrieval = mandatory_retrieval(QUESTION)

    with caplog.at_level(logging.INFO):
        events = [event async for event in model.async_chat_streamly_with_tools("sys", [{"role": "user", "content": QUESTION}], {})]

    assert "model answer" in events
    assert session.calls == []
    assert len(calls) == 1
    assert "which is not bound" in caplog.text


@pytest.mark.asyncio
async def test_failing_retrieval_leaves_the_turn_to_the_model(monkeypatch):
    calls = []
    _model_replies(monkeypatch, calls)
    session = _RecordingToolSession(error=RuntimeError("knowledge base unavailable"))
    model = _make_model(LiteLLMBase, tools=[_tool_schema("rag")], session=session)
    model.mandatory_retrieval = mandatory_retrieval(QUESTION)

    events = [event async for event in model.async_chat_streamly_with_tools("sys", [{"role": "user", "content": QUESTION}], {})]

    assert "model answer" in events
    assert len(session.calls) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_empty_retrieval_leaves_the_turn_to_the_model(monkeypatch):
    calls = []
    _model_replies(monkeypatch, calls)
    session = _RecordingToolSession(result="")
    model = _make_model(LiteLLMBase, tools=[_tool_schema("rag")], session=session)
    model.mandatory_retrieval = mandatory_retrieval(QUESTION)

    events = [event async for event in model.async_chat_streamly_with_tools("sys", [{"role": "user", "content": QUESTION}], {})]

    assert "model answer" in events
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_chit_chat_turn_is_not_guarded(monkeypatch):
    """The whitelist is what keeps a greeting from paying for a retrieval."""
    calls = []
    _model_replies(monkeypatch, calls, content="你好，请问有什么可以帮您？")
    session = _RecordingToolSession()
    model = _make_model(LiteLLMBase, tools=[_tool_schema("rag")], session=session)
    model.mandatory_retrieval = mandatory_retrieval("你好")

    events = [event async for event in model.async_chat_streamly_with_tools("sys", [{"role": "user", "content": "你好"}], {})]

    assert model.mandatory_retrieval is None
    assert "你好，请问有什么可以帮您？" in events
    assert session.calls == []
    assert len(calls) == 1
