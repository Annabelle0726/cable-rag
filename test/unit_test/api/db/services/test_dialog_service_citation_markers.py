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
"""A citation marker the client cannot open must not reach the answer.

`[ID:0]` names nothing (the numbering is 1-based), `[ID:9]` names nothing when the
pool is shorter, and a merged range `[ID:1-3]` names no single chunk. Production
showed both: an answer citing `[ID:5]` against a 3-chunk pool, and another citing
`[ID:0]`. The renderer now shows such a marker as an unopenable `[n]`, but the
answer itself should not carry it — Go drops it (`service.ResolveCitationMarkers`)
and these pin the Python half.
"""

from api.db.services.dialog_service import (
    repair_bad_citation_formats,
    resolve_citation_markers,
)


def _kbinfos(chunks: int):
    return {"chunks": [{"chunk_id": f"c{i}", "doc_id": f"d{i}"} for i in range(chunks)]}


class TestMarkersThatNameNothingAreDropped:
    def test_marker_zero_is_dropped(self):
        # 1-based numbering: there is no chunk 0.
        assert resolve_citation_markers("结论 [ID:0]。", 6) == "结论 。"

    def test_marker_past_the_pool_is_dropped(self):
        assert resolve_citation_markers("结论 [ID:9]。", 6) == "结论 。"

    def test_marker_at_the_last_position_is_kept(self):
        assert resolve_citation_markers("结论 [ID:6]。", 6) == "结论 [ID:6]。"

    def test_a_run_of_mostly_valid_markers_keeps_only_the_valid_ones(self):
        # The reported shape: three citations where only two resolve.
        assert (
            resolve_citation_markers("以该表为准 [ID:1][ID:3][ID:9]。", 6)
            == "以该表为准 [ID:1][ID:3]。"
        )

    def test_bare_bracketed_numbers_are_left_alone(self):
        # A bare `[2024]` is as likely to be a year or a footnote as a citation;
        # deleting text the reader wanted is worse than an unopenable marker.
        # Go makes the same distinction (canonicalIDMarkerPattern).
        assert resolve_citation_markers("参见 [2024] 年报告。", 6) == "参见 [2024] 年报告。"

    def test_an_empty_pool_drops_every_canonical_marker(self):
        assert resolve_citation_markers("结论 [ID:1]。", 0) == "结论 [ID:1]。"

    def test_markers_are_unchanged_when_the_pool_is_not_known(self):
        # chunk_count 0 means "no pool to judge against"; the caller decides what
        # to do with markers it cannot resolve.
        assert resolve_citation_markers("结论 [ID:1]。", 0) == "结论 [ID:1]。"


class TestMergedRanges:
    def test_a_valid_range_expands_so_its_citations_survive(self):
        assert (
            resolve_citation_markers("见表 [ID:1-3]。", 6)
            == "见表 [ID:1][ID:2][ID:3]。"
        )

    def test_a_reversed_range_expands_too(self):
        assert resolve_citation_markers("[ID:3-1]。", 6) == "[ID:1][ID:2][ID:3]。"

    def test_a_range_past_the_pool_is_dropped(self):
        assert resolve_citation_markers("见表 [ID:2-9]。", 6) == "见表 。"

    def test_a_range_starting_before_the_first_chunk_is_dropped(self):
        assert resolve_citation_markers("见表 [ID:0-2]。", 6) == "见表 。"


class TestBadFormatsUseTheSameRule:
    # `(ID:3)` is one of the malformed shapes BAD_CITATION_PATTERNS repairs (the
    # markdown-bold variant `(**ID:3**)` is repaired a layer earlier, in the
    # agentic tool).
    def test_an_in_range_bad_shape_is_normalised(self):
        answer, idx = repair_bad_citation_formats("见表 (ID:3)。", _kbinfos(6), set())

        assert answer == "见表 [ID:3]。"
        # `idx` holds 0-based pool indexes: marker 3 is the third chunk.
        assert idx == {2}

    def test_the_basis_is_stated_rather_than_guessed(self):
        # Same marker, same pool, two numbering bases: 1-based means "the third
        # chunk", 0-based means "the fourth".
        _, one_based = repair_bad_citation_formats("见表 (ID:3)。", _kbinfos(6), set())
        _, zero_based = repair_bad_citation_formats("见表 (ID:3)。", _kbinfos(6), set(), one_based=False)

        assert one_based == {2}
        assert zero_based == {3}

    def test_an_out_of_range_bad_shape_is_dropped_not_kept(self):
        answer, idx = repair_bad_citation_formats("见表 (ID:9)。", _kbinfos(6), set())

        assert answer == "见表 。"
        assert idx == set()

    def test_marker_zero_is_dropped_in_the_bad_shape_too(self):
        answer, idx = repair_bad_citation_formats("见表 (ID:0)。", _kbinfos(6), set())

        assert answer == "见表 。"
        assert idx == set()

    def test_the_zero_based_basis_keeps_its_own_numbering(self):
        # `insert_citations` emits 0-based positions, so `[ID:0]` is its first
        # chunk and `[ID:6]` is past a 6-chunk pool.
        answer, idx = repair_bad_citation_formats("见表 (ID:0)。", _kbinfos(6), set(), one_based=False)

        assert answer == "见表 [ID:0]。"
        assert idx == {0}

        answer, idx = repair_bad_citation_formats("见表 (ID:6)。", _kbinfos(6), set(), one_based=False)

        assert answer == "见表 。"
        assert idx == set()

    def test_zero_based_markers_resolve_against_the_same_basis(self):
        assert resolve_citation_markers("见表 [ID:0][ID:6]。", 6, one_based=False) == "见表 [ID:0]。"
