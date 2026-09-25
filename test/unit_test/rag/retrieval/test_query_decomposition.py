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
"""Module A: question decomposition and structural-reference stripping.

Two behaviours are load-bearing here and are pinned separately:

* a question with one information need must NOT cost an LLM call or an extra
  route - it keeps the single-route retrieval this path had before;
* a structural hierarchy reference ("第5章", "5.3.3", "附录A") must be removed
  from the search statement, while numeric DATA in the same sentence
  ("0.6/1kV", "1.2mm") must survive verbatim, because the keyword leg needs the
  value the user asked about.
"""

import pytest

from rag.retrieval import decomposition

pytestmark = pytest.mark.p1


class _ChatModel:
    """Only used as a token: ``gen_json`` is stubbed, the model is never called."""


@pytest.fixture
def decomposed(monkeypatch):
    """Install a scripted ``gen_json`` in place of the LLM node."""

    def _install(payload=None, error=None):
        async def _fake_gen_json(system_prompt, user_prompt, chat_mdl, gen_conf=None, max_retry=2):
            if error is not None:
                raise error
            return payload

        monkeypatch.setattr(decomposition, "gen_json", _fake_gen_json)

    return _install


# ---------------------------------------------------------------------------
# Structural references
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("第5章5.3.3 绝缘标称厚度是多少", "绝缘标称厚度是多少"),
        ("第6章 6.2 例行交流电压试验要求", "例行交流电压试验要求"),
        ("第 5.3 节 的绝缘电阻要求是什么", "绝缘电阻要求是什么"),
        ("第五章附录A 的试验方法", "试验方法"),
        ("5.3.3 标称厚度是多少", "标称厚度是多少"),
        ("第3条 导体直流电阻", "导体直流电阻"),
    ],
)
def test_structural_references_are_stripped(text, expected):
    assert decomposition.strip_section_references(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "额定电压 0.6/1kV 的绝缘标称厚度是 1.2mm 吗",
        "标称截面 3×240mm² 的导体直流电阻",
        "A、B、C 类检测任务应分别在收样后 20、15、10 个工作日内完成",
    ],
)
def test_numeric_data_is_not_mistaken_for_a_section_number(text):
    """Only outline coordinates go: a section word or a leading dotted number."""
    assert decomposition.strip_section_references(text) == text


def test_a_pure_reference_keeps_its_text():
    """Stripping must never hand the retriever an empty query."""
    assert decomposition.strip_section_references("第5章") == "第5章"


# ---------------------------------------------------------------------------
# Composite gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "普通绝缘和轻型薄绝缘的厚度、绝缘电阻和电压试验有什么区别？",
        "同时对比绝缘标称厚度、绝缘电阻、交流电压试验标准",
        "第5章和第6章的例行试验项目有哪些？分别是什么要求？",
    ],
)
def test_multi_dimensional_questions_are_composite(question):
    assert decomposition.looks_composite(question)


@pytest.mark.parametrize(
    "question",
    [
        "标称厚度是多少",
        "交流电压试验标准",
        "绝缘电阻是多少",
    ],
)
def test_single_dimension_questions_are_not_composite(question):
    """These keep the single-route path - and the behaviour that works today."""
    assert not decomposition.looks_composite(question)


def test_the_prompt_template_renders():
    """The prompt is loaded from disk; a Jinja typo must not reach production."""
    rendered = decomposition.PROMPT_JINJA_ENV.from_string(decomposition.DECOMPOSITION_PROMPT).render(
        question="绝缘标称厚度是多少",
        max_sub_queries=decomposition.MAX_SUB_QUERIES,
    )
    assert "绝缘标称厚度是多少" in rendered
    assert "sub_queries" in rendered


# ---------------------------------------------------------------------------
# Parsing the model's answer
# ---------------------------------------------------------------------------


def test_sub_queries_are_stripped_and_deduplicated():
    result = {
        "sub_queries": [
            "第5章 5.3.3 普通绝缘和轻型薄绝缘的标称厚度是多少",
            "普通绝缘和轻型薄绝缘的例行交流电压试验要求是多少",
            "普通绝缘和轻型薄绝缘的例行交流电压试验要求是多少",
            "普通绝缘和轻型薄绝缘的厚度、绝缘电阻和电压试验有什么区别？",
        ]
    }
    question = "普通绝缘和轻型薄绝缘的厚度、绝缘电阻和电压试验有什么区别？"

    assert decomposition.parse_sub_queries(result, question) == [
        "普通绝缘和轻型薄绝缘的标称厚度是多少",
        "普通绝缘和轻型薄绝缘的例行交流电压试验要求是多少",
    ]


def test_parse_accepts_a_bare_list_and_dict_members():
    assert decomposition.parse_sub_queries(["绝缘电阻要求是多少", {"query": "交流电压试验要求是多少"}], "问题") == [
        "绝缘电阻要求是多少",
        "交流电压试验要求是多少",
    ]


def test_parse_caps_the_number_of_sub_queries():
    payload = {"sub_queries": [f"参数{i}是多少" for i in range(10)]}

    assert len(decomposition.parse_sub_queries(payload, "问题", max_sub_queries=3)) == 3


@pytest.mark.parametrize("payload", [None, {}, {"sub_queries": "not-a-list"}, "text", 7])
def test_unusable_payloads_yield_no_sub_queries(payload):
    assert decomposition.parse_sub_queries(payload, "问题") == []


def test_an_over_long_echo_is_truncated_not_dropped():
    echoed = "绝缘标称厚度" * 40

    parsed = decomposition.parse_sub_queries({"sub_queries": [echoed]}, "问题")

    assert len(parsed) == 1
    assert len(parsed[0]) <= decomposition.MAX_SUB_QUERY_CHARS


# ---------------------------------------------------------------------------
# The LLM node
# ---------------------------------------------------------------------------


async def test_decompose_returns_parsed_sub_queries(decomposed):
    decomposed({"sub_queries": ["绝缘标称厚度是多少", "例行交流电压试验要求是多少"]})

    result = await decomposition.decompose_question(_ChatModel(), "标称厚度和例行交流电压试验要求分别是什么")

    assert result == ["绝缘标称厚度是多少", "例行交流电压试验要求是多少"]


async def test_decompose_degrades_when_the_model_fails(decomposed):
    """A dead LLM node must not fail the turn: the caller searches the original."""
    decomposed(error=RuntimeError("model down"))

    assert await decomposition.decompose_question(_ChatModel(), "标称厚度和电压试验要求分别是什么") == []


async def test_decompose_skips_an_empty_question_or_a_missing_model(decomposed):
    decomposed({"sub_queries": ["绝缘标称厚度是多少"]})

    assert await decomposition.decompose_question(None, "标称厚度和电压试验") == []
    assert await decomposition.decompose_question(_ChatModel(), "   ") == []
