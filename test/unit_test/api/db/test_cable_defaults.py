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
"""The cable vertical's defaults for a new dataset or chat assistant.

The values are asserted here because they are a product decision, and because
the DB models, the REST API and (in Go) the chat/dataset services all read them:
a silent drift in one of those would only show up as a wrong retrieval setting
on every newly created row.
"""

from api.db import cable_defaults
from api.db.db_models import Dialog, Knowledgebase

CABLE_PROMPT_OPENING = "你是一位经验丰富且亲切的线缆技术专家顾问。"


def test_retrieval_defaults():
    assert cable_defaults.SIMILARITY_THRESHOLD == 0.25
    assert cable_defaults.VECTOR_SIMILARITY_WEIGHT == 0.30
    # The full-text leg takes the remainder of the vector weight.
    assert round(1 - cable_defaults.VECTOR_SIMILARITY_WEIGHT, 2) == 0.70
    assert cable_defaults.RERANK_CANDIDATES_COUNT == 64
    assert cable_defaults.TOP_N == 6


def test_prompt_defaults():
    assert cable_defaults.SYSTEM_PROMPT.startswith(CABLE_PROMPT_OPENING)
    assert cable_defaults.SYSTEM_PROMPT.rstrip().endswith("以上是知识库。")
    # The retrieval step fills {knowledge}, so the parameter must be declared.
    assert "{knowledge}" in cable_defaults.SYSTEM_PROMPT
    assert {"key": "knowledge", "optional": False} in cable_defaults.PROMPT_PARAMETERS
    assert cable_defaults.PROLOGUE.strip() != ""
    assert cable_defaults.EMPTY_RESPONSE.strip() != ""


def test_prompt_config_returns_an_independent_copy():
    prompt_config = cable_defaults.prompt_config()
    prompt_config["parameters"].append({"key": "extra", "optional": True})
    prompt_config["system"] = "edited"

    assert cable_defaults.prompt_config()["parameters"] == cable_defaults.PROMPT_PARAMETERS
    assert cable_defaults.prompt_config()["system"] == cable_defaults.SYSTEM_PROMPT


def test_chat_model_defaults_use_the_cable_values():
    assert Dialog.similarity_threshold.default == cable_defaults.SIMILARITY_THRESHOLD
    assert Dialog.vector_similarity_weight.default == cable_defaults.VECTOR_SIMILARITY_WEIGHT
    assert Dialog.top_n.default == cable_defaults.TOP_N
    assert Dialog.rerank_candidates_count.default == cable_defaults.RERANK_CANDIDATES_COUNT

    # A JSONField default that is callable is evaluated per insert, which keeps
    # one row's prompt edits out of every other row.
    prompt_config = Dialog.prompt_config.default()
    assert prompt_config["system"] == cable_defaults.SYSTEM_PROMPT
    assert prompt_config["prologue"] == cable_defaults.PROLOGUE
    assert prompt_config["empty_response"] == cable_defaults.EMPTY_RESPONSE


def test_dataset_model_defaults_use_the_cable_values():
    assert Knowledgebase.similarity_threshold.default == cable_defaults.SIMILARITY_THRESHOLD
    assert Knowledgebase.vector_similarity_weight.default == cable_defaults.VECTOR_SIMILARITY_WEIGHT
