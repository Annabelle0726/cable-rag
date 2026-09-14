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
