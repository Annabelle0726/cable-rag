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
"""Multi-route retrieval for multi-dimensional questions.

``retrieve_multi_route`` is the entry point a chat turn calls; the three modules
underneath it are independently usable and independently testable:

* :mod:`~rag.retrieval.decomposition` — question -> atomic sub-queries (module A);
* :mod:`~rag.retrieval.multi_route` — concurrent hybrid routes + merge (module B);
* :mod:`~rag.retrieval.rerank` — rerank against the original question + cut (module C).
"""

from rag.retrieval.decomposition import (
    MAX_SUB_QUERIES,
    decompose_question,
    looks_composite,
    parse_sub_queries,
    strip_section_references,
)
from rag.retrieval.chunk_profile import (
    document_key,
    is_image_chunk,
    is_prose_chunk,
    is_table_chunk,
    summarize,
)
from rag.retrieval.decomposition import (
    CLAUSE_ROUTE_ANCHOR,
    clause_route,
    seeks_clause,
)
from rag.retrieval.multi_route import (
    DEFAULT_ROUTES_TOP_K,
    DEFAULT_VECTOR_SIMILARITY_WEIGHT,
    RECALL_FLOOR,
    ROUTES_TOP_K_RECOMMENDED,
    RouteResult,
    merge_route_hits,
    multi_route_retrieve,
    resolve_routes_top_k,
)
from rag.retrieval.pipeline import empty_kbinfos, retrieve_multi_route
from rag.retrieval.rerank import (
    DEFAULT_FINAL_TOP_N,
    FINAL_TOP_N_RECOMMENDED,
    MAX_TABLE_SHARE,
    MIN_PROSE_PASSAGES,
    TABLE_PENALTY,
    DiversityPolicy,
    apply_type_penalty,
    dedupe_chunks,
    ensure_route_coverage,
    rerank_chunks,
    resolve_final_top_n,
    routes_of,
    select_context,
)

__all__ = [
    "CLAUSE_ROUTE_ANCHOR",
    "DEFAULT_FINAL_TOP_N",
    "DEFAULT_ROUTES_TOP_K",
    "DEFAULT_VECTOR_SIMILARITY_WEIGHT",
    "FINAL_TOP_N_RECOMMENDED",
    "MAX_SUB_QUERIES",
    "MAX_TABLE_SHARE",
    "MIN_PROSE_PASSAGES",
    "RECALL_FLOOR",
    "ROUTES_TOP_K_RECOMMENDED",
    "TABLE_PENALTY",
    "DiversityPolicy",
    "RouteResult",
    "apply_type_penalty",
    "clause_route",
    "dedupe_chunks",
    "decompose_question",
    "document_key",
    "empty_kbinfos",
    "ensure_route_coverage",
    "is_image_chunk",
    "is_prose_chunk",
    "is_table_chunk",
    "looks_composite",
    "merge_route_hits",
    "multi_route_retrieve",
    "parse_sub_queries",
    "rerank_chunks",
    "resolve_final_top_n",
    "resolve_routes_top_k",
    "retrieve_multi_route",
    "routes_of",
    "seeks_clause",
    "select_context",
    "strip_section_references",
    "summarize",
]
