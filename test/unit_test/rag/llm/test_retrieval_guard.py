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

from rag.llm.retrieval_guard import is_small_talk, mandatory_retrieval

pytestmark = pytest.mark.p1


@pytest.mark.parametrize(
    "turn",
    [
        "",
        "   ",
        "？",
        "你好",
        "您好！",
        "你好呀",
        " 你好 ",
        "hi",
        "Hi there",
        "HELLO!",
        "嗨",
        "早上好",
        "晚安",
        "在吗",
        "谢谢",
        "谢谢你啦",
        "非常感谢您！",
        "Thanks!",
        "thank you very much",
        "THX",
        "辛苦了",
        "好的",
        "嗯嗯",
        "收到",
        "ok",
        "OK,",
        "got it",
        "再见",
        "拜拜~",
        "bye",
        "good night",
        "你是谁",
        "你叫什么名字？",
        "What's your name?",
        "你能做什么",
        "who are you",
    ],
)
def test_small_talk_turns_carry_nothing_to_retrieve(turn):
    assert is_small_talk(turn)


@pytest.mark.parametrize(
    "turn",
    [
        "请把 YZ 系列与 YJV 系列的技术参数差异整理成一张对照表",
        # A greeting that opens a real question is still a question.
        "你好，介绍一下 YZ 系列电缆",
        "你好！请问 YJV 的载流量是多少",
        "那它的价格呢？",
        "hi, what models do you have?",
        "谢谢，那么 YJV 和 YZ 的区别是什么？",
        "thanks for nothing, now compare the two cables",
        "who are you calling for the cable spec?",
        "电缆的额定电压是多少",
        "请继续",
        "还有吗",
        "好的，那给我一份对照表",
        "ok, list every model",
    ],
)
def test_questions_are_never_small_talk(turn):
    assert not is_small_talk(turn)


def test_mandatory_retrieval_keeps_the_turn_verbatim():
    turn = "请把 YZ 系列与 YJV 系列的技术参数差异整理成一张对照表"

    request = mandatory_retrieval(turn)

    assert request is not None
    assert request.tool == "rag"
    assert request.question == turn
    assert request.arguments == {"question": turn}


def test_mandatory_retrieval_is_none_for_small_talk():
    assert mandatory_retrieval("你好") is None
    assert mandatory_retrieval("") is None


def test_mandatory_retrieval_tool_can_be_overridden():
    request = mandatory_retrieval("YZ 系列的护套材料是什么", tool="search_kb")

    assert request is not None
    assert request.tool == "search_kb"
