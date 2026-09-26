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
from typing import Sequence

from rag.retrieval.chunk_profile import document_id, document_key, document_name, resolve_core_documents
from rag.retrieval.decomposition import MAX_SUB_QUERIES, clause_route, decompose_question, looks_composite, seeks_clause
from rag.retrieval.multi_route import (
    DEFAULT_ROUTES_TOP_K,
    DEFAULT_VECTOR_SIMILARITY_WEIGHT,
    RouteResult,
    merge_route_hits,
    multi_route_retrieve,
)
from rag.retrieval.rerank import DEFAULT_FINAL_TOP_N, rerank_chunks

_LOG = logging.getLogger(__name__)

#: How many routes the document-scoped follow-up may run. Each one is a retrieval
#: round trip, and the atomic sub-queries are the ones that find a standard's
#: individual clauses, so they are served first.
MAX_CORE_DOCUMENT_ROUTES = 3


def empty_kbinfos() -> dict:
    """A fresh empty result, in the shape every retrieval caller expects."""
    return {"total": 0, "chunks": [], "doc_aggs": []}


def core_document_followup(chunks, question: str, preferred_routes: Sequence[str] = ()) -> tuple[str, str, list[str]] | None:
    """``(doc_id, doc_name, queries)`` for a standard losing its own question.

    The measured gap this exists for: a three-parameter question whose pool held
    two passages from 《Q/GDW 73237.1 通用技术规范》 and seven from an auxiliary
    working document. The standard's 6.2.2 (绝缘电阻 ≥1500/1000 MΩ·km) is in the
    corpus, and Test 2 proved a question that NAMES the standard reaches it - but
    a composite question's fused score ranks the standard's clauses below whatever
    else matches the same words, so those clauses never enter any route's window.
    No cut-stage policy can recover a passage that was never recalled; the only
    lever left is to search the standard ITSELF, which is what this returns the
    material for: a retrieval scoped to the standard's ``doc_ids``.

    Fires only on the measured symptom, so an ordinary turn pays nothing:

    * a standard must be identifiable (:func:`resolve_core_documents`);
    * the question must be about several parameters or about a rule - the shapes
      whose clause can be buried by an auxiliary document;
    * a non-core document must have contributed MORE passages than every core
      document together. A standard that already leads its own question is left
      alone, because nothing says a passage is missing.

    ``preferred_routes`` are searched first inside the standard (the atomic
    sub-queries and the prose-tier route), then the question itself.
    """
    core = resolve_core_documents(chunks, question)
    if not core:
        return None
    if not (looks_composite(question) or seeks_clause(question)):
        return None

    core_counts: dict[str, int] = {}
    auxiliary_counts: dict[str, int] = {}
    best_core: tuple[float, str, str] = (-1.0, "", "")
    for chunk in chunks or []:
        key = document_key(chunk)
        if key in core:
            core_counts[key] = core_counts.get(key, 0) + 1
            score = float(chunk.get("similarity") or 0.0)
            if score > best_core[0]:
                best_core = (score, document_id(chunk), document_name(chunk))
        else:
            auxiliary_counts[key] = auxiliary_counts.get(key, 0) + 1

    core_total = sum(core_counts.values())
    if not core_total or max(auxiliary_counts.values(), default=0) <= core_total:
        return None
    _, doc_id, doc_name = best_core
    if not doc_id:
        # Only a file name is known, and a file name is not a doc-store id: a
        # scoped search would match nothing and hide the standard completely.
        _LOG.info("[Multi-route] the standard for this question has no doc id (%s); skipping the document-scoped route", doc_name or "?")
        return None

    queries: list[str] = []
    for query in list(preferred_routes) + [question]:
        text = " ".join(str(query or "").split())
        if text and text not in queries:
            queries.append(text)
        if len(queries) >= MAX_CORE_DOCUMENT_ROUTES:
            break
    _LOG.info(
        "[Multi-route] the standard is out-numbered %d to %d in the pool; searching %s itself (%d route(s))",
        core_total,
        max(auxiliary_counts.values(), default=0),
        doc_name or doc_id,
        len(queries),
    )
    return doc_id, doc_name, queries


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
    sub_queries: list[str] = []
    if looks_composite(question):
        sub_queries = await decompose_question(chat_mdl, question, max_sub_queries)
        routes.extend(sub_queries)
    # A rule-seeking question also gets a route at the normative PROSE tier. It is
    # deterministic on purpose: it must fire on every clause question, including
    # the ones the LLM decomposition failed on or never saw (single-dimension
    # wording), because a bidder fill-in table can win the fused score against it.
    targeted = clause_route(question)
    if targeted:
        routes.append(targeted)
    _LOG.info("[Multi-route] question=%r -> %d route(s): %s", question[:80], len(routes), routes)

    async def _retrieve(queries, doc_scope):
        return await multi_route_retrieve(
            retriever=retriever,
            queries=queries,
            embd_mdl=embd_mdl,
            tenant_ids=tenant_ids,
            kb_ids=kb_ids,
            routes_top_k=routes_top_k,
            similarity_threshold=similarity_threshold,
            vector_similarity_weight=vector_similarity_weight,
            knn_top_k=knn_top_k,
            rerank_candidates_count=rerank_candidates_count,
            doc_ids=doc_scope,
            rank_feature=rank_feature,
            must_not=must_not,
            allow_dense_fallback=allow_dense_fallback,
        )

    merged = await _retrieve(routes, doc_ids)
    if not merged.get("chunks"):
        return empty_kbinfos()

    # Second chance for the standard: the cut can rebalance what was recalled, but
    # it cannot bring back a clause no route retrieved. When an auxiliary document
    # out-recalled the standard on a question about several parameters (or about a
    # rule), one more pass searches the standard itself.
    followup = core_document_followup(merged["chunks"], question, preferred_routes=[*sub_queries, *([targeted] if targeted else [])])
    if followup:
        doc_id, doc_name, queries = followup
        scoped = await _retrieve(queries, [doc_id])
        before = len(merged["chunks"])
        merged = merge_route_hits(
            [RouteResult(query=query, chunks=[dict(chunk, core_scoped=True) for chunk in scoped["chunks"]], doc_aggs=scoped["doc_aggs"]) for query in queries],
            existing=merged,
        )
        _LOG.info("[Multi-route] document-scoped follow-up on %s added %d passage(s) (%d -> %d in the pool)", doc_name or doc_id, len(merged["chunks"]) - before, before, len(merged["chunks"]))

    chunks = await rerank_chunks(rerank_mdl, merged["chunks"], question, final_top_n)
    return {"total": merged.get("total", len(chunks)), "chunks": chunks, "doc_aggs": merged.get("doc_aggs", [])}
