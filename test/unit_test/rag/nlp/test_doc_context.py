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

import pytest

from rag import nlp
from rag.nlp import doc_context

#: The real file name from the reported failure: the file is a procurement-standard
#: PDF whose body is Q/GDW 73289.2-2026. Sliced away from the cover page, the table
#: chunks kept only this name, and the answering model concluded the knowledge base
#: held "only a procurement standard" rather than the Q/GDW body it was asked about.
INCIDENT_DOC_NAME = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2.pdf"
INCIDENT_DOC_TITLE = "450/750V聚氯乙烯绝缘电缆采购标准+第2部分：专用技术规范_2"


class _StubRagTokenizer:
    """Stand-in for the C++ rag_tokenizer binding: deterministic, dictionary-free."""

    language = None

    class tokenizer:  # noqa: N801 - mirrors the binding's namespace
        @staticmethod
        def set_language(language):
            _StubRagTokenizer.language = language

    @staticmethod
    def tokenize(text):
        return "tk:" + text

    @staticmethod
    def fine_grained_tokenize(text):
        return "fg:" + text


@pytest.fixture(autouse=True)
def stub_rag_tokenizer(monkeypatch):
    """Keep the prefix tokenization hermetic: no C++ tokenizer binding needed."""
    monkeypatch.setattr(nlp, "rag_tokenizer", _StubRagTokenizer)
    _StubRagTokenizer.language = None
    return _StubRagTokenizer


@pytest.mark.p2
def test_apply_document_context_binds_standard_id_to_every_chunk():
    chunks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准\n第2部分：专用技术规范"},
        {"content_with_weight": "表1 技术参数特性表\n型号\t芯数\t标称截面\nYJV\t3\t240", "doc_type_kwd": "table"},
        {"content_with_weight": "5.1 电缆结构\n导体应符合GB/T 3956-2008的规定。"},
    ]

    prefixed = doc_context.apply_document_context(chunks, INCIDENT_DOC_NAME)

    assert prefixed == 3
    # Every chunk names the standard the document actually contains — including the
    # table chunk, which no longer looks like an unrelated procurement table.
    for chunk in chunks:
        assert chunk["content_with_weight"].startswith("[标准号: Q/GDW 73289.2-2026 | ")
        assert "文档: " + INCIDENT_DOC_TITLE in chunk["content_with_weight"]

    assert chunks[0]["content_with_weight"].startswith("[标准号: Q/GDW 73289.2-2026 | 文档: " + INCIDENT_DOC_TITLE + "] ")
    assert chunks[1]["content_with_weight"].startswith("[标准号: Q/GDW 73289.2-2026 | 文档: " + INCIDENT_DOC_TITLE + " | 章节: 表1 技术参数特性表] ")
    # A later clause keeps its own number, not the one referenced inside its body.
    assert chunks[2]["content_with_weight"].startswith("[标准号: Q/GDW 73289.2-2026 | 文档: " + INCIDENT_DOC_TITLE + " | 章节: 5.1 电缆结构] ")
    # The original body survives the prefix untouched.
    assert chunks[1]["content_with_weight"].endswith("型号\t芯数\t标称截面\nYJV\t3\t240")


@pytest.mark.p2
def test_apply_document_context_prepends_prefix_tokens_to_the_indexed_fields(stub_rag_tokenizer):
    chunks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n标准正文", "content_ltks": "body tokens", "content_sm_ltks": "body sm tokens"},
        {"content_with_weight": "表1 技术参数特性表\nYJV\t3"},
    ]

    doc_context.apply_document_context(chunks, INCIDENT_DOC_NAME, language="Chinese")

    # The chunker's own tokens are preserved and the prefix's tokens are added, so
    # the standard number is matched by the full-text leg — not only by the embedding.
    prefix_tks = _StubRagTokenizer.tokenize("[标准号: Q/GDW 73289.2-2026 | 文档: " + INCIDENT_DOC_TITLE + "] ")
    assert stub_rag_tokenizer.language == "Chinese"
    assert chunks[0]["content_ltks"] == prefix_tks + " body tokens"
    assert chunks[0]["content_sm_ltks"] == "fg:" + prefix_tks + " body sm tokens"
    # A chunk that carries no token fields still gains the prefix's, so it cannot be
    # indexed without the standard number.
    assert chunks[1]["content_ltks"] == prefix_tks


@pytest.mark.p2
def test_apply_document_context_leaves_other_documents_untouched(stub_rag_tokenizer):
    chunks = [
        {"content_with_weight": "产品使用说明书\n本产品适用于室内布线。"},
        {"content_with_weight": "表1 规格表\n型号\t电压\nA\t450/750V"},
        {"content_with_weight": "1.5 mm2 铜芯线，长期工作温度不超过70℃。"},
    ]
    before = [dict(chunk) for chunk in chunks]

    assert doc_context.apply_document_context(chunks, "产品说明书.pdf") == 0
    assert chunks == before
    assert stub_rag_tokenizer.language is None


@pytest.mark.p2
def test_apply_document_context_is_idempotent():
    chunks = [{"content_with_weight": "Q/GDW 73289.2-2026\n标准正文"}]

    assert doc_context.apply_document_context(chunks, INCIDENT_DOC_NAME) == 1
    once = dict(chunks[0])

    assert doc_context.apply_document_context(chunks, INCIDENT_DOC_NAME) == 0
    assert chunks[0] == once
    assert once["content_with_weight"].count(doc_context.CONTEXT_PREFIX_OPEN) == 1


@pytest.mark.p2
def test_apply_document_context_skips_empty_and_textless_chunks():
    chunks = [
        {"content_with_weight": "Q/GDW 73289.2-2026\n标准正文"},
        {"content_with_weight": "", "img_id": "picture"},
        {"content_with_weight": "   \n  "},
        {"img_id": "no-body-key"},
    ]

    assert doc_context.apply_document_context(chunks, INCIDENT_DOC_NAME) == 1
    assert chunks[1]["content_with_weight"] == ""
    assert chunks[2]["content_with_weight"] == "   \n  "
    assert "content_with_weight" not in chunks[3]


@pytest.mark.p2
@pytest.mark.parametrize(
    ("doc_name", "texts", "expected"),
    [
        ("Q/GDW 73289.2-2026 采购标准.pdf", [], "Q/GDW 73289.2-2026"),
        ("专用技术规范.pdf", ["Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准"], "Q/GDW 73289.2-2026"),
        ("技术规范.pdf", ["本规范依据GB/T 12706.1-2020编制。"], "GB/T 12706.1-2020"),
        ("规范.pdf", ["DL/T 5221\u20142016"], "DL/T 5221-2016"),
        ("规范.pdf", ["Q/GDW\n73289.2-2026"], "Q/GDW 73289.2-2026"),
        ("企标.pdf", ["Q/GDW 73289.2 专用技术规范"], "Q/GDW 73289.2"),
        # A bare number with a national prefix is more likely a table value.
        ("手册.pdf", ["GB 1234 见附表"], ""),
        # 450/750V is the cable rating in the incident document, not a standard.
        ("450/750V聚氯乙烯绝缘电缆采购标准.pdf", ["额定电压450/750V，用于固定敷设。"], ""),
        # The inner EN must not be read as a designation.
        ("report.pdf", ["GENERAL 100-2020 requirements"], ""),
        ("", [], ""),
    ],
)
def test_detect_standard_id(doc_name, texts, expected):
    assert doc_context.detect_standard_id(doc_name, texts) == expected


@pytest.mark.p2
def test_detect_standard_id_prefers_the_number_that_names_the_document():
    # The incident document references GB/T 3956-2008 inside a clause body; the
    # number that identifies the document comes first and must win.
    found = doc_context.detect_standard_id(
        INCIDENT_DOC_NAME,
        [
            "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准",
            "5.1 电缆结构\n导体应符合GB/T 3956-2008的规定。",
        ],
    )
    assert found == "Q/GDW 73289.2-2026"


@pytest.mark.p2
def test_document_title_keeps_the_voltage_rating_slash():
    # The "/" in "450/750V" is part of the name, not a directory separator.
    assert doc_context.document_title(INCIDENT_DOC_NAME) == INCIDENT_DOC_TITLE
    assert doc_context.document_title("   ") == ""
    assert doc_context.document_title("报告.docx") == "报告"


@pytest.mark.p2
def test_document_sections_walks_headings_in_reading_order():
    sections = doc_context.document_sections(
        [
            "Q/GDW 73289.2-2026\n450/750V聚氯乙烯绝缘电缆采购标准",
            "表1 技术参数特性表\n型号\t芯数",
            "YJV\t3",
            "5.1 电缆结构\n导体应符合规定。",
            "1.5 mm2 铜芯线",
            "图1所示为本标准的结构示意图。",
            "附录A 试验方法\n按GB/T 2951.11-2008执行。",
        ]
    )

    assert sections == [
        "",
        "表1 技术参数特性表",
        "表1 技术参数特性表",
        "5.1 电缆结构",
        "5.1 电缆结构",
        "5.1 电缆结构",
        "附录A 试验方法",
    ]


@pytest.mark.p2
@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("表1 技术参数特性表", "表1 技术参数特性表"),
        ("表 2.1  结构尺寸", "表2.1 结构尺寸"),
        ("图3 电缆截面", "图3 电缆截面"),
        ("附录A 规范性附录", "附录A 规范性附录"),
        ("第一章 总则", "第一章 总则"),
        ("第2部分：专用技术规范", "第2部分 专用技术规范"),
        ("5.1 电缆结构", "5.1 电缆结构"),
        ("# 5.1 电缆结构", "5.1 电缆结构"),
        ("2 规范性引用文件", "2 规范性引用文件"),
        ("1.5 mm2", ""),
        ("图1所示为本标准的结构示意图。", ""),
        ("450/750V聚氯乙烯绝缘电缆", ""),
        ("YJV\t3\t240", ""),
    ],
)
def test_heading_detection(line, expected):
    assert doc_context._heading_of(line) == expected


@pytest.mark.p2
def test_render_document_context_omits_missing_fields():
    assert doc_context.render_document_context("GB/T 12706.1-2020", "", "") == "[标准号: GB/T 12706.1-2020] "
    assert doc_context.render_document_context("GB/T 12706.1-2020", "报告", "") == "[标准号: GB/T 12706.1-2020 | 文档: 报告] "
