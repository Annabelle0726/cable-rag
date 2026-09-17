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
"""Citation markers are 1-based, so collecting cited chunks must shift by one.

``kb_prompt`` labels the evidence blocks it hands to the model 1-based
("ID: 1" … "ID: n"), which is why an answer may cite ``[ID:5]`` for a five-chunk
pool. Reading that number as a pool index (the previous behaviour) dropped the
citation — ``5 < 5`` was false — so the chunk was neither marked recalled nor
counted as a cited document, and the reference list handed back to the client
lost it.
"""

import warnings

import pytest

from api.db.services.dialog_service import cited_chunk_indexes

warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    category=UserWarning,
)

CHUNK_COUNT = 5


@pytest.mark.p2
@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        # 1-based marker -> 0-based pool index
        ("见表1 [ID:1]。", {0}),
        ("见表1 [ID:4]。", {3}),
        ("老化前抗张强度为 10.0 N/mm² [ID:5]。", {4}),
        # several markers, de-duplicated
        ("[ID:2] 与 [ID:4] 均适用，见 [ID:2]。", {1, 3}),
        # bare markers without the ID: prefix
        ("依据 [5]", {4}),
        # Arabic-Indic digits are normalized before parsing
        ("依据 [ID:٥]", {4}),
        # outside the pool: dropped, never clamped
        ("[ID:6]", set()),
        ("[ID:99]", set()),
        # marker 0 is not a valid 1-based citation
        ("[ID:0]", set()),
        # no markers at all
        ("没有任何引用。", set()),
        ("", set()),
    ],
)
def test_cited_chunk_indexes_maps_one_based_markers_to_pool_indexes(answer, expected):
    assert cited_chunk_indexes(answer, CHUNK_COUNT) == expected


@pytest.mark.p2
def test_cited_chunk_indexes_is_empty_for_an_empty_pool():
    assert cited_chunk_indexes("见表1 [ID:1]。", 0) == set()
