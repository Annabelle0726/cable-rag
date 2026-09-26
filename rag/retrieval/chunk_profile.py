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
"""What a retrieved passage IS - prose, a table, an image - and where it came from.

A standards corpus puts two very different things in the same index: normative
prose (``5.3.3 绝缘标称厚度应不小于 1.2mm``) and the bidder fill-in tables of a
专用技术规范 (technique-parameter tables whose cells repeat every parameter name
and unit the question asks about). The tables win the fused score - they are
dense in exactly the query's terms - and a plain top-N then hands the answer
model a window of nothing but tables, which is how a question whose clause IS in
the corpus comes back as "只有表格，没有正文规定".

The doc store already tells the two apart: ``doc_type_kwd`` is the field the
parsers write (``rag/flow/parser/parser.py`` sets ``"table"`` for a PDF table,
``"image"`` for a figure), and ``Dealer.retrieval`` copies it onto every returned
passage. This module reads that field, plus the HTML markup of tables emitted as
text, and derives the two groupings the context cut needs: the passage TYPE and
the DOCUMENT it belongs to.

Deliberately NOT used as a table signal: ``row_id``. It is the doc store's row
identity - Infinity answers ``row_id()`` for every row of every passage - so
treating it as "this is a table row" would relabel the whole corpus.
"""

from __future__ import annotations

import re
from typing import Sequence

#: ``doc_type_kwd`` values the parsers write.
DOC_TYPE_TABLE = "table"
DOC_TYPE_IMAGE = "image"
DOC_TYPE_VIDEO = "video"
_IMAGE_TYPES = frozenset({DOC_TYPE_IMAGE, DOC_TYPE_VIDEO})

#: A table emitted as text (deepdoc renders a PDF table as HTML and some
#: pipelines keep the markup). Used only when ``doc_type_kwd`` says nothing.
_TABLE_MARKUP_RE = re.compile(r"<table[\s>]|<t[dh][\s>]|<tr[\s>]", re.IGNORECASE)


def doc_type(chunk: dict) -> str:
    return str(chunk.get("doc_type_kwd") or "").strip().lower()


def _content(chunk: dict) -> str:
    return str(chunk.get("content_with_weight") or chunk.get("content") or "")


def is_table_chunk(chunk: dict) -> bool:
    """A tabular passage: the parser's own label, or HTML table markup."""
    if doc_type(chunk) == DOC_TYPE_TABLE:
        return True
    return bool(_TABLE_MARKUP_RE.search(_content(chunk)))


def is_image_chunk(chunk: dict) -> bool:
    """A figure: labelled as one, or carrying an image with no text to read."""
    if doc_type(chunk) in _IMAGE_TYPES:
        return True
    if not _content(chunk).strip():
        return bool(chunk.get("image_id") or chunk.get("img_id") or chunk.get("image"))
    return False


def is_prose_chunk(chunk: dict) -> bool:
    """A passage a normative clause can be read out of."""
    return not is_table_chunk(chunk) and not is_image_chunk(chunk)


def document_key(chunk: dict) -> str:
    """The document a passage came from (``doc_id``, else its file name)."""
    for name in ("doc_id", "docnm_kwd", "docnm", "document_name"):
        value = chunk.get(name)
        if value:
            return str(value)
    return ""


def document_id(chunk: dict) -> str:
    """The doc-store id only - what a ``doc_ids`` scope can be built from.

    Distinct from :func:`document_key`, which falls back to the file name for
    grouping: a file name is fine for counting passages per document, but handing
    one to the doc store as a ``doc_id`` filter would match nothing.
    """
    return str(chunk.get("doc_id") or "")


def document_name(chunk: dict) -> str:
    """The document's file name/title as the transcript shows it."""
    for name in ("docnm_kwd", "docnm", "document_name"):
        value = chunk.get(name)
        if value:
            return str(value)
    return ""


#: A standard designation in a file name or a question: ``Q/GDW 73237.1-2026``,
#: ``GB/T 19666``, ``DL/T 5221``. ``_`` and spaces are interchangeable with the
#: slash, because an archived file is routinely named ``Q_GDW_73237.2-2026_…``.
_STANDARD_DESIGNATION_RE = re.compile(
    r"\b(?:Q\s*/?\s*GDW|GB\s*/?\s*T|GB|DL\s*/?\s*T|JB\s*/?\s*T|NB\s*/?\s*T|YD\s*/?\s*T|T\s*/?\s*CEC|JJG|JG)\s*\d{2,}(?:\.\d+)?",
    re.IGNORECASE,
)

#: Names that say "this file IS the standard the corpus is about", without a
#: designation of their own. Deliberately NOT a list of auxiliary names (抽检/
#: 检验/试验/方案…): a corpus is free to name a standard 《…验收规范》, and a
#: blacklist would then hide the standard itself. The rule is positive - a file
#: either carries a standard designation (or one of these tier names) or it does
#: not - so it generalises past the corpus that produced it.
CORE_DOCUMENT_NAME_CUES = ("采购标准", "通用技术规范", "专用技术规范")


def _normalized_name(text: str) -> str:
    return re.sub(r"[\s_]+", " ", str(text or "")).strip()


def standard_designations(text: str) -> set[str]:
    """Every standard designation a file name or question carries, normalized.

    Normalization drops the separators so ``Q/GDW73237.1`` in a question matches
    ``Q_GDW_73237.1-2026`` in a file name.
    """
    found = set()
    for match in _STANDARD_DESIGNATION_RE.finditer(_normalized_name(text)):
        found.add(re.sub(r"[\s/]+", "", match.group(0)).upper())
    return found


def core_document_score(chunk_or_name) -> int:
    """How strongly a document presents itself as the corpus's standard.

    2 = carries a standard designation, 1 = carries a tier name (采购标准 /
    通用技术规范 / 专用技术规范), 0 = neither.
    """
    name = chunk_or_name if isinstance(chunk_or_name, str) else document_name(chunk_or_name)
    if not name:
        return 0
    score = 0
    if standard_designations(name):
        score += 2
    normalized = _normalized_name(name)
    if any(cue in normalized for cue in CORE_DOCUMENT_NAME_CUES):
        score += 1
    return score


def resolve_core_documents(chunks: Sequence[dict], question: str = "") -> set[str]:
    """The documents that ARE the standard this question is about, if any.

    Two rules, in order:

    1. the question names a designation (``Q/GDW 73237.1``) - the documents whose
       file name or whose own passage text carries it are the core;
    2. otherwise every document whose name carries a designation or a tier name.

    An empty result means the corpus does not advertise a standard at all (a
    folder of supplier datasheets, product manuals, test reports). Callers must
    then leave document-level policy alone rather than guess which file is
    "main" - guessing is how an auxiliary working document gets promoted or a
    legitimate single-document answer gets truncated.
    """
    by_document: dict[str, list[dict]] = {}
    for chunk in chunks or []:
        key = document_key(chunk)
        if key:
            by_document.setdefault(key, []).append(chunk)
    if not by_document:
        return set()

    named = standard_designations(question)
    if named:
        hit = {key for key, group in by_document.items() if standard_designations(document_name(group[0])) & named or any(named & standard_designations(_content(chunk)) for chunk in group)}
        if hit:
            return hit

    return {key for key, group in by_document.items() if core_document_score(group[0]) > 0}


def summarize(chunks: Sequence[dict]) -> str:
    """One line describing a passage pool or a context: types and provenance."""
    chunks = list(chunks or [])
    tables = sum(1 for chunk in chunks if is_table_chunk(chunk))
    images = sum(1 for chunk in chunks if is_image_chunk(chunk))
    prose = sum(1 for chunk in chunks if is_prose_chunk(chunk))
    documents = {document_key(chunk) for chunk in chunks if document_key(chunk)}
    return f"{len(chunks)} passage(s): {prose} prose / {tables} table / {images} image from {len(documents)} document(s)"


def document_breakdown(chunks: Sequence[dict], limit: int = 3) -> str:
    """``Q/GDW 73237.1…pdf x5, 抽检工作规范.pdf x4`` - who filled the context.

    The measurement that started this: nine recalled passages, seven of them from
    one auxiliary working document (22,684 characters) and two from the standard
    the question was about (1,130 characters). A count per document makes that
    visible in one line of the transcript.
    """
    counts: dict[str, int] = {}
    for chunk in chunks or []:
        key = document_name(chunk) or document_key(chunk) or "?"
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    shown = [f"{name} x{count}" for name, count in ordered[:limit]]
    if len(ordered) > limit:
        shown.append(f"+{len(ordered) - limit} more")
    return ", ".join(shown)
