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
"""The seam between the pipeline and the real retriever.

Every other test in this directory drives a test double, and a double accepts
``**kwargs`` whether or not the caller spelled a keyword the way ``Dealer`` does.
These two checks keep the layer honest against the real thing: the keyword names
it sends, and the positional request they belong to.
"""

import inspect

import pytest

# `rag.nlp.search` reaches `common.settings` through `rag.utils.redis_conn`, and
# importing it first is what breaks that cycle from the outside.
import common.settings  # noqa: F401  (import order matters, see above)
from rag.nlp.search import Dealer  # noqa: E402
from rag.retrieval import multi_route  # noqa: E402

pytestmark = pytest.mark.p1

#: Keywords ``multi_route._retrieve_route`` sends on every call.
_SENT_KEYWORDS = (
    "vector_similarity_weight",
    "knn_top_k",
    "aggs",
    "highlight",
    "doc_ids",
    "rank_feature",
    "rerank_candidates_count",
    "allow_dense_fallback",
)


def test_every_keyword_the_routes_send_exists_on_dealer_retrieval():
    parameters = inspect.signature(Dealer.retrieval).parameters

    for name in _SENT_KEYWORDS + ("must_not",):
        assert name in parameters, f"Dealer.retrieval does not accept {name!r}"


def test_the_routes_fill_the_request_dealer_expects():
    """``(question, embd_mdl, tenant_ids, kb_ids, page, page_size, threshold)``."""
    parameters = list(inspect.signature(Dealer.retrieval).parameters)
    positional = parameters[1:7]

    assert positional == ["question", "embd_mdl", "tenant_ids", "kb_ids", "page", "page_size"]
    assert parameters[7] == "similarity_threshold"
    assert multi_route.RECALL_FLOOR > 0
