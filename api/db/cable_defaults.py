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
"""Cable-domain defaults for a newly created dataset or chat assistant.

This fork is a cable-industry vertical, so a dataset or chat assistant created
without explicit retrieval or prompt settings starts from the cable values below
instead of the generic RAGFlow ones. Both the persisted model defaults
(``api/db/db_models.py``) and the API create defaults
(``api/apps/restful_apis/chat_api.py``) read this module, so a row lands on the
same configuration whichever path created it: the UI, the SDK, or a direct
service call.

This is the single source of truth on the Python side; the Go backend mirrors
the same values in ``internal/service/chat.go`` and
``internal/service/dataset/crud.go``.
"""

from typing import Any

#: Minimum similarity a passage must reach to be retrieved by a new dataset or
#: chat assistant.
SIMILARITY_THRESHOLD = 0.25
#: Weight of the vector leg of the hybrid score. The full-text (keyword) leg
#: takes the remainder, i.e. 0.70.
VECTOR_SIMILARITY_WEIGHT = 0.30
#: Passages handed to the reranker.
RERANK_CANDIDATES_COUNT = 64
#: Passages kept for the answer handed to the LLM.
TOP_N = 6

#: System prompt of a new chat assistant. ``{knowledge}`` is where the retrieved
#: passages are injected; the declared parameters below must match it.
SYSTEM_PROMPT = (
    "你是一位经验丰富且亲切的线缆技术专家顾问。\n"
    "\n"
    "【沟通风格】\n"
    "- 请使用自然、流畅、口语化的语言回答问题，语气生动亲切。\n"
    "- 避免像机器一样机械地罗列硬邦邦的规范条款，把复杂的工程标准用通俗易懂的专业语言表达出来。\n"
    "\n"
    "【回答与推理原则】\n"
    "1. 自然表达与拒答：如果知识库中完全没有包含回答问题所需的信息，请用自然的口吻告知用户暂未查到相关资料即可，无需使用僵硬固定的模板（如“未找到您想要的答案”）。\n"
    "2. 弹性与例外条款优先：在回答基于标准规范的逻辑判定或选型问题时，必须优先检查标准文本中是否存在“例外条款”、“供需双方协商确定”、“补充协议规定”或“特殊工况说明”等弹性规定。只要标准允许协商或存在例外，不得仅凭通用常识直接否定。\n"
    "3. 合理工程推理：允许基于知识库提取出的物理结构特征（如铠装类型、材质、截面等），结合线缆工程常识进行合理的适用性分析。\n"
    "\n"
    "以下是知识库：\n"
    "{knowledge}\n"
    "以上是知识库。"
)

#: Opening line of a new chat assistant.
PROLOGUE = "您好！我是您的线缆技术与选型专家助手，请发送您的文件或提问合规校验及工程选型评估"

#: Answer shown when retrieval returns nothing, instead of asking the model.
EMPTY_RESPONSE = "暂未在知识库中检索到相关线缆参数或规范条款。您可以提供更具体的型号规格或更新补充文档"

#: Prompt parameters the system prompt above declares. ``knowledge`` is filled by
#: the retrieval step, ``date`` is optional and filled from the request.
PROMPT_PARAMETERS = [
    {"key": "knowledge", "optional": False},
    {"key": "date", "optional": True},
]


def prompt_config() -> dict[str, Any]:
    """A fresh cable prompt configuration for a new chat assistant.

    A function rather than a module-level dict: every caller needs its own copy
    so one row's edits can never leak into another's.
    """
    return {
        "system": SYSTEM_PROMPT,
        "prologue": PROLOGUE,
        "parameters": [dict(parameter) for parameter in PROMPT_PARAMETERS],
        "empty_response": EMPTY_RESPONSE,
    }
