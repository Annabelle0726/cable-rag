#
#  Copyright 2026 The InfiniFlow Authors. All Rights Reserved.
#  Modifications Copyright 2026 线缆工业智搜平台. All Rights Reserved.
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
"""The multi-route retrieval pipeline: decompose, retrieve, rerank.

One entry point wires the three stages together for a chat turn:

1. :mod:`rag.retrieval.decomposition` — a composite question becomes an original
   route plus one atomic route per information need;
2. :mod:`rag.retrieval.multi_route` — every route is retrieved concurrently
   (hybrid, per-route candidate window) and the results are merged by
   ``chunk_id``;
3. :mod:`rag.retrieval.rerank` — the merged pool is scored against the ORIGINAL
   question and cut to the passages the answer model will see.

A question with a single information need does not call the LLM at all: it takes
one route, which is the behaviour this path had before the pipeline existed.
"""

from __future__ import annotations

import logging

from rag.retrieval.decomposition import MAX_SUB_QUERIES, clause_route, decompose_question, looks_composite
from rag.retrieval.multi_route import (
    DEFAULT_ROUTES_TOP_K,
    DEFAULT_VECTOR_SIMILARITY_WEIGHT,
    multi_route_retrieve,
)
from rag.retrieval.rerank import DEFAULT_FINAL_TOP_N, rerank_chunks

_LOG = logging.getLogger(__name__)


def empty_kbinfos() -> dict:
    """A fresh empty result, in the shape every retrieval caller expects."""
    return {"total": 0, "chunks": [], "doc_aggs": []}


async def retrieve_multi_route(
    *,
    retriever,
    question: str,
    tenant_ids,
    kb_ids,
    chat_mdl=None,
    embd_mdl=None,
    rerank_mdl=None,
    similarity_threshold: float = 0.2,
    vector_similarity_weight: float = DEFAULT_VECTOR_SIMILARITY_WEIGHT,
    routes_top_k=DEFAULT_ROUTES_TOP_K,
    final_top_n=DEFAULT_FINAL_TOP_N,
    knn_top_k: int = 1024,
    rerank_candidates_count=None,
    doc_ids=None,
    rank_feature=None,
    must_not=None,
    max_sub_queries: int = MAX_SUB_QUERIES,
    allow_dense_fallback: bool = True,
) -> dict:
    """Retrieve for ``question`` through decomposition + hybrid routes + rerank.

    Two knobs, deliberately separate:

    * ``routes_top_k`` - the recall window of ONE route. Default 12, inside the
      recommended 10-15 band: wide enough that a chapter's answering clause
      survives the fused gate inside its own route, narrow enough that N routes
      stay inside the reranker's window. Callers whose ``top_n`` already means
      "passages this search returns" pass it through (the harness search tools
      do), because a route that cannot fill the page it has to return cannot
      contribute to it.
    * ``final_top_n`` - the passages handed to the answer model. Default 8, in
      the recommended 6-8 band; a configured value wins (the cable assistant
      sets 12 for a measured reason - see ``api/db/cable_defaults.py``).
    """
    question = " ".join(str(question or "").split())
    if not question:
        return empty_kbinfos()

    routes = [question]
    if looks_composite(question):
        routes.extend(await decompose_question(chat_mdl, question, max_sub_queries))
    # A rule-seeking question also gets a route at the normative PROSE tier. It is
    # deterministic on purpose: it must fire on every clause question, including
    # the ones the LLM decomposition failed on or never saw (single-dimension
    # wording), because a bidder fill-in table can win the fused score against it.
    targeted = clause_route(question)
    if targeted:
        routes.append(targeted)
    _LOG.info("[Multi-route] question=%r -> %d route(s): %s", question[:80], len(routes), routes)

    merged = await multi_route_retrieve(
        retriever=retriever,
        queries=routes,
        embd_mdl=embd_mdl,
        tenant_ids=tenant_ids,
        kb_ids=kb_ids,
        routes_top_k=routes_top_k,
        similarity_threshold=similarity_threshold,
        vector_similarity_weight=vector_similarity_weight,
        knn_top_k=knn_top_k,
        rerank_candidates_count=rerank_candidates_count,
        doc_ids=doc_ids,
        rank_feature=rank_feature,
        must_not=must_not,
        allow_dense_fallback=allow_dense_fallback,
    )
    if not merged.get("chunks"):
        return empty_kbinfos()

    chunks = await rerank_chunks(rerank_mdl, merged["chunks"], question, final_top_n)
    return {"total": merged.get("total", len(chunks)), "chunks": chunks, "doc_aggs": merged.get("doc_aggs", [])}
