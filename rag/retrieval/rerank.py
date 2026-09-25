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

The fourth decision is about passage TYPE, and it is the one four live smoke
tests turned up. A 专用技术规范's bidder fill-in tables repeat every parameter
name and unit a question uses, so they out-score the normative prose of the
通用技术规范 and take the whole window; the answer layer then reports "只有表格，
没有正文规定" for a question whose clause IS in the corpus. When the question asks
for a rule (``seeks_clause``), the cut therefore reserves a PROSE floor, caps how
much of the window tables may take, and orders the pool with a small table
penalty (:class:`DiversityPolicy`). Nothing here can invent a prose passage that
never entered the pool - that is a recall failure and is reported as one.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Sequence

from common.misc_utils import thread_pool_exec
from rag.retrieval.chunk_profile import is_prose_chunk, is_table_chunk, summarize
from rag.retrieval.decomposition import mentions_requirement, seeks_clause
from rag.retrieval.multi_route import chunk_key

_LOG = logging.getLogger(__name__)

#: Passages kept for the answer. The recommended band is 6-8; a configured
#: ``top_n`` always wins (the cable assistant sets 12 for a measured reason - see
#: ``api/db/cable_defaults.py``).
DEFAULT_FINAL_TOP_N = 8
FINAL_TOP_N_RECOMMENDED = (6, 8)

#: Room the context must leave for prose when the question asks for a rule.
#: 4 is the "3-4 slots for the 通用技术规范 clause" the smoke tests asked for, and
#: it is affordable inside both the 6-8 band and the cable assistant's 12.
MIN_PROSE_PASSAGES = 4
#: Share of the window tables may take at most, for the same question shape.
MAX_TABLE_SHARE = 0.5
#: Ordering nudge for a tabular passage: enough to put a comparable prose clause
#: first, not enough to reorder passages whose scores actually differ.
TABLE_PENALTY = 0.85


@dataclass(frozen=True)
class DiversityPolicy:
    """How much room the cut must leave for non-tabular prose.

    Two strengths, because the two intents differ. A RULE question ("例行交流电压
    试验的维持时间是多少", "两份规范对不上时以谁为准") gets the full policy: a
    window reserved for prose is the only way it gets answered, since a fill-in
    table cannot state a rule. A question that merely mentions a requirement or a
    test gets the ordering nudge alone - a parameter table IS the right source for
    绝缘电阻试验的数值是多少, so its window is not reserved for prose.
    """

    min_prose: int = 0
    max_table_share: float = 1.0
    table_penalty: float = 1.0

    @classmethod
    def for_question(cls, question: str) -> "DiversityPolicy":
        if seeks_clause(question):
            return cls(min_prose=MIN_PROSE_PASSAGES, max_table_share=MAX_TABLE_SHARE, table_penalty=TABLE_PENALTY)
        if mentions_requirement(question):
            return cls(table_penalty=TABLE_PENALTY)
        return cls()

    @property
    def active(self) -> bool:
        return self.min_prose > 0 or self.max_table_share < 1.0 or self.table_penalty != 1.0


def _score(chunk: dict, *, key: str = "similarity") -> float:
    try:
        return float(chunk.get(key) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def apply_type_penalty(chunks: Sequence[dict], policy: DiversityPolicy) -> list[dict]:
    """Order the pool by its score, tabular passages nudged down.

    Writes ``rank_score`` (the value the cut orders by) and leaves the model's own
    numbers untouched: ``similarity`` still means what the reranker or the fused
    score said, so a transcript can tell a relevance decision from a tie-break.
    """
    for chunk in chunks:
        base = _score(chunk, key="rerank_score") or _score(chunk)
        penalty = policy.table_penalty if is_table_chunk(chunk) else 1.0
        chunk["rank_score"] = base * penalty
    return sorted(chunks, key=lambda chunk: _score(chunk, key="rank_score"), reverse=True)


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

    A pool with fewer passages than slots, or one that came from a single route,
    is cut the ordinary way - there is nothing to balance. This is
    :func:`select_context` with an inert policy; see it for the reservation order
    and for the type floor a rule-seeking question adds.
    """
    return select_context(ordered, top_n)


def select_context(ordered: Sequence[dict], top_n: int, policy: DiversityPolicy = DiversityPolicy()) -> list[dict]:
    """Cut a score-ordered pool to ``top_n``, reserving slots before filling.

    ``ordered`` is score-ordered and is NOT truncated before this runs: the
    passage a reservation exists for can sit below the cut, which is exactly the
    case this is for. Slots are handed out in priority order:

    1. one slot per route, so a composite question's chapters are all
       represented (the failure the routes themselves exist to undo, one stage
       later);
    2. the prose floor, when the question asks for a rule: normative clauses
       first, because a parameter table cannot state one;
    3. everything else by score - non-table passages first, then tables up to
       ``policy.max_table_share`` of the window.

    A pool with nothing but tables fills the window anyway (step 4): a window of
    tables is worse than a mixed one, but it is not worse than a short one, and
    reserving slots a pool cannot fill would silently shrink the evidence.

    What a cap DOES cost is honesty about the window's size: with twelve tables
    and three clauses, a 12-slot window at a 50% table cap comes back with 9
    passages, not 12 - the three slots the cap withheld had no prose to go to.
    The caller is told (see :func:`_select`).

    The result keeps ``ordered``'s order, so the prompt and its citation numbers
    stay relevance-ordered.
    """
    if top_n <= 0:
        return []
    if len(ordered) <= top_n:
        return list(ordered)

    chosen_keys: set[str] = set()
    chosen: list[str] = []

    def take(chunk: dict) -> bool:
        if len(chosen) >= top_n:
            return False
        key = chunk_key(chunk)
        if key in chosen_keys:
            return False
        chosen.append(key)
        chosen_keys.add(key)
        return True

    def taken(predicate) -> int:
        return sum(1 for chunk in ordered if chunk_key(chunk) in chosen_keys and predicate(chunk))

    # 1. one slot per route
    route_order: list[str] = []
    for chunk in ordered:
        for route in routes_of(chunk):
            if route not in route_order:
                route_order.append(route)
    if len(route_order) > 1:
        for route in route_order:
            for chunk in ordered:
                if route in routes_of(chunk) and take(chunk):
                    break

    # 2. the prose floor
    if policy.min_prose > 0:
        prose_taken = taken(is_prose_chunk)
        for chunk in ordered:
            if prose_taken >= policy.min_prose or len(chosen) >= top_n:
                break
            if is_prose_chunk(chunk) and take(chunk):
                prose_taken += 1

    # 3. everything else by score. A capped cut takes non-table passages first;
    # an uncapped one is a plain top-N and must not prefer anything.
    cap = top_n if policy.max_table_share >= 1.0 else min(top_n, math.ceil(top_n * policy.max_table_share))
    if cap < top_n:
        for chunk in ordered:
            if len(chosen) >= top_n:
                break
            if not is_table_chunk(chunk):
                take(chunk)
        for chunk in ordered:
            if len(chosen) >= top_n or taken(is_table_chunk) >= cap:
                break
            if is_table_chunk(chunk):
                take(chunk)
        # 4. A pool with nothing but tables cannot satisfy the cap; a window of
        # tables is worse than a mixed one but not worse than a short one.
        if not any(not is_table_chunk(chunk) for chunk in ordered):
            for chunk in ordered:
                take(chunk)
    else:
        for chunk in ordered:
            if len(chosen) >= top_n:
                break
            take(chunk)

    return [chunk for chunk in ordered if chunk_key(chunk) in chosen_keys]


def _select(ordered: Sequence[dict], top_n: int, *, policy: DiversityPolicy, reason: str) -> list[dict]:
    selected = select_context(ordered, top_n, policy)
    tables = sum(1 for chunk in selected if is_table_chunk(chunk))
    prose = sum(1 for chunk in selected if is_prose_chunk(chunk))
    prose_available = sum(1 for chunk in ordered if is_prose_chunk(chunk))
    shortfall = ""
    if len(selected) < min(top_n, len(ordered)):
        shortfall = (
            f"; window cut to {len(selected)} because the table cap ({math.ceil(top_n * policy.max_table_share)}) and the prose floor left no eligible passage (pool holds {prose_available} prose)"
        )
    _LOG.info(
        "[Rerank] %d candidate(s) -> %d passage(s) kept%s (%d prose / %d table; best scores %s)%s",
        len(ordered),
        len(selected),
        reason,
        prose,
        tables,
        ", ".join(f"{_score(chunk):.4f}" for chunk in selected[:3]) or "-",
        shortfall,
    )
    return selected


def _warn_when_the_pool_cannot_satisfy_the_floor(pool: Sequence[dict], policy: DiversityPolicy) -> None:
    """Say which stage failed when a clause question has no clause to answer from.

    A prose floor can only promote a passage that is IN the pool. When the pool
    holds none, the tables crowded the prose out of every route's own window
    before this stage ever saw it - a recall failure, and the transcript has to
    say so, or the next smoke test reads as "the fix did not work".
    """
    if not policy.min_prose:
        return
    if any(is_prose_chunk(chunk) for chunk in pool):
        return
    _LOG.warning(
        "[Rerank] none of the %d merged candidate(s) is prose: the %d-passage prose floor cannot be met. "
        "The tables won every route's own window - this is a RECALL problem (raise the per-route window or "
        "add a route aimed at the prose tier), not a cut problem.",
        len(pool),
        policy.min_prose,
    )


def _by_fused_score(chunks: Sequence[dict], top_n: int, policy: DiversityPolicy = DiversityPolicy()) -> list[dict]:
    return _select(apply_type_penalty(list(chunks), policy), top_n, policy=policy, reason="")


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

    The scoring order decides which passages are eligible and
    :func:`select_context` decides the cut: every route of a composite question is
    represented, and a rule-seeking question also gets its prose floor.

    Never raises: a reranker that is missing, misconfigured, or counting a
    different number of scores than documents degrades to the fused-score
    ordering, because a broken reranker must not turn a question the knowledge
    base can answer into an empty answer.
    """
    limit = resolve_final_top_n(top_n)
    pool = dedupe_chunks(chunks)
    if not pool:
        return []
    policy = DiversityPolicy.for_question(question)
    _warn_when_the_pool_cannot_satisfy_the_floor(pool, policy)
    if rerank_mdl is None or not str(question or "").strip():
        return _by_fused_score(pool, limit, policy)

    docs = [str(chunk.get("content_with_weight") or chunk.get("content") or "") for chunk in pool]
    if not any(doc.strip() for doc in docs):
        _LOG.warning("[Rerank] %d candidate(s) carry no text; keeping the fused order", len(pool))
        return _by_fused_score(pool, limit, policy)

    try:
        scores, _ = await thread_pool_exec(rerank_mdl.similarity, question, docs)
    except Exception as exc:  # noqa: BLE001 - reranking is an ordering pass
        _LOG.warning("[Rerank] reranker failed on %d candidate(s); keeping the fused order: %s", len(pool), exc)
        return _by_fused_score(pool, limit, policy)

    scores = [] if scores is None else list(scores)
    if len(scores) != len(pool):
        _LOG.warning("[Rerank] reranker returned %d score(s) for %d candidate(s); keeping the fused order", len(scores), len(pool))
        return _by_fused_score(pool, limit, policy)

    for chunk, score in zip(pool, scores):
        try:
            value = float(score)
        except (TypeError, ValueError):
            continue
        chunk.setdefault("fused_similarity", chunk.get("similarity"))
        chunk["rerank_score"] = value
        chunk["similarity"] = value

    selected = _select(apply_type_penalty(pool, policy), limit, policy=policy, reason=" by rerank score")
    _LOG.info("[Rerank] pool %s -> context %s", summarize(pool), summarize(selected))
    return selected
