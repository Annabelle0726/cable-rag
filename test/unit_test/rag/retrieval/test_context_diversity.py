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
"""Table dominance: a clause question must not get a window of nothing but tables.

Four live smoke tests on the cable corpus produced this shape:

* with the standard number in the question (Q/GDW 73237.1) retrieval hit eleven
  prose passages of 《第1部分：通用技术规范》 and answered perfectly;
* without it, a bidder fill-in table of 《第2部分：专用技术规范》 - cells that
  repeat every parameter name and unit the question uses - won the fused score,
  and the window came back as tables only ("[1][5][8] 全是表格"), so the answer
  layer reported 只有表格，没有正文规定 for a question whose clause was in the
  corpus;
* a question about 优先权/以谁为准 never reached 4.1.10 at all.

The corpus below is that shape: twelve parameter tables that out-score three
normative clauses. What the cut can fix, it must fix; what only recall can fix,
it must SAY it cannot fix.
"""

import logging

import pytest

from rag.retrieval import chunk_profile, decomposition, pipeline, rerank

pytestmark = pytest.mark.p1

_PART_2 = "doc-part2"
_PART_1 = "doc-part1"

#: A rule-seeking question: its answer is prose stating a rule.
_CLAUSE_QUESTION = "例行交流电压试验的维持时间是多少"

#: A value question: a parameter table answers it, so nothing is reserved.
_VALUE_QUESTION = "绝缘标称厚度是多少"


def _table(chunk_id, score, text="技术参数特性表 标称厚度 mm 绝缘电阻 MΩ 交流电压试验 kV"):
    return {
        "chunk_id": chunk_id,
        "doc_id": _PART_2,
        "docnm_kwd": "Q_GDW_73237.2-2026_专用技术规范.pdf",
        "doc_type_kwd": "table",
        "content_with_weight": text,
        "similarity": score,
    }


def _prose(chunk_id, score, text="6.2.3 例行交流电压试验应施加 3.5kV 电压并维持 5min。"):
    return {
        "chunk_id": chunk_id,
        "doc_id": _PART_1,
        "docnm_kwd": "Q_GDW_73237.1-2026_通用技术规范.pdf",
        "doc_type_kwd": "text",
        "content_with_weight": text,
        "similarity": score,
    }


def _pool():
    """The measured failure: twelve tables that out-score three clauses."""
    tables = [_table(f"t{i}", 0.62 - i * 0.001) for i in range(12)]
    clauses = [_prose("c1", 0.583), _prose("c2", 0.577), _prose("c3", 0.574)]
    return tables + clauses


def _pool_with_enough_prose():
    """Twelve tables and six clauses: the floor and the cap can both hold."""
    tables = [_table(f"t{i}", 0.62 - i * 0.001) for i in range(12)]
    clauses = [_prose(f"c{i}", 0.583 - i * 0.002) for i in range(6)]
    return tables + clauses


def _ordered(pool):
    return sorted(pool, key=lambda chunk: chunk["similarity"], reverse=True)


def _ids(chunks):
    return [chunk["chunk_id"] for chunk in chunks]


# ---------------------------------------------------------------------------
# What a passage IS
# ---------------------------------------------------------------------------


def test_the_parser_label_marks_a_table():
    assert chunk_profile.is_table_chunk(_table("t", 0.5))
    assert not chunk_profile.is_table_chunk(_prose("c", 0.5))


def test_table_markup_marks_a_table_even_without_the_label():
    chunk = _prose("c", 0.5, text="<table><tr><td>标称厚度</td><td>1.2</td></tr></table>")
    chunk["doc_type_kwd"] = "text"

    assert chunk_profile.is_table_chunk(chunk)


def test_an_image_is_not_prose():
    chunk = _prose("i", 0.5, text="")
    chunk["doc_type_kwd"] = "image"

    assert chunk_profile.is_image_chunk(chunk)
    assert not chunk_profile.is_prose_chunk(chunk)


def test_a_summary_names_types_and_documents():
    assert chunk_profile.summarize(_pool()) == "15 passage(s): 3 prose / 12 table / 0 image from 2 document(s)"


# ---------------------------------------------------------------------------
# The route aimed at the prose tier
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("question", ["例行交流电压试验的维持时间是多少", "两份规范对不上时以谁为准", "4.1.10 条对抽样是怎么规定的"])
def test_a_rule_question_gets_a_prose_tier_route(question):
    route = decomposition.clause_route(question)

    assert route is not None
    assert route.endswith(decomposition.CLAUSE_ROUTE_ANCHOR)
    assert "第" not in route, "a structural reference is exactly what the other routes strip"


@pytest.mark.parametrize("question", [_VALUE_QUESTION, "交流电压试验"])
def test_a_value_question_gets_no_extra_route(question):
    assert decomposition.clause_route(question) is None


def test_the_prose_route_strips_the_section_reference_from_the_subject():
    question = "第5章 5.3.3 例行试验的抽样是怎么规定的"

    route = decomposition.clause_route(question)

    assert route is not None
    assert route.startswith(decomposition.strip_section_references(question))
    assert "5.3.3" not in route
    assert "第5章" not in route


# ---------------------------------------------------------------------------
# The cut: a prose floor and a table cap
# ---------------------------------------------------------------------------


def test_a_clause_question_keeps_prose_and_caps_tables():
    selected = rerank.select_context(_ordered(_pool_with_enough_prose()), 12, rerank.DiversityPolicy.for_question(_CLAUSE_QUESTION))

    assert len(selected) == 12
    prose = [c for c in selected if chunk_profile.is_prose_chunk(c)]
    tables = [c for c in selected if chunk_profile.is_table_chunk(c)]
    assert len(prose) >= rerank.MIN_PROSE_PASSAGES
    assert len(tables) == 6, "tables may take at most half the window"
    assert "c0" in _ids(selected), "the clause the corpus holds must be in the context"


def test_scarce_prose_shrinks_the_window_rather_than_filling_it_with_tables():
    """A cap a pool cannot fill is reported, not silently traded for tables.

    Three clauses and twelve tables at a 50% table cap cannot make 12 passages:
    six table slots plus three prose is nine. The window stays nine, so the cap
    means what it says.
    """
    selected = rerank.select_context(_ordered(_pool()), 12, rerank.DiversityPolicy.for_question(_CLAUSE_QUESTION))

    assert len(selected) == 9
    assert len([c for c in selected if chunk_profile.is_table_chunk(c)]) == 6
    assert len([c for c in selected if chunk_profile.is_prose_chunk(c)]) == 3
    assert "c1" in _ids(selected)


def test_a_value_question_keeps_the_plain_cut():
    """The floor is scoped to rule questions: a table answers a value question."""
    selected = rerank.select_context(_ordered(_pool()), 12, rerank.DiversityPolicy.for_question(_VALUE_QUESTION))

    assert _ids(selected)[:12] == [f"t{i}" for i in range(12)]


def test_the_floor_never_overruns_the_window():
    selected = rerank.select_context(_ordered(_pool()), 3, rerank.DiversityPolicy.for_question(_CLAUSE_QUESTION))

    assert len(selected) == 3
    assert all(chunk_profile.is_prose_chunk(c) for c in selected), "the floor spends the window on clauses"


async def test_a_table_only_pool_still_fills_the_window_and_says_why_the_floor_failed(caplog):
    """The floor cannot invent a clause: a table-only pool is a RECALL failure."""
    pool = [_table(f"t{i}", 0.62 - i * 0.001) for i in range(12)]

    with caplog.at_level(logging.WARNING):
        kept = await rerank.rerank_chunks(None, pool, _CLAUSE_QUESTION, top_n=8)

    assert len(kept) == 8
    assert "RECALL problem" in caplog.text


async def test_a_pool_that_holds_prose_does_not_claim_a_recall_failure(caplog):
    with caplog.at_level(logging.WARNING):
        kept = await rerank.rerank_chunks(None, _pool_with_enough_prose(), _CLAUSE_QUESTION, top_n=12)

    assert "RECALL problem" not in caplog.text
    assert len([c for c in kept if chunk_profile.is_prose_chunk(c)]) >= rerank.MIN_PROSE_PASSAGES


# ---------------------------------------------------------------------------
# The ordering nudge
# ---------------------------------------------------------------------------


async def test_a_table_is_nudged_down_for_a_clause_question():
    pool = [_table("t1", 0.60), _prose("c1", 0.55)]

    kept = await rerank.rerank_chunks(None, pool, _CLAUSE_QUESTION, top_n=1)

    assert _ids(kept) == ["c1"], "0.60 * 0.85 = 0.51 falls below the clause at 0.55"


async def test_the_nudge_also_applies_to_a_question_that_only_mentions_a_test():
    pool = [_table("t1", 0.60), _prose("c1", 0.55)]

    kept = await rerank.rerank_chunks(None, pool, "交流电压试验的数值是多少", top_n=1)

    assert _ids(kept) == ["c1"]


async def test_no_nudge_for_a_value_question():
    pool = [_table("t1", 0.60), _prose("c1", 0.55)]

    kept = await rerank.rerank_chunks(None, pool, _VALUE_QUESTION, top_n=1)

    assert _ids(kept) == ["t1"]


def test_the_nudge_never_overwrites_the_scores_a_transcript_reports():
    pool = [_table("t1", 0.60)]

    rerank.apply_type_penalty(pool, rerank.DiversityPolicy.for_question(_CLAUSE_QUESTION))

    assert pool[0]["similarity"] == pytest.approx(0.60), "the model's own number stays"
    assert pool[0]["rank_score"] == pytest.approx(0.60 * rerank.TABLE_PENALTY)


def test_route_coverage_is_the_inert_case_of_the_same_cut():
    ordered = sorted(_pool(), key=lambda c: c["similarity"], reverse=True)

    assert _ids(rerank.ensure_route_coverage(ordered, 6)) == _ids(rerank.select_context(ordered, 6))


# ---------------------------------------------------------------------------
# End to end through the pipeline
# ---------------------------------------------------------------------------


class _Store:
    """Hands every route the same pool and records what it was asked."""

    def __init__(self, pool):
        self.pool = pool
        self.questions = []

    async def retrieval(self, question, embd_mdl, tenant_ids, kb_ids, page, page_size, threshold, **kwargs):
        self.questions.append(question)
        return {"total": len(self.pool), "chunks": [dict(c) for c in self.pool], "doc_aggs": []}


async def test_a_clause_question_searches_the_prose_tier_through_the_pipeline(monkeypatch):
    async def _no_decomposition(*_args, **_kwargs):
        return None

    monkeypatch.setattr(decomposition, "gen_json", _no_decomposition)
    store = _Store(_pool_with_enough_prose())

    result = await pipeline.retrieve_multi_route(
        retriever=store,
        question=_CLAUSE_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=12,
    )

    assert store.questions == [_CLAUSE_QUESTION, f"{_CLAUSE_QUESTION} {decomposition.CLAUSE_ROUTE_ANCHOR}"]
    assert len([c for c in result["chunks"] if chunk_profile.is_prose_chunk(c)]) >= rerank.MIN_PROSE_PASSAGES


async def test_a_value_question_searches_one_route(monkeypatch):
    async def _no_decomposition(*_args, **_kwargs):
        return None

    monkeypatch.setattr(decomposition, "gen_json", _no_decomposition)
    store = _Store(_pool())

    await pipeline.retrieve_multi_route(
        retriever=store,
        question=_VALUE_QUESTION,
        chat_mdl=object(),
        embd_mdl=object(),
        tenant_ids=["t-1"],
        kb_ids=["kb-1"],
        similarity_threshold=0.55,
        final_top_n=12,
    )

    assert store.questions == [_VALUE_QUESTION]
