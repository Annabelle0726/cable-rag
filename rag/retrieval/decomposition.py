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
"""Module A — sub-query decomposition for multi-dimensional questions.

One retrieval statement per question does not survive a question that asks for
several parameters at once. Both legs of the hybrid score are diluted by extra
dimensions:

* the text leg is a query-RECALL ratio (``Qryr.token_similarity`` divides the
  matched term weight by the query's TOTAL term weight), so a passage covering
  one of four asked-for parameters scores at best a quarter of the text weight;
* the vector leg is one embedding of the whole sentence, whose centroid drifts
  away from every single-parameter clause.

The result is a pool whose members sit under the assistant's
``similarity_threshold``: the knowledge base contains chapter 5's thickness
clause and chapter 6's routine-test clause, and neither reaches the answer.

This module splits such a question into atomic sub-queries, and - separately
from the LLM call - strips structural hierarchy references ("第5章", "5.3.3",
"附录A") out of a search statement. A chapter number is a coordinate in the
document outline, not content the retriever should be asked to match; left in
the statement it takes weight away from the business entity next to it.

Everything here is best-effort: the LLM node is an optimization, and every
failure path returns "no sub-queries" so the caller retrieves the original
question exactly as before.
"""

from __future__ import annotations

import logging
import re

from rag.prompts.generator import PROMPT_JINJA_ENV, gen_json
from rag.prompts.template import load_prompt

_LOG = logging.getLogger(__name__)

DECOMPOSITION_PROMPT = load_prompt("sub_query_decomposition")

#: Upper bound on the sub-queries one question may fan out into. Total routes
#: are this plus the original question, and every route is one retrieval round
#: trip, so the cap is a latency budget as much as a quality knob.
MAX_SUB_QUERIES = 4

#: A sub-query longer than this is a paraphrase of the original question, not an
#: atomic one; the model occasionally echoes the whole sentence back.
MAX_SUB_QUERY_CHARS = 120

#: ``第5章`` / ``第 5.3 节`` / ``第五章`` / ``第3条`` / ``第2款`` / ``第4部分``.
_SECTION_WORD_RE = re.compile(r"第\s*[0-9０-９一二三四五六七八九十百零]+(?:\s*[.．]\s*\d+)*\s*(?:章|节|条|款|部分|篇|项)")

#: ``附录A`` / ``附录 B`` / ``附录3``.
_APPENDIX_RE = re.compile(r"附录\s*[A-Za-z0-9一二三四五六七八九十]+")

#: A dotted section number glued to a section word (``第5章5.3.3``). The
#: lookbehind is what keeps this from touching data values: ``0.6/1kV`` and
#: ``1.2mm`` are not preceded by a section word, so they are never stripped.
_GLUED_SECTION_NUMBER_RE = re.compile(r"(?<=[章节条款篇项])\s*\d+(?:\.\d+){1,4}")

#: A dotted section number opening the statement (``5.3.3 绝缘标称厚度是多少``).
_LEADING_SECTION_NUMBER_RE = re.compile(r"^\s*\d+(?:\.\d+){1,4}\s*[、,，:：.．]?\s*")

#: Conjunctions that put two information needs in one sentence. ``和`` needs the
#: lookbehind because it also builds single words (饱和/柔和/温升和谐波...).
_CONJUNCTION_RE = re.compile(r"[、；;]|(?<![饱柔混搅调缓总均附])和|与|及|以及|还有|同时|分别|各自|对比|比较|区别|不同|差异")

#: Interrogative markers. Two or more of them in one sentence is a second
#: information need even without a conjunction ("厚度是多少 电阻又是多少").
_INTERROGATIVE_RE = re.compile(r"多少|多大|是什么|有哪些|如何|怎样|要求|规定|标准|参数|数值|类型|区别|几")

_WHITESPACE_RE = re.compile(r"\s+")


def strip_section_references(text: str) -> str:
    """Drop structural hierarchy references from a search statement.

    ``"第5章 5.3.3 绝缘标称厚度和绝缘电阻分别是多少"`` becomes
    ``"绝缘标称厚度和绝缘电阻分别是多少"``. Only outline coordinates are
    removed - section words, appendix labels (with an optional glued section
    number), and a leading dotted number. Numeric data (``0.6/1kV``, ``1.2mm``,
    ``20个工作日``) is deliberately left alone: it is content, and the BM25 leg
    needs it verbatim.

    A statement that is *only* a section reference (``"第5章"``) keeps its
    original text rather than collapsing to the empty string.
    """
    original = str(text or "")
    stripped = _GLUED_SECTION_NUMBER_RE.sub(" ", original)
    stripped = _SECTION_WORD_RE.sub(" ", stripped)
    stripped = _APPENDIX_RE.sub(" ", stripped)
    stripped = _LEADING_SECTION_NUMBER_RE.sub("", stripped)
    stripped = _WHITESPACE_RE.sub(" ", stripped).strip(" 　的,，、;；:：")
    return stripped if len(stripped) >= 2 else original.strip()


def looks_composite(question: str) -> bool:
    """Whether a question carries more than one information need.

    A cheap deterministic gate in front of the LLM node: a single-parameter
    question ("标称厚度是多少") has exactly one route and keeps the retrieval
    behaviour it has today, so the decomposition call and its extra round trips
    are spent only where they can change the outcome.

    The gate is deliberately recall-biased - a false positive costs one LLM call
    and a route that returns the same chunks, while a false negative leaves a
    composite question on the diluted single-route path.
    """
    text = _WHITESPACE_RE.sub(" ", str(question or "")).strip()
    if not text:
        return False
    if _CONJUNCTION_RE.search(text):
        return True
    return len(_INTERROGATIVE_RE.findall(text)) >= 2


def _normalized(text: str) -> str:
    return _WHITESPACE_RE.sub("", str(text or "")).lower()


def _sub_query_text(item) -> str:
    if isinstance(item, dict):
        for key in ("query", "question", "sub_query", "text"):
            value = item.get(key)
            if value:
                return str(value)
        return ""
    return str(item or "")


def parse_sub_queries(result, question: str, max_sub_queries: int = MAX_SUB_QUERIES) -> list[str]:
    """Normalize an LLM decomposition response into clean sub-queries.

    Accepts the documented ``{"sub_queries": [...]}`` shape (plus the common
    synonyms a model may emit), the bare list ``json_repair`` produces when the
    model answers with an array, and list members written as dicts. Returns the
    sub-queries with section references stripped, exact duplicates removed, and -
    because a sub-query that repeats the original question adds a round trip and
    no recall - the original question itself dropped.
    """
    if isinstance(result, dict):
        raw = []
        for key in ("sub_queries", "sub_questions", "queries", "questions"):
            value = result.get(key)
            if isinstance(value, list):
                raw = value
                break
    elif isinstance(result, list):
        raw = result
    else:
        return []

    original_key = _normalized(question)
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        text = _WHITESPACE_RE.sub(" ", _sub_query_text(item)).strip()
        if not text or len(text) < 2:
            continue
        if len(text) > MAX_SUB_QUERY_CHARS:
            text = text[:MAX_SUB_QUERY_CHARS].strip()
        text = strip_section_references(text)
        key = _normalized(text)
        if not key or key == original_key or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= max_sub_queries:
            break
    return out


async def decompose_question(chat_mdl, question: str, max_sub_queries: int = MAX_SUB_QUERIES) -> list[str]:
    """Split a composite question into atomic sub-queries.

    Returns an empty list - never raises - when there is no chat model, when the
    question is empty, or when the model call or its JSON response cannot be
    used. The caller then searches the original question alone, which is exactly
    the behaviour that predates this module.
    """
    question = _WHITESPACE_RE.sub(" ", str(question or "")).strip()
    if not question or chat_mdl is None or max_sub_queries <= 0:
        return []
    try:
        rendered = PROMPT_JINJA_ENV.from_string(DECOMPOSITION_PROMPT).render(question=question, max_sub_queries=max_sub_queries)
        result = await gen_json(rendered, "Output:\n", chat_mdl)
    except Exception as exc:  # noqa: BLE001 - decomposition is an optimization
        _LOG.warning("[Decompose] failed for %r: %s", question[:80], exc)
        return []
    sub_queries = parse_sub_queries(result, question, max_sub_queries)
    _LOG.info("[Decompose] %r -> %s", question[:80], sub_queries)
    return sub_queries
