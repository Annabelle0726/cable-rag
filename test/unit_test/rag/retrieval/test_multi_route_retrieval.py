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
"""Module B: hybrid retrieval per route, merged by ``chunk_id``.

The retriever here is a recorder rather than a scorer: what module B is
responsible for is *how many* retrieval calls happen, with *which settings*, and
what the union of their results looks like. Ranking is module C's job.
"""

from copy import deepcopy

import pytest

from rag.retrieval import multi_route

pytestmark = pytest.mark.p1


def _chunk(chunk_id, similarity, doc_id="doc-1", text="正文"):
    return {
        "chunk_id": chunk_id,
        "content_with_weight": text,
        "doc_id": doc_id,
        "docnm_kwd": f"{doc_id}.pdf",
        "kb_id": "kb-1",
        "similarity": similarity,
        "vector_similarity": similarity,
        "term_similarity": similarity,
    }


class _Retriever:
    """Answers per query from a script, recording every call it receives."""

    def __init__(self, by_query=None, delay=0.0, max_concurrency=None):
        self.by_query = by_query or {}
        self.delay = delay
        self.calls = []
        self.in_flight = 0
        self.peak_concurrency = 0
        self.max_concurrency = max_concurrency

    async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, page, page_size, threshold, **kwargs):
        self.calls.append({"question": question, "page": page, "page_size": page_size, "threshold": threshold, "kwargs": kwargs, "embd_mdl": embd_mdl, "tenant_ids": tenant_ids, "kb_ids": kb_ids})
        self.in_flight += 1
        self.peak_concurrency = max(self.peak_concurrency, self.in_flight)
        try:
            if self.max_concurrency is not None:
                assert self.in_flight <= self.max_concurrency
            if self.delay:
                import asyncio

                await asyncio.sleep(self.delay)
            result = self.by_query.get(question)
            if callable(result):
                result = result(threshold)
            return deepcopy(result or {"chunks": [], "doc_aggs": [], "total": 0})
        finally:
            self.in_flight -= 1


async def test_every_route_is_retrieved_hybrid_with_an_expanded_window():
    retriever = _Retriever({query: {"chunks": [_chunk(f"chunk-{i}", 0.9)], "doc_aggs": []} for i, query in enumerate(["原始问题", "子问题一", "子问题二"])})
    await multi_route.multi_route_retrieve(
        retriever=retriever,
        queries=["原始问题", "子问题一", "子问题二"],
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        knn_top_k=1024,
        rerank_candidates_count=30,
    )
    assert [call["question"] for call in retriever.calls] == ["原始问题", "子问题一", "子问题二"]
    for call in retriever.calls:
        # page 1, a 10-15 wide per-route window, the caller's own gate.
        assert (call["page"], call["page_size"]) == (1, multi_route.DEFAULT_ROUTES_TOP_K)
        low, high = multi_route.ROUTES_TOP_K_RECOMMENDED
        assert low <= call["page_size"] <= high
        assert call["threshold"] == 0.55
        assert call["kwargs"]["vector_similarity_weight"] == 0.6
        assert call["kwargs"]["aggs"] is True
        assert call["kwargs"]["knn_top_k"] == 1024
        # The candidate window can never be smaller than the page it must fill.
        assert call["kwargs"]["rerank_candidates_count"] >= call["page_size"]
        # Reranking is one pass over the union, so no route reranks on its own.
        assert "rerank_mdl" not in call["kwargs"]


async def test_recommended_defaults_are_used_when_nothing_is_configured():
    retriever = _Retriever()

    await multi_route.multi_route_retrieve(retriever=retriever, queries=["q"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    call = retriever.calls[0]
    low, high = multi_route.ROUTES_TOP_K_RECOMMENDED
    assert low <= call["page_size"] <= high
    assert call["kwargs"]["vector_similarity_weight"] == multi_route.DEFAULT_VECTOR_SIMILARITY_WEIGHT == 0.6


async def test_configured_weights_and_windows_win():
    retriever = _Retriever()

    await multi_route.multi_route_retrieve(
        retriever=retriever,
        queries=["q"],
        embd_mdl=None,
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        routes_top_k=14,
        similarity_threshold=0.4,
        vector_similarity_weight=0.5,
        rerank_candidates_count=30,
        doc_ids=["doc-9"],
        must_not={"exists": "compile_kwd"},
        allow_dense_fallback=False,
    )

    call = retriever.calls[0]
    assert (call["page_size"], call["threshold"]) == (14, 0.4)
    assert call["kwargs"]["vector_similarity_weight"] == 0.5
    assert call["kwargs"]["rerank_candidates_count"] == 30
    assert call["kwargs"]["doc_ids"] == ["doc-9"]
    assert call["kwargs"]["must_not"] == {"exists": "compile_kwd"}
    assert call["kwargs"]["allow_dense_fallback"] is False


async def test_routes_are_retrieved_concurrently():
    retriever = _Retriever(delay=0.02)

    await multi_route.multi_route_retrieve(retriever=retriever, queries=["a", "b", "c", "d"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    assert retriever.peak_concurrency == 4, "routes must not be retrieved one after another"


async def test_the_same_passage_from_several_routes_is_merged_once():
    shared = _chunk("chunk-shared", 0.61)
    retriever = _Retriever(
        {
            "原始问题": {"chunks": [shared], "doc_aggs": [{"doc_id": "doc-1", "doc_name": "doc-1.pdf", "count": 1}]},
            "子问题一": {"chunks": [dict(shared, similarity=0.72), _chunk("chunk-only-1", 0.9)], "doc_aggs": [{"doc_id": "doc-1", "doc_name": "doc-1.pdf", "count": 2}]},
            "子问题二": {"chunks": [dict(shared, similarity=0.5)], "doc_aggs": [{"doc_id": "doc-1", "doc_name": "doc-1.pdf", "count": 1}]},
        }
    )

    merged = await multi_route.multi_route_retrieve(retriever=retriever, queries=["原始问题", "子问题一", "子问题二"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    by_id = {c["chunk_id"]: c for c in merged["chunks"]}
    assert set(by_id) == {"chunk-shared", "chunk-only-1"}
    assert merged["total"] == 2
    shared_out = by_id["chunk-shared"]
    assert shared_out["route_hits"] == 3
    assert shared_out["retrieval_routes"] == ["原始问题", "子问题一", "子问题二"]
    assert shared_out["similarity"] == pytest.approx(0.72), "a passage keeps the best score it earned on any route"
    # Document counts describe the merged pool, not whichever route ran first.
    assert merged["doc_aggs"] == [{"doc_id": "doc-1", "doc_name": "doc-1.pdf", "count": 4}]
    assert [c["chunk_id"] for c in merged["chunks"]] == ["chunk-only-1", "chunk-shared"]


async def test_a_failing_route_does_not_sink_the_others():
    class _Flaky(_Retriever):
        async def retrieval(self, question, *args, **kwargs):
            if question == "坏的子问题":
                raise RuntimeError("doc store down")
            return await super().retrieval(question, *args, **kwargs)

    retriever = _Flaky({"好的子问题": {"chunks": [_chunk("chunk-ok", 0.8)], "doc_aggs": []}})

    merged = await multi_route.multi_route_retrieve(retriever=retriever, queries=["坏的子问题", "好的子问题"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    assert [c["chunk_id"] for c in merged["chunks"]] == ["chunk-ok"]


async def test_an_empty_route_is_retried_at_the_recall_floor():
    """A gate sitting above the whole pool is a mis-set threshold, not an empty corpus."""
    retriever = _Retriever({"q": lambda threshold: {"chunks": [], "doc_aggs": []} if threshold > multi_route.RECALL_FLOOR else {"chunks": [_chunk("rescued", 0.3)], "doc_aggs": []}})

    merged = await multi_route.multi_route_retrieve(retriever=retriever, queries=["q"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"], similarity_threshold=0.55)

    assert [call["threshold"] for call in retriever.calls] == [0.55, multi_route.RECALL_FLOOR]
    assert [c["chunk_id"] for c in merged["chunks"]] == ["rescued"]


async def test_a_threshold_at_or_below_the_floor_is_not_retried():
    retriever = _Retriever()

    await multi_route.multi_route_retrieve(retriever=retriever, queries=["q"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"], similarity_threshold=multi_route.RECALL_FLOOR)

    assert [call["threshold"] for call in retriever.calls] == [multi_route.RECALL_FLOOR]


async def test_no_routes_means_no_retrieval():
    retriever = _Retriever()

    merged = await multi_route.multi_route_retrieve(retriever=retriever, queries=["", "   "], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    assert merged == {"total": 0, "chunks": [], "doc_aggs": []}
    assert retriever.calls == []


async def test_a_repeated_route_is_retrieved_once():
    retriever = _Retriever({"q": {"chunks": [_chunk("c1", 0.9)], "doc_aggs": []}})

    merged = await multi_route.multi_route_retrieve(retriever=retriever, queries=["q", " q ", "q"], embd_mdl=None, tenant_ids=["t-1"], kb_ids=["kb-1"])

    assert [call["question"] for call in retriever.calls] == ["q"]
    assert merged["chunks"][0]["retrieval_routes"] == ["q"]


def test_a_passage_without_an_id_is_keyed_by_its_document_and_text():
    assert multi_route.chunk_key({"doc_id": "d", "content_with_weight": "abc"}) == "d|abc"
    assert multi_route.chunk_key({"chunk_id": "c1", "doc_id": "d"}) == "c1"
