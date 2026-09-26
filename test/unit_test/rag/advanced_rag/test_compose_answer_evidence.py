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
"""The composer must write from the evidence it was handed.

A live reasoning turn answered the configured empty response - 暂未在知识库中检索到
相关线缆参数或规范条款 - over a pool it had just announced as eight passages:

    [Composing the answer] Writing the final answer from 8 gathered passage(s).
    [Composing the answer] No supporting evidence was found; returning the
    configured empty response without calling the answer model.

The passages were there. The kill came from ``state["empty_result"]``, a flag
``formalize_question`` seeded as ``True`` BEFORE any retrieval ran and which
nothing ever cleared: ``direct_search`` wrote ``True`` again when it found
nothing and wrote nothing at all when it found something, so the value was only
ever True and the composer OR-ed it into its evidence test. It is deleted; the
verdict on the pool now belongs to the pool (plus an explicit post-retrieval
``abstain``). These cases pin that, and pin that the empty path still works for a
pool that really is empty.
"""

import asyncio
import logging

import pytest

from rag.advanced_rag import agentic_rag_graph as graph
from rag.advanced_rag.harness.orchestrator import direct as direct_module

pytestmark = pytest.mark.p1

_EMPTY_RESPONSE = "暂未在知识库中检索到相关线缆参数或规范条款。"


def _chunk(index):
    return {
        "chunk_id": f"chunk-{index}",
        "doc_id": "doc-standard",
        "docnm_kwd": "通用技术规范.pdf",
        "kb_id": "kb-1",
        "content_with_weight": f"5.3.3 第{index}条：绝缘标称厚度应不小于 3.4mm。",
        "content_ltks": "绝缘标称厚度",
        "vector": [],
        "similarity": 0.62 - index * 0.001,
    }


class _ChatModel:
    max_length = 8192

    def __init__(self):
        self.calls = 0
        self.system = ""
        self.user_content = ""

    async def async_chat_streamly_delta(self, system_prompt, messages, gen_conf, **_kwargs):
        self.calls += 1
        self.system = system_prompt
        self.user_content = "\n".join(str(m.get("content") or "") for m in messages)
        for token in ("ANSWER ", "FROM ", "EVIDENCE"):
            yield token


class _Tools:
    def __init__(self, chunks):
        self.kbinfos = {"chunks": list(chunks), "doc_aggs": []}
        self.empty_response = _EMPTY_RESPONSE
        self.chat_mdl = _ChatModel()
        self.user_defined_prompts = {}
        self.system_prompt = ""
        self._bound_dataset_names = ""


async def _compose(tools, state):
    queue = asyncio.Queue()
    result = await graph._compose_answer_from_evidence(state, tools, queue, {"temperature": 0.3})
    tokens = []
    while not queue.empty():
        tokens.append(queue.get_nowait())
    return result, "".join(tokens)


async def test_eight_gathered_passages_reach_the_answer_model():
    """The reported failure: a non-empty pool must not be answered from the fallback."""
    chunks = [_chunk(i) for i in range(8)]
    tools = _Tools(chunks)
    state = {"question": "标称厚度是多少？", "kbinfos": tools.kbinfos, "empty_result": True}

    result, streamed = await _compose(tools, state)

    assert tools.chat_mdl.calls == 1, "the answer model must be called when the pool holds passages"
    assert streamed == "ANSWER FROM EVIDENCE"
    assert _EMPTY_RESPONSE not in streamed
    assert result == {"final_answer": ""}


async def test_the_prompt_carries_the_passages():
    """The evidence travels in the user turn; the system turn is the contract."""
    chunks = [_chunk(i) for i in range(8)]
    tools = _Tools(chunks)

    await _compose(tools, {"question": "标称厚度是多少？", "kbinfos": tools.kbinfos})

    assert "绝缘标称厚度应不小于 3.4mm" in tools.chat_mdl.user_content
    assert "Evidence:" in tools.chat_mdl.user_content
    assert "标称厚度是多少？" in tools.chat_mdl.user_content


async def test_an_empty_pool_still_returns_the_configured_empty_response(caplog):
    tools = _Tools([])

    with caplog.at_level(logging.INFO):
        result, streamed = await _compose(tools, {"question": "标称厚度是多少？", "kbinfos": tools.kbinfos})

    assert tools.chat_mdl.calls == 0
    assert streamed == _EMPTY_RESPONSE
    assert result == {"final_answer": _EMPTY_RESPONSE}
    assert "retrieval gathered no passage" in caplog.text, "the log must name which condition emptied the answer"


async def test_an_explicit_abstain_verdict_wins_over_a_non_empty_pool(caplog):
    """``abstain`` is the one verdict allowed to refuse a pool that has passages."""
    tools = _Tools([_chunk(0)])

    with caplog.at_level(logging.INFO):
        _, streamed = await _compose(tools, {"question": "q", "kbinfos": tools.kbinfos, "abstain": True})

    assert tools.chat_mdl.calls == 0
    assert streamed == _EMPTY_RESPONSE
    assert "the verdict was to abstain" in caplog.text


async def test_direct_search_does_not_seed_a_pre_retrieval_empty_flag(monkeypatch):
    """What the low-mode node returns is the pool - no flag that can only lie."""
    tools = _Tools([])

    async def _hybrid_search(_tools, **_kwargs):
        return {"chunks": [_chunk(0)], "doc_aggs": []}

    monkeypatch.setattr(direct_module, "hybrid_search", _hybrid_search)

    result = await direct_module.direct_search({"question": "q", "keywords": ""}, tools)

    assert "empty_result" not in result
    assert [c["chunk_id"] for c in result["kbinfos"]["chunks"]] == ["chunk-0"]


async def test_direct_search_reports_an_empty_pool_through_the_pool_itself(monkeypatch, caplog):
    tools = _Tools([])

    async def _hybrid_search(_tools, **_kwargs):
        return {"chunks": [], "doc_aggs": []}

    monkeypatch.setattr(direct_module, "hybrid_search", _hybrid_search)

    with caplog.at_level(logging.INFO):
        result = await direct_module.direct_search({"question": "q", "keywords": ""}, tools)

    assert result == {"kbinfos": {"chunks": [], "doc_aggs": []}}
    assert "Found no matching passages" in caplog.text


def test_the_state_no_longer_declares_a_pre_retrieval_empty_flag():
    """Structural guard: a flag seeded before retrieval can only ever be a lie."""
    assert "empty_result" not in graph.AgenticState.__annotations__
