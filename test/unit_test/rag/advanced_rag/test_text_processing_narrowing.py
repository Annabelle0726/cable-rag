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
"""Keyword narrowing must shrink passages; it must never drop one.

`_narrow_content` returned nothing for a plain-text passage that no keyword
occurred in, and `_narrow_by_keywords` then dropped those passages — while
structured passages (HTML tables, markdown pipe tables) were returned whole
regardless of the keywords. That asymmetry is what emptied the evidence for the
prose half of 《柔性拖链技术规格书.pdf》: the page-2 electrical/environmental table
survived every question, the 605-char page-1 chunk (jacket material, colour,
outer diameter, marking) was discarded whenever the formalized keywords did not
overlap it verbatim, and the assistant answered "知识库无相关资料" for facts the
page-1 chunk states outright. Server log of the failing run:

    [hybrid_search] Kept 2 of 5 passage(s) that actually mention the keywords.

The length guard is the second half of the fix: a short plain-text chunk IS the
evidence, so window-narrowing around one keyword hit used to cut the rest of it
away even when the chunk survived.
"""

import logging

import pytest

from rag.advanced_rag.harness.tools.text_processing import (
    _NARROWED,
    _NO_KEYWORD,
    _SHORT_PLAIN_TEXT_CHARS,
    _SHORT_WHOLE,
    _TABLE,
    _narrow_by_keywords,
    _narrow_content,
    _narrow_or_keep,
)

pytestmark = pytest.mark.p1

#: The page-1 chunk of 《柔性拖链技术规格书.pdf》 (605 chars in the index): the
#: jacket facts and the marking facts sit in one chunk, at opposite ends.
PAGE_1_PROSE = (
    "规格书编号：ZL5103011\n"
    "LONGTRONIC®柔性拖链DeviceNet总线电缆\n"
    "版本号：A/03\n"
    "1. 导体：24AWG 和 22AWG 两种规格，多股绞合。\n"
    "2. 绝缘：发泡 PE。\n"
    "3. 屏蔽：铝箔 + 镀锡铜编织网，覆盖率 ≥ 85%。\n"
    "4. 护套：PUR（聚氨酯），紫色，近似 RAL4001。\n"
    "5. 成品外径：6.60 ± 0.30 mm。\n"
    "6. 印字：LONGTRONIC DeviceNet 24AWG/22AWG 75°C 600V 阻燃耐油。\n"
)

PAGE_2_TABLE = (
    "<table><caption>电气性能(20℃)</caption>\n" "<tr><td>导体电阻</td><td>①24AWG ≤ 91.8 Ω/km</td></tr>\n" "<tr><td>工作温度</td><td>固定 -40 至 +80 ℃；移动 +5 至 +60 ℃</td></tr>\n" "</table>"
)


def _chunk(text: str, **extra) -> dict:
    chunk = {"id": "c", "content_with_weight": text}
    chunk.update(extra)
    return chunk


def test_prose_and_table_both_survive_keywords_that_match_neither():
    """The regression: zero keyword overlap must not cost a prose passage.

    English keywords stand in for any rewrite whose wording does not occur in the
    Chinese chunk (the pipeline rewrites the question before searching).
    """
    chunks = [
        _chunk(PAGE_1_PROSE),
        _chunk(PAGE_2_TABLE),
    ]

    kept = _narrow_or_keep(list(chunks), "jacket, colour, outer diameter", "hybrid_search")

    assert len(kept) == 2, "a passage no keyword occurs in must stay in the pool"
    prose = next(c for c in kept if "护套" in c["content_with_weight"])
    # Whole passage, not an excerpt: the 外径 and 印字 lines are the answers.
    assert "6.60" in prose["content_with_weight"]
    assert "印字" in prose["content_with_weight"]
    assert "PUR" in prose["content_with_weight"]


def test_short_prose_is_kept_whole_even_when_a_keyword_matches():
    """A short chunk keeps every line, not just the keyword sentence ±2."""
    payload, matched, mode = _narrow_content(PAGE_1_PROSE, ["护套"])

    assert mode == _SHORT_WHOLE
    assert matched is True
    assert len(PAGE_1_PROSE) <= _SHORT_PLAIN_TEXT_CHARS
    for fact in ("护套", "PUR", "RAL4001", "6.60", "印字", "屏蔽"):
        assert fact in payload, f"{fact} was cut out of a short passage"


def test_short_prose_still_highlights_the_keywords():
    payload, _matched, _mode = _narrow_content(PAGE_1_PROSE, ["护套"])

    assert "*护套*" in payload


def test_long_prose_without_any_keyword_is_kept_whole():
    long_prose = "这是一段与关键词无关的长文本。" * 200
    assert len(long_prose) > _SHORT_PLAIN_TEXT_CHARS

    payload, matched, mode = _narrow_content(long_prose, ["护套"])

    assert mode == _NO_KEYWORD
    assert matched is False
    assert payload == long_prose, "an untouched payload must not be rewritten"


def test_long_prose_with_a_keyword_is_still_narrowed():
    """The size optimisation survives: long prose is cut to its keyword window."""
    filler = "无关信息。" * 260
    long_prose = f"{filler}护套为 PUR 紫色。{filler}"
    assert len(long_prose) > _SHORT_PLAIN_TEXT_CHARS

    payload, matched, mode = _narrow_content(long_prose, ["护套"])

    assert mode == _NARROWED
    assert matched is True
    assert len(payload) < len(long_prose)
    assert "护套" in payload
    assert payload.startswith("...") and payload.endswith("...")


def test_table_is_returned_whole_without_any_keyword_hit():
    """The table exemption is deliberate (FRAMES Q408: a truncated table lost a row)."""
    payload, matched, mode = _narrow_content(PAGE_2_TABLE, ["jacket"])

    assert mode == _TABLE
    assert matched is True
    assert "-40 至 +80" in payload
    assert "+5 至 +60" in payload
    assert "91.8" in payload


def test_markdown_pipe_table_is_returned_whole():
    pipe_table = "\n".join(
        [
            "| 项目 | 数值 |",
            "| --- | --- |",
            "| 外径 | 6.60 mm |",
            "| 护套 | PUR |",
        ]
    )

    _payload, _matched, mode = _narrow_content(pipe_table, ["jacket"])

    assert mode == _TABLE


def test_retrieval_narrowing_never_reduces_the_passage_count():
    chunks = [_chunk(PAGE_1_PROSE), _chunk(PAGE_2_TABLE), _chunk("煤炭行业标准的相关条款。")]

    kept = _narrow_or_keep(list(chunks), "jacket, colour, outer diameter", "hybrid_search")

    assert len(kept) == 3


def test_keyword_filtering_callers_still_lose_non_matching_passages():
    """Graph exploration / wiki lookup / the grep fallback ARE keyword filters."""
    chunks = [_chunk(PAGE_1_PROSE), _chunk("煤炭行业标准的相关条款。")]

    kept = _narrow_by_keywords(list(chunks), "煤炭")

    assert len(kept) == 1
    assert "煤炭" in kept[0]["content_with_weight"]


def test_identical_payloads_are_still_deduplicated():
    chunks = [_chunk(PAGE_1_PROSE), _chunk(PAGE_1_PROSE)]

    kept = _narrow_or_keep(list(chunks), "jacket", "hybrid_search")

    assert len(kept) == 1, "identical passages are still collapsed"


def test_content_keys_are_mirrored_and_highlight_is_dropped():
    """Write-back rules: content_with_weight always, `content` only when present."""
    only_weight = _chunk(PAGE_1_PROSE)
    both = _chunk(f"{PAGE_1_PROSE}7. 备注：耐油。\n", content=f"{PAGE_1_PROSE}7. 备注：耐油。\n", highlight=["stale"])

    kept = _narrow_by_keywords([only_weight, both], "护套")

    assert len(kept) == 2
    assert "content" not in kept[0]
    assert kept[0]["content_with_weight"].startswith("...")
    assert kept[1]["content"] == kept[1]["content_with_weight"]
    assert "highlight" not in kept[1]


def test_narrow_or_keep_leaves_chunks_untouched_without_keywords():
    chunks = [_chunk(PAGE_1_PROSE)]

    assert _narrow_or_keep(list(chunks), "", "hybrid_search")[0] == chunks[0]


def test_narrow_or_keep_logs_the_keywords_and_the_per_mode_counts(caplog):
    """The log line has to name the keywords: without them a thin pool is
    indistinguishable from keywords that never matched anything."""
    chunks = [_chunk(PAGE_1_PROSE), _chunk(PAGE_2_TABLE), _chunk("煤炭行业标准的相关条款。")]

    with caplog.at_level(logging.INFO, logger="rag.advanced_rag.harness.tools.text_processing"):
        _narrow_or_keep(list(chunks), "jacket, colour, outer diameter", "hybrid_search")

    message = "\n".join(record.getMessage() for record in caplog.records)
    assert "[hybrid_search]" in message
    assert "3 passage(s) -> 3 kept" in message
    assert "keywords=[jacket, colour, outer diameter]" in message
    assert "structured kept whole" in message
