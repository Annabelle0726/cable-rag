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

"""Wiring tests: ``ChunkService.build_chunks`` binds the standard number to every chunk.

The reported failure was a clean pipeline that produced the right chunks but a wrong
answer: the table slices of a procurement-named standards PDF reached the model
without the standard number they belong to, so the model reported that the knowledge
base held no such standard. These tests pin the chunking-stage fix in the live
(refactored) executor path.
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import xxhash

from rag import nlp
from rag.svr.task_executor_refactor import chunk_service
from rag.svr.task_executor_refactor.chunk_service import ChunkService
from test.unit_test.rag.svr.task_executor_refactor.conftest import create_mock_settings, make_task_context

INCIDENT_DOC_NAME = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2.pdf"
INCIDENT_DOC_TITLE = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2"


class _StubRagTokenizer:
    """Stand-in for the C++ rag_tokenizer binding: deterministic, dictionary-free."""

    class tokenizer:  # noqa: N801 - mirrors the binding's namespace
        @staticmethod
        def set_language(language):
            pass

    @staticmethod
    def tokenize(text):
        return "tk:" + text

    @staticmethod
    def fine_grained_tokenize(text):
        return "fg:" + text


@pytest.fixture(autouse=True)
def stub_rag_tokenizer(monkeypatch):
    """Keep the prefix tokenization hermetic: no C++ tokenizer binding needed."""
    monkeypatch.setattr(nlp, "rag_tokenizer", _StubRagTokenizer)
    return _StubRagTokenizer


async def _build(cks, doc_name):
    """Run the real ChunkService.build_chunks over a canned parser output.

    ``get_parser`` and ``thread_pool_exec`` are patched for the whole call: the real
    parser factory would import every rag.app chunker (and deepdoc with it), which
    this test — about chunk post-processing, not parsing — does not need.
    ``thread_pool_exec`` is patched in chunk_builder, which is the module
    ``run_chunking`` resolves it from.
    """
    ctx = make_task_context(name=doc_name, language="Chinese", doc_id="doc_incident", kb_id="kb_1")
    with (
        patch("rag.svr.task_executor_refactor.chunk_service.get_parser") as mock_get_parser,
        patch("rag.svr.task_executor_refactor.chunk_builder.thread_pool_exec", AsyncMock(return_value=cks)),
        patch("rag.svr.task_executor_refactor.chunk_service.settings", create_mock_settings()),
    ):
        mock_get_parser.return_value = MagicMock()
        service = ChunkService(ctx)
        docs = await service.build_chunks(b"binary")
    return docs, cks


@pytest.mark.asyncio
@pytest.mark.p2
async def test_build_chunks_binds_standard_number_to_every_chunk():
    cks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准\n第2部分：专用技术规范"},
        {"content_with_weight": "表1 技术参数特性表\n型号\t芯数\t标称截面\nYJV\t3\t240", "doc_type_kwd": "table"},
    ]

    docs, cks = await _build(cks, INCIDENT_DOC_NAME)

    assert len(docs) == 2
    for doc in docs:
        assert doc["content_with_weight"].startswith("[标准号: Q/GDW 73289.2-2026 | 文档: " + INCIDENT_DOC_TITLE)
        # Lexical retrieval must be able to match the standard number.
        assert "Q/GDW 73289.2-2026" in doc["content_ltks"]
    assert "章节: 表1 技术参数特性表" in docs[1]["content_with_weight"]
    # The chunk id is the persisted identity: it must cover the persisted body.
    expected_id = xxhash.xxh64((docs[1]["content_with_weight"] + "doc_incident").encode("utf-8", "surrogatepass")).hexdigest()
    assert docs[1]["id"] == expected_id
    # The raw parser output that produced the docs is prefixed too — raw_chunks is
    # what the dry-run comparator inspects.
    assert cks[1]["content_with_weight"].startswith("[标准号: ")


@pytest.mark.asyncio
@pytest.mark.p2
async def test_build_chunks_leaves_documents_without_a_standard_number_alone():
    cks = [
        {"content_with_weight": "产品使用说明书\n本产品适用于室内布线。"},
        {"content_with_weight": "表1 规格表\n型号\t电压\nA\t450/750V"},
    ]

    docs, cks = await _build(cks, "产品说明书.pdf")

    assert [doc["content_with_weight"] for doc in docs] == [ck["content_with_weight"] for ck in cks]


@pytest.mark.asyncio
@pytest.mark.p2
async def test_standard_id_is_bound_to_every_persisted_chunk():
    """Regression: the incident document's standard number reaches every chunk.

    The standard number is NOT in the file name (which is the whole point of the
    reported failure), so it can only come from the cover-page text.
    """
    cks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准\n第2部分：专用技术规范"},
        {"content_with_weight": "表1 技术参数特性表\n型号\t芯数\t标称截面"},
        {"content_with_weight": "表2 电气参数表\n额定电压\t450/750V"},
        {"content_with_weight": "5.1 电缆结构\n导体应符合GB/T 3956-2008的规定。"},
    ]

    docs, _ = await _build(cks, INCIDENT_DOC_NAME)

    assert len(docs) == 4
    for index, doc in enumerate(docs):
        assert "Q/GDW 73289.2-2026" in doc["content_with_weight"], f"chunk[{index}] lost the standard number"
        assert "Q/GDW 73289.2-2026" in doc["content_ltks"], f"chunk[{index}] not lexically searchable by standard number"


@pytest.mark.asyncio
@pytest.mark.p2
async def test_assembly_guard_binds_context_when_the_chunking_stage_is_bypassed(monkeypatch, caplog):
    """The fallback guard covers a chunking path that skipped the stage hook.

    The first ``apply_document_context`` invocation — the one the chunking stage
    makes — is neutered, so only the guard at chunk assembly can bind the context. A
    prefix already present makes the guard a no-op, which the other tests pin; here it
    is the sole line of defence, and it must warn instead of repairing silently.
    """
    from rag.nlp import doc_context

    real = doc_context.apply_document_context
    calls = []

    def bypass_first_call(chunks, doc_name, language="English"):
        calls.append(doc_name)
        if len(calls) == 1:  # the chunking stage's call, as if it had been removed
            return 0
        return real(chunks, doc_name, language=language)

    monkeypatch.setattr(chunk_service, "apply_document_context", bypass_first_call)

    cks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准"},
        {"content_with_weight": "表1 技术参数特性表\n型号\t芯数"},
    ]

    with caplog.at_level(logging.WARNING):
        docs, cks = await _build(cks, INCIDENT_DOC_NAME)

    # The guard ran (stage call + assembly call) and every chunk still carries the
    # standard number, with an id derived from the prefixed body.
    assert len(calls) == 2
    for index, doc in enumerate(docs):
        assert "Q/GDW 73289.2-2026" in doc["content_with_weight"], f"chunk[{index}] lost the standard number"
        expected_id = xxhash.xxh64((doc["content_with_weight"] + "doc_incident").encode("utf-8", "surrogatepass")).hexdigest()
        assert doc["id"] == expected_id
    assert any("not bound by the chunking stage" in record.message for record in caplog.records)
    assert cks[1]["content_with_weight"].startswith("[标准号: ")
