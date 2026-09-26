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
"""Document flooding: one auxiliary file must not own the context.

Measured live, on a question about 例行试验:

    recalled 9 passages
    《20_架空绝缘导线抽检工作规范.pdf》  7 passages / 22,684 characters
    《Q/GDW 73237.1 通用技术规范.pdf》   2 passages /  1,130 characters

The working document's whole text repeats 例行试验, so it out-scored the clause
that DEFINES the test, and a plain top-N handed the answer model the working
document and little else - the 通用技术规范's clauses never reached the context.

Two mechanisms, both on the document axis and both scoped to a corpus that
advertises a standard (a file name carrying a standard designation, or a tier
name like 采购标准/通用技术规范/专用技术规范):

* a boost for the standard, so its passage wins a near-tie and is cited first;
* a per-document quota for the auxiliary files (40% of the window), so one of
  them cannot take the whole context.

The earlier milestone's winning answer came from ELEVEN passages of one
document, so the standard itself is exempt from the quota - these cases pin that
too.
"""

import pytest

from rag.retrieval import chunk_profile, rerank

pytestmark = pytest.mark.p1

_STANDARD = "Q_GDW_73237.1-2026_通用技术规范.pdf"
_AUXILIARY = "20_架空绝缘导线抽检工作规范.pdf"
_QUESTION = "例行交流电压试验的维持时间是多少？"

#: The measured failure: seven auxiliary passages ahead of two standard clauses.
_AUXILIARY_SCORES = [0.63, 0.62, 0.615, 0.61, 0.605, 0.60, 0.595]
_STANDARD_SCORES = [0.59, 0.585]


def _chunk(chunk_id, doc, score):
    return {
        "chunk_id": chunk_id,
        "doc_id": doc.split(".pdf")[0],
        "docnm_kwd": doc,
        "doc_type_kwd": "text",
        "content_with_weight": f"{chunk_id} 例行交流电压试验应施加 3.5kV 电压并维持 5min。",
        "similarity": score,
    }


def _pool():
    chunks = [_chunk(f"aux{i}", _AUXILIARY, score) for i, score in enumerate(_AUXILIARY_SCORES)]
    chunks += [_chunk(f"std{i}", _STANDARD, score) for i, score in enumerate(_STANDARD_SCORES)]
    return chunks


def _ids(chunks):
    return [chunk["chunk_id"] for chunk in chunks]


def _ordered(pool):
    return sorted(pool, key=lambda chunk: chunk["similarity"], reverse=True)


# ---------------------------------------------------------------------------
# Which document is the standard
# ---------------------------------------------------------------------------


def test_a_file_name_designation_marks_the_standard():
    """Separators are normalized away, so a question's ``Q/GDW 73237.1`` matches
    an archived file's ``Q_GDW_73237.1-2026``."""
    assert chunk_profile.standard_designations(_STANDARD) == {"QGDW73237.1"}
    assert chunk_profile.core_document_score(_STANDARD) == 3, "designation + tier name"
    assert chunk_profile.core_document_score(_AUXILIARY) == 0, "a working document claims nothing"


def test_the_designation_in_the_question_picks_the_document():
    pool = _pool()
    pool.append(_chunk("other0", "GB_T_9999-2020_其他标准.pdf", 0.5))

    core = chunk_profile.resolve_core_documents(pool, "Q/GDW 73237.1 的例行试验要求")

    assert {chunk_profile.document_name(pool[i]) for i in range(len(pool)) if chunk_profile.document_key(pool[i]) in core} == {_STANDARD}


def test_a_corpus_without_a_standard_identifies_nothing():
    """No designation, no tier name: the cut must not invent a quota."""
    pool = [_chunk("a0", "供应商数据表.pdf", 0.6), _chunk("b0", "产品说明书.pdf", 0.5)]

    assert chunk_profile.resolve_core_documents(pool, _QUESTION) == set()


def test_documents_that_both_advertise_a_standard_are_both_core():
    """A standard split across parts: neither part is an auxiliary file."""
    pool = [_chunk("p1", "Q_GDW_73237.1-2026_通用技术规范.pdf", 0.6), _chunk("p2", "Q_GDW_73237.2-2026_专用技术规范.pdf", 0.5)]

    assert len(chunk_profile.resolve_core_documents(pool, _QUESTION)) == 2


# ---------------------------------------------------------------------------
# The cut
# ---------------------------------------------------------------------------


def test_an_auxiliary_document_cannot_own_the_window():
    """The quota rebalances the window and hands the lead back to the standard.

    What it CANNOT do is manufacture more standard passages: the pool holds two,
    so two is what the context gets, and the three slots the quota withheld from
    the auxiliary file stay empty rather than going back to it. Those three are
    the honest sign that the standard was UNDER-RECALLED (its other clauses never
    entered the pool at all) - a recall gap, which the per-document line in the
    transcript now shows before anyone tunes the cut again.
    """
    policy = rerank.DiversityPolicy.for_question(_QUESTION, _pool())
    # The production path: the boost orders the pool, then the quota cuts it.
    ordered = rerank.apply_rank_adjustments(_pool(), policy)

    selected = rerank.select_context(ordered, 9, policy)

    auxiliary = [c for c in selected if chunk_profile.document_name(c) == _AUXILIARY]
    standard = [c for c in selected if chunk_profile.document_name(c) == _STANDARD]
    assert len(auxiliary) == 4, "40% of a nine-passage window"
    assert len(standard) == 2, "the standard keeps every passage it has"
    assert len(selected) == 6, "the withheld slots are not handed back to the flooder"
    assert _ids(selected)[:2] == ["std0", "std1"], "and the standard leads the context"


def test_the_standard_itself_is_never_quota_capped():
    """Eleven passages of one standard document was the winning answer."""
    pool = [_chunk(f"std{i}", _STANDARD, 0.70 - i * 0.001) for i in range(11)]
    pool += [_chunk(f"aux{i}", _AUXILIARY, 0.50 - i * 0.001) for i in range(4)]
    policy = rerank.DiversityPolicy.for_question(_QUESTION, pool)

    selected = rerank.select_context(_ordered(pool), 12, policy)

    assert len([c for c in selected if chunk_profile.document_name(c) == _STANDARD]) == 11
    assert len(selected) == 12


def test_a_corpus_without_a_standard_keeps_a_plain_cut():
    pool = [_chunk(f"a{i}", "供应商数据表.pdf", 0.6 - i * 0.001) for i in range(9)]
    pool += [_chunk("b0", "产品说明书.pdf", 0.5)]
    policy = rerank.DiversityPolicy.for_question(_QUESTION, pool)

    selected = rerank.select_context(_ordered(pool), 9, policy)

    assert policy.max_auxiliary_document_share == 1.0
    assert len([c for c in selected if chunk_profile.document_name(c) == "供应商数据表.pdf"]) == 9


def test_the_boost_puts_the_standard_first_on_a_near_tie():
    pool = [_chunk("aux0", _AUXILIARY, 0.600), _chunk("std0", _STANDARD, 0.590)]
    policy = rerank.DiversityPolicy.for_question(_QUESTION, pool)

    ordered = rerank.apply_rank_adjustments(pool, policy)

    assert _ids(ordered) == ["std0", "aux0"], "0.590 * 1.15 = 0.679 beats 0.600 of an auxiliary file"


def test_the_boost_does_not_overwrite_the_reported_scores():
    pool = [_chunk("std0", _STANDARD, 0.590)]

    rerank.apply_rank_adjustments(pool, rerank.DiversityPolicy.for_question(_QUESTION, pool))

    assert pool[0]["similarity"] == pytest.approx(0.590)
    assert pool[0]["rank_score"] == pytest.approx(0.590 * rerank.CORE_DOCUMENT_BOOST)


def test_the_quota_never_zeroes_an_auxiliary_document():
    """A smaller window still leaves an auxiliary file at least one slot."""
    policy = rerank.DiversityPolicy.for_question(_QUESTION, _pool())

    selected = rerank.select_context(_ordered(_pool()), 3, policy)

    assert len([c for c in selected if chunk_profile.document_name(c) == _AUXILIARY]) >= 1


async def test_the_log_names_the_core_document_and_the_quota(caplog):
    import logging

    with caplog.at_level(logging.INFO):
        kept = await rerank.rerank_chunks(None, _pool(), _QUESTION, top_n=9)

    assert len(kept) == 6, "four auxiliary passages plus the standard's two"
    assert "auxiliary documents are capped at 4 of 9" in caplog.text
    assert "documents: " in caplog.text, "the transcript names who filled the context"
    assert "per-document quota 4" in caplog.text, "and which quota cost the window slots"
    assert "table cap" not in caplog.text, "a cap that could not bind must not be blamed"


def test_the_document_breakdown_counts_per_document():
    assert chunk_profile.document_breakdown(_pool()) == f"{_AUXILIARY} x7, {_STANDARD} x2"
