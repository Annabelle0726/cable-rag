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

import pytest

from common.text_utils import CONVERSATION_TITLE_MAX_CHARS, normalize_conversation_title


@pytest.mark.p2
def test_keeps_a_clean_title_untouched():
    assert normalize_conversation_title("5芯电缆色标合规") == "5芯电缆色标合规"


@pytest.mark.p2
@pytest.mark.parametrize(
    "raw,expected",
    [
        ('"5芯电缆色标合规。"', "5芯电缆色标合规"),
        ("Title: 5芯电缆色标合规", "5芯电缆色标合规"),
        ("标题：5芯电缆色标合规", "5芯电缆色标合规"),
        ("**5芯电缆色标合规**", "5芯电缆色标合规"),
        ("- 5芯电缆色标合规", "5芯电缆色标合规"),
        ("  5芯电缆色标合规  ", "5芯电缆色标合规"),
    ],
)
def test_strips_the_decoration_models_add(raw, expected):
    assert normalize_conversation_title(raw) == expected


@pytest.mark.p2
def test_keeps_only_the_first_line():
    assert normalize_conversation_title("5芯电缆色标合规\n说明：这是标题") == "5芯电缆色标合规"


@pytest.mark.p2
@pytest.mark.parametrize("raw", [None, "", "   ", "\n\n"])
def test_returns_empty_for_nothing_usable(raw):
    assert normalize_conversation_title(raw) == ""


@pytest.mark.p2
def test_clamps_a_runaway_title():
    title = normalize_conversation_title("x" * 120)

    assert len(title) == CONVERSATION_TITLE_MAX_CHARS
    assert title == "x" * CONVERSATION_TITLE_MAX_CHARS


@pytest.mark.p2
def test_honours_a_custom_clamp():
    assert normalize_conversation_title("abcdefghij", max_chars=4) == "abcd"


@pytest.mark.p2
@pytest.mark.parametrize(
    "raw,expected",
    [
        # The titler is told to drop the year, because the characters it costs are
        # worth more on the material model and the indicator.
        ("Q/GDW 73289.2-2026 PVC/E 热稳定性", "Q/GDW 73289.2 PVC/E 热稳定性"),
        ("GB/T 3956-2008 5芯导体直流电阻", "GB/T 3956 5芯导体直流电阻"),
        ("IEC 60502-1:2014 交联电缆", "IEC 60502-1 交联电缆"),
        ("Q/GDW 73289.2—2026 PVC/E 热稳定性", "Q/GDW 73289.2 PVC/E 热稳定性"),
        ("Q/GDW  73289.2 - 2026 PVC/E", "Q/GDW 73289.2 PVC/E"),
    ],
)
def test_drops_the_year_of_a_standard_number(raw, expected):
    assert normalize_conversation_title(raw) == expected


@pytest.mark.p2
@pytest.mark.parametrize(
    "raw,expected",
    [
        # A year standing on its own is content, not decoration: the strip is anchored
        # on a digit followed by a separator, and a leading year has neither.
        ("2026年电缆采购计划", "2026年电缆采购计划"),
        # A hyphenated figure that is not a year is part of the designation.
        ("YJV22-4×185 交货期", "YJV22-4×185 交货期"),
        ("GB/T 3956 导体结构", "GB/T 3956 导体结构"),
    ],
)
def test_leaves_a_year_that_is_not_suffix_to_a_designation(raw, expected):
    assert normalize_conversation_title(raw) == expected


@pytest.mark.p2
def test_drops_a_year_suffix_from_any_designation():
    # A four-digit year hyphenated onto an alphanumeric token is treated as a year
    # wherever it appears, not only after a standard number: no cable designation in
    # this knowledge base ends in `-YYYY`, and the characters are worth more on the
    # model and the indicator.
    assert normalize_conversation_title("YJV22-2026 交货期") == "YJV22 交货期"


@pytest.mark.p2
def test_the_year_is_dropped_before_the_clamp():
    # 26 characters with the year, 21 without: dropping it first is what keeps the
    # model's own wording instead of a truncated tail.
    raw = "Q/GDW 73289.2-2026 PVC/E 热稳定性"

    assert len(raw) > CONVERSATION_TITLE_MAX_CHARS
    assert normalize_conversation_title(raw) == "Q/GDW 73289.2 PVC/E 热稳定性"
