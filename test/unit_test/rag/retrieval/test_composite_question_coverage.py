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
"""End-to-end: a composite question must reach chapter 5 AND chapter 6.

The standards corpus below is the shape of the reported failure. One document
holds 5.3.3 (绝缘标称厚度), 5.4.2 (绝缘电阻) and 6.2 (例行交流电压试验); the
question asks for all three plus three more parameters.

The fake doc store reproduces the mechanism that empties the result rather than
a bare "returns nothing" stub: its score is the query-RECALL RATIO
(``matched terms / query terms``) that ``Qryr.token_similarity`` implements, so a
passage that covers one of six asked-for parameters scores 1/6 and never clears
the assistant's 0.55 gate - and here not even the 0.2 recall floor. That is
exactly why the knowledge base "cannot answer" a question whose chapters are
sitting in it.

The test then asserts the three stages do their job: the atomic sub-queries are
stripped of their chapter references before they are searched, chapter 5's and
chapter 6's passages both reach the final context, and the reranker judges them
against the user's original question.
"""

import numpy as np
import pytest

from rag.retrieval import decomposition, pipeline
from rag.retrieval.multi_route import RECALL_FLOOR

pytestmark = pytest.mark.p1

#: Parameters a standards question can ask for in one breath. Every passage below
#: covers exactly one of them, which is what makes the recall ratio decisive.
_TERMS = ("标称厚度", "绝缘电阻", "交流电压试验", "外护套", "铠装", "燃烧性能")

_QUESTION = "同时对比绝缘标称厚度、绝缘电阻、交流电压试验、外护套材料、铠装类型和燃烧性能的区别？"

_CORPUS = [
    {
        "chunk_id": "ch5-1",
        "doc_id": "doc-standard",
        "docnm_kwd": "Q/GDW 73289.2-2026.pdf",
        "content_with_weight": "5.3.3 普通绝缘和轻型薄绝缘的绝缘标称厚度应不小于 1.2mm。",
    },
    {
        "chunk_id": "ch5-2",
        "doc_id": "doc-standard",
        "docnm_kwd": "Q/GDW 73289.2-2026.pdf",
        "content_with_weight": "5.4.2 例行试验中绝缘电阻应不小于 100MΩ·km。",
    },
    {
        "chunk_id": "ch6-1",
        "doc_id": "doc-standard",
        "docnm_kwd": "Q/GDW 73289.2-2026.pdf",
        "content_with_weight": "6.2 例行交流电压试验：施加 3.5kV 电压 5min 不击穿。",
    },
    {
        "chunk_id": "ch5-9",
        "doc_id": "doc-other",
        "docnm_kwd": "采购技术规范.pdf",
        "content_with_weight": "5.1 外护套应采用阻燃聚氯乙烯材料。",
    },
    {
        "chunk_id": "ch5-10",
        "doc_id": "doc-other",
        "docnm_kwd": "采购技术规范.pdf",
        "content_with_weight": "5.2 铠装类型分为钢带铠装和钢丝铠装。",
    },
    {
        "chunk_id": "ch7-1",
        "doc_id": "doc-other",
        "docnm_kwd": "采购技术规范.pdf",
        "content_with_weight": "7.1 燃烧性能应符合 GB/T 19666 的规定。",
    },
]

#: What the decomposition node returns for this question: atomic, business-only
#: statements - the chapter references the model was told to drop are still on
#: the first and third of them, so the pipeline's own stripping is exercised too.
_SUB_QUERIES = [
    "第5章 5.3.3 绝缘标称厚度是多少",
    "绝缘电阻的要求是多少",
    "第6章 6.2 例行交流电压试验要求是什么",
    "外护套材料的要求是什么",
]


def _terms_in(text):
    return [term for term in _TERMS if term in str(text or "")]


class _DilutingStore:
    """Doc store whose fused score is a query-recall ratio (see the module docstring)."""

    def __init__(self, corpus):
        self.corpus = corpus
        self.questions = []
        self.thresholds = []

    async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, page, page_size, threshold, **kwargs):
        self.questions.append(question)
        self.thresholds.append(threshold)
        query_terms = _terms_in(question)
        scored = []
        for chunk in self.corpus:
            matched = [term for term in query_terms if term in chunk["content_with_weight"]]
            if not query_terms:
                continue
            score = len(matched) / len(query_terms)
            if score < threshold:
                continue
            scored.append(dict(chunk, similarity=score))
        scored.sort(key=lambda chunk: chunk["similarity"], reverse=True)
        page_chunks = scored[:page_size]
        return {
            "total": len(scored),
            "chunks": page_chunks,
            "doc_aggs": [{"doc_id": "doc-standard", "doc_name": "Q/GDW 73289.2-2026.pdf", "count": len(page_chunks)}],
        }


class _Reranker:
    """Scores by the parameter a passage actually carries, and records its query."""

    _SCORES = {"标称厚度": 0.93, "绝缘电阻": 0.88, "交流电压试验": 0.91}

    def __init__(self):
        self.queries = []

    def similarity(self, query, texts):
        self.queries.append(query)
        values = []
        for text in texts:
            values.append(next((score for term, score in self._SCORES.items() if term in text), 0.4))
        return np.asarray(values, dtype=float), 0


@pytest.fixture
def decomposition_node(monkeypatch):
    async def _fake_gen_json(system_prompt, user_prompt, chat_mdl, gen_conf=None, max_retry=2):
        return {"sub_queries": list(_SUB_QUERIES)}

    monkeypatch.setattr(decomposition, "gen_json", _fake_gen_json)


def _ids(chunks):
    return [chunk["chunk_id"] for chunk in chunks]


async def test_the_composite_question_reaches_chapter_5_and_chapter_6(decomposition_node):
    store = _DilutingStore(_CORPUS)
    reranker = _Reranker()

    result = await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        rerank_mdl=reranker,
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        vector_similarity_weight=0.5,
        final_top_n=3,
    )

    kept = _ids(result["chunks"])
    # Chapter 5's thickness clause, chapter 5's insulation-resistance clause and
    # chapter 6's routine AC voltage test are all in the context the model sees.
    assert kept == ["ch5-1", "ch6-1", "ch5-2"], kept
    assert result["total"] >= 3


async def test_the_same_question_answered_nothing_before_the_pipeline():
    """The regression this pipeline exists for, reproduced on the same corpus.

    One call, one query string, the assistant's own 0.55 gate - which is what
    ``async_chat`` did before this change.
    """
    store = _DilutingStore(_CORPUS)

    legacy = await store.retrieval(_QUESTION, object(), ["t-1"], ["kb-1"], 1, 12, 0.55, vector_similarity_weight=0.5)

    assert legacy["chunks"] == []
    assert store.questions == [_QUESTION]


async def test_the_search_statements_carry_no_chapter_references(decomposition_node):
    """A chapter number is a coordinate in the outline, not content to match."""
    store = _DilutingStore(_CORPUS)

    await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    assert _SUB_QUERIES[0] not in store.questions, "the model's chapter reference must not be searched"
    assert _SUB_QUERIES[2] not in store.questions
    assert store.questions[0] == _QUESTION, "the original question is still the first route"
    assert "绝缘标称厚度是多少" in store.questions
    assert "例行交流电压试验要求是什么" in store.questions
    assert not any("第" in question for question in store.questions), store.questions


async def test_every_route_is_gated_at_the_configured_threshold(decomposition_node):
    store = _DilutingStore(_CORPUS)

    await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    assert set(store.thresholds) <= {0.55, RECALL_FLOOR}, store.thresholds


async def test_the_original_route_alone_still_yields_nothing(decomposition_node):
    """Chapter coverage is provably the sub-queries' doing, not the original route's.

    The composite statement scores 1/6 on every passage, so neither the
    configured gate nor the recall floor lets the original route contribute a
    passage to the merged pool.
    """
    store = _DilutingStore(_CORPUS)

    await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    # The original question is route 0 and appears exactly twice: once at the
    # configured threshold and once at the recall floor.
    assert [q for q in store.questions if q == _QUESTION] == [_QUESTION, _QUESTION]
    assert store.thresholds[:2] == [0.55, RECALL_FLOOR]


async def test_the_reranker_judges_against_the_original_question(decomposition_node):
    store = _DilutingStore(_CORPUS)
    reranker = _Reranker()

    await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        rerank_mdl=reranker,
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    assert reranker.queries == [_QUESTION], "one rerank pass, against what the user asked"


async def test_off_topic_chapters_are_dropped_by_the_final_cut(decomposition_node):
    store = _DilutingStore(_CORPUS)
    reranker = _Reranker()

    result = await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        rerank_mdl=reranker,
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    assert not {"ch5-9", "ch5-10", "ch7-1"} & set(_ids(result["chunks"])), "the rerank cut keeps the three asked-for clauses"
    assert all(chunk.get("rerank_score") is not None for chunk in result["chunks"])


def test_the_corpus_holds_the_two_chapters_the_question_asks_about():
    """Guard the fixture itself: the coverage assertion must have something to find."""
    assert "5.3.3" in _CORPUS[0]["content_with_weight"]
    assert "6.2 例行交流电压试验" in _CORPUS[2]["content_with_weight"]
    assert decomposition.looks_composite(_QUESTION)


# ---------------------------------------------------------------------------
# The same question against a corpus that FLOODS one dimension
# ---------------------------------------------------------------------------

#: The live cable corpus, reproduced: twelve near-identical parameter tables of
#: the dimension the question leads with, plus the single clause chapter 6 has.
_FLOOD_CORPUS = [
    {
        "chunk_id": f"ch5-{i}",
        "doc_id": "doc-standard",
        "docnm_kwd": "Q/GDW 73289.2-2026.pdf",
        "content_with_weight": f"表{i} 技术参数特性表：绝缘标称厚度 薄绝缘 2.5mm 普通绝缘 3.4mm。",
    }
    for i in range(1, 7)
] + [
    {
        "chunk_id": "ch6-1",
        "doc_id": "doc-standard",
        "docnm_kwd": "Q/GDW 73289.2-2026.pdf",
        "content_with_weight": "[标准号: Q/GDW 73237.1-2026 | 章节: 6.2.3 交流电压试验] 例行交流电压试验：施加 3.5kV 电压 5min 不击穿。",
    }
]


async def test_a_flood_of_one_dimension_cannot_crowd_out_the_other_chapter(decomposition_node):
    """Measured live, and the reason the cut reserves a slot per route.

    Twelve thickness tables scored 0.596-0.603 against the question and filled
    every one of the twelve context slots; the 6.2.3 交流电压试验 clause the
    corpus holds sat at 0.577 and was dropped before the answer model saw it.
    """
    store = _DilutingStore(_FLOOD_CORPUS)
    reranker = _Reranker()

    result = await pipeline.retrieve_multi_route(
        retriever=store,
        question=_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        rerank_mdl=reranker,
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=3,
    )

    kept = _ids(result["chunks"])
    assert len(kept) == 3
    assert "ch6-1" in kept, f"chapter 6 was crowded out: {kept}"
    # The remaining slots still go by score, so the leading dimension keeps its
    # best passage.
    assert kept[0] == "ch5-1"
