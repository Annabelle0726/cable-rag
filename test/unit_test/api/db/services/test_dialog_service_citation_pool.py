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
"""A citation marker's number must be resolved against the pool it was numbered on.

The agentic compose stage labels its evidence ``ID: 1 … ID: n`` over a narrowed
list and records it as ``_rag_cite_chunks``; the reference handed to the client
used to come from the chat-side accumulator instead. Measured over the stored
history: answers reached ``[ID:5]`` against a 3-chunk pool, so the chip opened a
passage the model had not read.
"""

from api.db.services.dialog_service import _citation_pool


def _chunk(name):
    return {"chunk_id": name, "doc_id": f"doc-{name}", "content_with_weight": f"passage {name}"}


def _kbinfos(chunks, doc_aggs=None):
    return {
        "chunks": [_chunk(c) for c in chunks],
        "doc_aggs": doc_aggs or [{"doc_id": f"doc-{c}", "doc_name": f"{c}.doc", "count": 1} for c in chunks],
    }


class TestTheNumberingBasisWins:
    def test_narrowed_prompt_pool_replaces_the_accumulator(self):
        # The model was prompted with three passages, which it numbered 1..3, while
        # the accumulator still holds the whole retrieval.
        pool = _citation_pool(_kbinfos(["a", "b", "c", "d", "e"]), [_chunk("a"), _chunk("b"), _chunk("c")])

        assert [c["chunk_id"] for c in pool["chunks"]] == ["a", "b", "c"]

    def test_marker_five_now_names_nothing_instead_of_the_wrong_passage(self):
        pool = _citation_pool(_kbinfos(["a", "b", "c", "d", "e"]), [_chunk("a"), _chunk("b"), _chunk("c")])

        # `[ID:5]` used to resolve against the accumulator's fifth chunk; it is now
        # out of range, which the renderer reports as an unopenable marker.
        assert not (0 <= 5 - 1 < len(pool["chunks"]))

    def test_accumulator_is_used_when_no_prompt_pool_was_recorded(self):
        pool = _citation_pool(_kbinfos(["a", "b"]), None)

        assert [c["chunk_id"] for c in pool["chunks"]] == ["a", "b"]

    def test_empty_list_falls_back_too(self):
        pool = _citation_pool(_kbinfos(["a"]), [])

        assert [c["chunk_id"] for c in pool["chunks"]] == ["a"]


class TestThePoolIsACopy:
    def test_editing_the_pool_does_not_touch_the_source(self):
        source = _kbinfos(["a"])
        probe = _chunk("b")
        pool = _citation_pool(source, [probe])

        # `decorate_answer` strips the vectors from the pool it returns; that must
        # not reach the chunks the pipeline still holds.
        pool["chunks"][0]["vector"] = None
        probe["vector"] = [0.1]

        assert "vector" not in source["chunks"][0]
        assert pool["chunks"][0] is not probe
