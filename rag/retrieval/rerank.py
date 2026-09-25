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
"""Module C — rerank the merged pool against the original question and cut the
context the answer model receives.

Two decisions here are what separate this stage from the fused score the routes
computed:

* the query handed to the reranker is the user's ORIGINAL question, not a
  sub-query. The sub-queries exist to make recall per topic possible; relevance
  to what was actually asked is what decides which passages reach the answer, so
  a passage that only answers part of the question is not silently promoted
  because some sub-query matched it alone;
* the reranker's own score replaces the fused score instead of being averaged
  with it. The fused score's text leg is a query-recall ratio, and for a
  multi-dimensional question that ratio penalizes every passage for the
  dimensions it does not cover - the same dilution that motivated module A.
  ``fused_similarity`` keeps the pre-rerank value for diagnosis.

Without a reranker (a tenant with none configured, or a reranker that fails) the
pool is returned ordered by the fused score, so the answer still gets the routes'
own best passages.

The CUT is not a plain top-N, and that is the third decision here. A composite
question's routes recall different chapters, and those chapters do not score
equally against the whole question: measured on the cable corpus with a
five-parameter question, twelve near-identical parameter tables of the dimension
the question leads with scored 0.596-0.603 and filled all twelve slots, while the
``6.2.3 交流电压试验`` clause the corpus does hold sat at 0.577 and was dropped -
the same "the window is filled by one topic" failure the routes exist to undo,
one stage later. One slot per route is therefore reserved before the remaining
slots take the highest scoring passages left.
"""

from __future__ import annotations

import logging
from typing import Any, Sequence

from common.misc_utils import thread_pool_exec
from rag.retrieval.multi_route import chunk_key

_LOG = logging.getLogger(__name__)

#: Passages kept for the answer. The recommended band is 6-8; a configured
#: ``top_n`` always wins (the cable assistant sets 12 for a measured reason - see
#: ``api/db/cable_defaults.py``).
DEFAULT_FINAL_TOP_N = 8
FINAL_TOP_N_RECOMMENDED = (6, 8)


def dedupe_chunks(chunks: Sequence[dict]) -> list[dict]:
    """Drop repeated ``chunk_id``s, keeping the first occurrence.

    The pool arriving here was already merged across routes, so a duplicate now
    can only come from a caller assembling its own pool (e.g. a web-search
    passage that repeats a document passage). Order is preserved so the
    pre-rerank ordering stays meaningful for ties and for the no-reranker path.
    """
    seen: set[str] = set()
    out: list[dict] = []
    for chunk in chunks or []:
        key = chunk_key(chunk)
        if key in seen:
            continue
        seen.add(key)
        out.append(chunk)
    return out


def routes_of(chunk: dict) -> list[str]:
    """The routes that recalled ``chunk`` (empty for a passage from elsewhere)."""
    routes = chunk.get("retrieval_routes")
    return [str(route) for route in routes] if isinstance(routes, list) else []


def ensure_route_coverage(ordered: Sequence[dict], top_n: int) -> list[dict]:
    """Cut ``ordered`` to ``top_n`` while keeping every route represented.

    ``ordered`` is score-ordered and is NOT truncated before this runs: the best
    passage of a route can sit below the cut, which is exactly the case this
    exists for. One slot per route goes to that route's highest scoring passage,
    then the remaining slots take the highest scoring passages left. The result
    keeps ``ordered``'s order, so the prompt and its citation numbers stay
    relevance-ordered.

    A pool with fewer passages than slots, or one that came from a single route,
    is cut the ordinary way - there is nothing to balance.
    """
    if top_n <= 0:
        return []
    if len(ordered) <= top_n:
        return list(ordered)

    route_order: list[str] = []
    for chunk in ordered:
        for route in routes_of(chunk):
            if route not in route_order:
                route_order.append(route)
    if len(route_order) <= 1:
        return list(ordered[:top_n])

    chosen: list[str] = []
    chosen_keys: set[str] = set()
    for route in route_order:
        if len(chosen) >= top_n:
            break
        for chunk in ordered:
            key = chunk_key(chunk)
            if key in chosen_keys:
                continue
            if route in routes_of(chunk):
                chosen.append(key)
                chosen_keys.add(key)
                break
    if len(chosen) < top_n:
        for chunk in ordered:
            if len(chosen) >= top_n:
                break
            key = chunk_key(chunk)
            if key in chosen_keys:
                continue
            chosen.append(key)
            chosen_keys.add(key)
    return [chunk for chunk in ordered if chunk_key(chunk) in chosen_keys]


def _select(ordered: Sequence[dict], top_n: int, *, reason: str) -> list[dict]:
    selected = ensure_route_coverage(ordered, top_n)
    _LOG.info(
        "[Rerank] %d candidate(s) -> %d passage(s) kept%s (best scores %s)",
        len(ordered),
        len(selected),
        reason,
        ", ".join(f"{float(chunk.get('similarity') or 0.0):.4f}" for chunk in selected[:3]) or "-",
    )
    return selected


def _by_fused_score(chunks: Sequence[dict], top_n: int) -> list[dict]:
    def score(chunk: dict) -> float:
        try:
            return float(chunk.get("similarity") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    return _select(sorted(chunks, key=score, reverse=True), top_n, reason="")


def resolve_final_top_n(value: Any) -> int:
    """``top_n`` from configuration, defaulting to :data:`DEFAULT_FINAL_TOP_N`."""
    if value is None:
        return DEFAULT_FINAL_TOP_N
    try:
        top_n = int(value)
    except (TypeError, ValueError):
        return DEFAULT_FINAL_TOP_N
    return top_n if top_n > 0 else DEFAULT_FINAL_TOP_N


async def rerank_chunks(rerank_mdl, chunks: Sequence[dict], question: str, top_n: Any = DEFAULT_FINAL_TOP_N) -> list[dict]:
    """Score the de-duplicated pool against ``question`` and assemble the context.

    The scoring order decides which passages are eligible; :func:`ensure_route_coverage`
    decides the cut, so every route of a composite question is represented.

    Never raises: a reranker that is missing, misconfigured, or counting a
    different number of scores than documents degrades to the fused-score
    ordering, because a broken reranker must not turn a question the knowledge
    base can answer into an empty answer.
    """
    limit = resolve_final_top_n(top_n)
    pool = dedupe_chunks(chunks)
    if not pool:
        return []
    if rerank_mdl is None or not str(question or "").strip():
        return _by_fused_score(pool, limit)

    docs = [str(chunk.get("content_with_weight") or chunk.get("content") or "") for chunk in pool]
    if not any(doc.strip() for doc in docs):
        _LOG.warning("[Rerank] %d candidate(s) carry no text; keeping the fused order", len(pool))
        return _by_fused_score(pool, limit)

    try:
        scores, _ = await thread_pool_exec(rerank_mdl.similarity, question, docs)
    except Exception as exc:  # noqa: BLE001 - reranking is an ordering pass
        _LOG.warning("[Rerank] reranker failed on %d candidate(s); keeping the fused order: %s", len(pool), exc)
        return _by_fused_score(pool, limit)

    scores = [] if scores is None else list(scores)
    if len(scores) != len(pool):
        _LOG.warning("[Rerank] reranker returned %d score(s) for %d candidate(s); keeping the fused order", len(scores), len(pool))
        return _by_fused_score(pool, limit)

    for chunk, score in zip(pool, scores):
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        chunk.setdefault("fused_similarity", chunk.get("similarity"))
        chunk["rerank_score"] = value
        chunk["similarity"] = value

    ordered = sorted(pool, key=lambda chunk: float(chunk.get("rerank_score") or 0.0), reverse=True)
    return _select(ordered, limit, reason=" by rerank score")
