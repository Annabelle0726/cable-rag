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


def summarize(chunks: Sequence[dict]) -> str:
    """One line describing a passage pool or a context: types and provenance."""
    chunks = list(chunks or [])
    tables = sum(1 for chunk in chunks if is_table_chunk(chunk))
    images = sum(1 for chunk in chunks if is_image_chunk(chunk))
    prose = sum(1 for chunk in chunks if is_prose_chunk(chunk))
    documents = {document_key(chunk) for chunk in chunks if document_key(chunk)}
    return f"{len(chunks)} passage(s): {prose} prose / {tables} table / {images} image from {len(documents)} document(s)"
