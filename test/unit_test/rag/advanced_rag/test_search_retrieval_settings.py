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
"""
The agentic search tools must retrieve with the caller's retrieval settings.

`hybrid_search` hardcoded `vector_similarity_weight=0.3`, `similarity_threshold=0.2`
and `top_n=12`, so a chat assistant's own tuning had no effect on any query the
agentic path made. The classic (non-agentic) chat path always honoured these
fields; the agentic search framework (#16859) reimplemented retrieval without them.

`vector_search` and `bm25_search` keep their own weights and thresholds: those are
what those tools mean, not a default standing in for configuration.

The second half covers the two ways the caller's threshold used to silence a
knowledge base that could answer: appending the extracted keyword expansion to the
scored query lowered every passage's score (the text leg is a query-RECALL ratio),
and applying the raw threshold as a hard cut then emptied the pool. Both are
reproduced from the cable assistant, whose retrieved answer chunk scored 0.6085 on
its question and 0.5283 with the expansion appended, under a 0.55 threshold.
"""

import logging

import pytest

from rag.advanced_rag.harness.tools import search as search_tools

pytestmark = pytest.mark.p1


class _Tools:
    """Minimal stand-in for RAGTools, carrying only what the search tools read."""

    def __init__(self, **settings):
        self.kb_ids = ["kb-1"]
        self.sql_kbs = []
        self.tenant_ids = ["t-1"]
        self.embed_mdl = object()
        self.search_cache = None
        for name, value in settings.items():
            setattr(self, name, value)


class _Recorder:
    """Captures the arguments of every retrieval call a search tool makes.

    ``args``/``kwargs`` expose the FIRST call — the one made with the caller's own
    settings — because a search may legitimately issue a second call (the
    threshold rescue), and "which settings did this tool ask for" is a question
    about the first. ``calls`` keeps them all.
    """

    def __init__(self):
        self.args = None
        self.kwargs = None
        self.calls = []

    async def retrieval(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.args is None:
            self.args, self.kwargs = args, kwargs
        return {"chunks": [], "doc_aggs": []}

    @staticmethod
    def retrieval_by_children(chunks, _tenant_ids):
        return chunks


@pytest.fixture
def recorder(monkeypatch):
    rec = _Recorder()
    monkeypatch.setattr(search_tools.settings, "retriever", rec)
    monkeypatch.setattr(search_tools, "_normalize", lambda kbinfos, tenant_ids: kbinfos)
    return rec


def _top_k(rec):
    return rec.kwargs.get("knn_top_k")


def _call(rec):
    """(page_size, similarity_threshold, vector_similarity_weight, rerank_candidates_count)."""
    return (
        rec.args[5],
        rec.args[6],
        rec.kwargs["vector_similarity_weight"],
        rec.kwargs.get("rerank_candidates_count"),
    )


async def test_hybrid_search_uses_the_configured_settings(recorder):
    tools = _Tools(vector_similarity_weight=0.8, similarity_threshold=0.35, top_n=20, rerank_candidates_count=256, top_k=4096)

    await search_tools.hybrid_search(tools, query="q")

    assert _call(recorder) == (20, 0.35, 0.8, 256)
    assert _top_k(recorder) == 4096


async def test_hybrid_search_falls_back_when_nothing_is_configured(recorder):
    """An unconfigured caller must behave exactly as before this change."""
    await search_tools.hybrid_search(_Tools(), query="q")

    assert _call(recorder) == (12, 0.2, 0.3, 64)
    assert _top_k(recorder) == 1024


async def test_zero_weight_is_configuration_not_absence(recorder):
    """0.0 is a meaningful weight — it must not be mistaken for "unset"."""
    await search_tools.hybrid_search(_Tools(vector_similarity_weight=0.0, similarity_threshold=0.0), query="q")

    _, threshold, weight, _ = _call(recorder)
    assert weight == 0.0
    assert threshold == 0.0


async def test_no_embedding_model_forces_the_vector_leg_off(recorder):
    """Whatever the caller configured, there is no vector leg without an embedder."""
    tools = _Tools(vector_similarity_weight=0.8)
    tools.embed_mdl = None

    await search_tools.hybrid_search(tools, query="q")

    assert _call(recorder)[2] == 0


async def test_explicit_top_n_argument_beats_the_configuration(recorder):
    await search_tools.hybrid_search(_Tools(top_n=20), query="q", top_n=5)

    assert _call(recorder)[0] == 5


async def test_rerank_candidates_is_never_smaller_than_the_page_it_must_fill(recorder):
    """Dealer.retrieval rejects page * page_size > rerank_candidates_count."""
    await search_tools.hybrid_search(_Tools(top_n=100, rerank_candidates_count=64), query="q")

    page_size, _, _, rerank_candidates = _call(recorder)
    assert page_size == 100
    assert rerank_candidates >= page_size


async def test_vector_search_keeps_its_defining_weight(recorder):
    """Weight 1.0 is what this tool means, not a default standing in for configuration."""
    await search_tools.vector_search(_Tools(vector_similarity_weight=0.3, top_n=7), query="q")

    page_size, threshold, weight, _ = _call(recorder)
    assert (weight, threshold) == (1.0, 0.2)
    assert page_size == 7


async def test_bm25_search_keeps_its_defining_weight(recorder):
    """Weight 0 is what this tool means, not a default standing in for configuration."""
    await search_tools.bm25_search(_Tools(vector_similarity_weight=0.8, top_n=7), query="q")

    page_size, threshold, weight, _ = _call(recorder)
    assert (weight, threshold) == (0, 0.0)
    assert page_size == 7


async def test_top_k_reaches_every_search_tool(recorder):
    """The kNN candidate pool is recall for all three tools, not a hybrid-only knob."""
    for tool in (search_tools.hybrid_search, search_tools.vector_search, search_tools.bm25_search):
        await tool(_Tools(top_k=4096), query="q")
        assert _top_k(recorder) == 4096, tool.__name__


async def test_ragtools_retrieve_honours_the_configuration(monkeypatch):
    """The naive fallback (`_naive_rag` -> `RAGTools.retrieve`) bypasses the search
    tools, so it has to resolve the same settings itself."""
    from rag.advanced_rag import agentic_rag

    rec = _Recorder()
    monkeypatch.setattr(agentic_rag.settings, "retriever", rec)
    monkeypatch.setattr(agentic_rag, "label_question", lambda _q, _kbs: None)

    tools = agentic_rag.RAGTools.__new__(agentic_rag.RAGTools)
    tools.kb_ids = ["kb-1"]
    tools.kbs = []
    tools.tenant_ids = ["t-1"]
    tools.embed_mdl = object()
    tools.doc_scope = None
    tools.similarity_threshold = 0.35
    tools.vector_similarity_weight = 0.8
    tools.top_n = 20
    tools.rerank_candidates_count = 256
    tools.top_k = 4096
    monkeypatch.setattr(type(tools), "scoped_doc_ids", lambda _self, scope: scope, raising=False)

    await tools.retrieve("q", using_embedding=True)

    assert rec.args[5] == 20
    assert rec.args[6] == 0.35
    assert rec.kwargs["vector_similarity_weight"] == 0.8
    assert rec.kwargs["knn_top_k"] == 4096
    assert rec.kwargs["rerank_candidates_count"] == 256


async def test_ragtools_retrieve_keeps_its_own_defaults_when_unconfigured(monkeypatch):
    """Unconfigured callers keep this method's previous behaviour, which is not
    the same as the search tools' (top_n 6, vector weight 0.7)."""
    from rag.advanced_rag import agentic_rag

    rec = _Recorder()
    monkeypatch.setattr(agentic_rag.settings, "retriever", rec)
    monkeypatch.setattr(agentic_rag, "label_question", lambda _q, _kbs: None)

    tools = agentic_rag.RAGTools.__new__(agentic_rag.RAGTools)
    tools.kb_ids = ["kb-1"]
    tools.kbs = []
    tools.tenant_ids = ["t-1"]
    tools.embed_mdl = object()
    tools.doc_scope = None
    for name in ("similarity_threshold", "vector_similarity_weight", "top_n", "rerank_candidates_count", "top_k"):
        setattr(tools, name, None)
    monkeypatch.setattr(type(tools), "scoped_doc_ids", lambda _self, scope: scope, raising=False)

    await tools.retrieve("q", using_embedding=True)

    assert rec.args[5] == 6
    assert rec.args[6] == 0.2
    assert rec.kwargs["vector_similarity_weight"] == 0.7
    assert rec.kwargs["knn_top_k"] == 1024


async def test_hybrid_search_warns_when_no_dataset_is_bound(recorder, caplog):
    """A chat assistant with no dataset bound is a misconfiguration, not an empty
    corpus: the search never runs, so every passage is unreachable. Without this
    warning the two look identical in the transcript (`[Direct search] Found no
    matching passages.`)."""
    tools = _Tools(kb_ids=[])

    with caplog.at_level(logging.WARNING):
        res = await search_tools.hybrid_search(tools, query="q")

    assert res == {"chunks": [], "doc_aggs": []}
    assert recorder.args is None, "the retriever must not be called with no dataset"
    assert "no dataset is bound" in caplog.text


async def test_hybrid_search_reports_a_zero_result_search(recorder, caplog):
    """A query that matched nothing has to say so: this path used to log nothing
    at all, which is indistinguishable from a search that never ran."""
    with caplog.at_level(logging.WARNING):
        await search_tools.hybrid_search(_Tools(), query="q")

    assert "0 chunk(s)" in caplog.text


class _ThresholdScript:
    """Retriever that answers per similarity threshold — the gate is the subject.

    Records every threshold it was called with so a test can tell "the configured
    threshold was used" from "it was replaced" and from "the search ran twice".
    """

    def __init__(self, by_threshold):
        self.by_threshold = by_threshold
        self.thresholds = []

    async def retrieval(self, *args, **kwargs):
        threshold = args[6]
        self.thresholds.append(threshold)
        return {"chunks": list(self.by_threshold.get(threshold, [])), "doc_aggs": []}

    @staticmethod
    def retrieval_by_children(chunks, _tenant_ids):
        return chunks


@pytest.fixture
def scripted(monkeypatch):
    def _install(by_threshold):
        rec = _ThresholdScript(by_threshold)
        monkeypatch.setattr(search_tools.settings, "retriever", rec)
        monkeypatch.setattr(search_tools, "_normalize", lambda kbinfos, tenant_ids: kbinfos)
        return rec

    return _install


async def test_hybrid_search_scores_the_question_alone(recorder):
    """The keyword expansion is a narrowing hint, never extra query text.

    `Qryr.token_similarity` divides the matched term weight by the query's TOTAL
    term weight, so appending extracted terms a passage does not contain lowers
    that passage's score — which is how a retrieved answer chunk fell from 0.6085
    to 0.5283 and under the assistant's 0.55 threshold.
    """
    await search_tools.hybrid_search(
        _Tools(),
        query="检测机构完成 A、B、C 类检测任务的时限分别是多少",
        keywords="检测机构, 时限, 工作日, A类, B类, C类",
    )

    assert recorder.args[0] == "检测机构完成 A、B、C 类检测任务的时限分别是多少"


async def test_hybrid_search_normalises_the_scored_query(scripted):
    """Whitespace in the query must not cost a cache hit on the same question."""
    rec = scripted({0.2: [{"chunk_id": "c1"}]})
    tools = _Tools(search_cache={})

    await search_tools.hybrid_search(tools, query="  a\n b  ")
    await search_tools.hybrid_search(tools, query="a b")

    assert len(rec.thresholds) == 1, "the same question must be retrieved once"


async def test_hybrid_search_rescues_a_pool_the_threshold_emptied(scripted):
    """A threshold above every candidate is a mis-set gate, not an empty corpus.

    The fused score is ``vector_weight * cosine + term_weight * term_recall``, and
    both legs' scales belong to the deployed models — on the cable corpus the
    embedding leg alone gives every chunk ~0.45 — so a threshold tuned elsewhere
    can sit above the whole pool. An answer layer reading "no chunks" as "cannot be
    answered" then refuses a question the corpus answers verbatim, so the search
    re-runs once at the recall floor instead.
    """
    rec = scripted({search_tools._THRESHOLD_RESCUE_FLOOR: [{"chunk_id": "answer"}]})
    tools = _Tools(similarity_threshold=0.55, vector_similarity_weight=0.5, top_n=12, rerank_candidates_count=30)

    res = await search_tools.hybrid_search(tools, query="q")

    assert rec.thresholds == [0.55, search_tools._THRESHOLD_RESCUE_FLOOR]
    assert [c["chunk_id"] for c in res["chunks"]] == ["answer"]


async def test_hybrid_search_logs_the_rescue(scripted, caplog):
    """The substitution is visible in the transcript, or the tuning looks applied."""
    scripted({search_tools._THRESHOLD_RESCUE_FLOOR: [{"chunk_id": "answer"}]})

    with caplog.at_level(logging.WARNING):
        await search_tools.hybrid_search(_Tools(similarity_threshold=0.55), query="q")

    assert "recall floor" in caplog.text


async def test_hybrid_search_keeps_a_threshold_that_discriminates(scripted):
    """A threshold that returns anything keeps its effect on the tail untouched."""
    rec = scripted({0.55: [{"chunk_id": "kept"}], search_tools._THRESHOLD_RESCUE_FLOOR: [{"chunk_id": "tail"}]})
    tools = _Tools(similarity_threshold=0.55, top_n=12, rerank_candidates_count=30)

    res = await search_tools.hybrid_search(tools, query="q")

    assert rec.thresholds == [0.55]
    assert [c["chunk_id"] for c in res["chunks"]] == ["kept"]


async def test_hybrid_search_does_not_retry_at_or_below_the_floor(scripted):
    """Nothing to fall back TO below the floor: a bare default reports an empty result."""
    rec = scripted({})
    tools = _Tools(similarity_threshold=search_tools._THRESHOLD_RESCUE_FLOOR)

    res = await search_tools.hybrid_search(tools, query="q")

    assert rec.thresholds == [search_tools._THRESHOLD_RESCUE_FLOOR]
    assert res["chunks"] == []


async def test_the_result_cache_is_keyed_by_the_narrowing_keywords(scripted):
    """The cached entry is the NARROWED pool, so the hint is part of the key."""
    rec = scripted({0.2: [{"chunk_id": "c1"}]})
    tools = _Tools(search_cache={})

    await search_tools.hybrid_search(tools, query="q", keywords="时限")
    await search_tools.hybrid_search(tools, query="q", keywords="工作日")
    await search_tools.hybrid_search(tools, query="q", keywords="时限")

    assert len(rec.thresholds) == 2, "a different keyword hint is a different result"
