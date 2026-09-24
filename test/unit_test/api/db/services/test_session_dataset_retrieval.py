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
"""Where a session's turn retrieves from (api/db/services/conversation_service.py).

A turn used to union the per-request `kb_ids` onto the assistant's set and never
look at the session, so a session could not decide anything. The rule now is:

* the session's own binding, when it has one, is what the turn retrieves from --
  it REPLACES the assistant's set, it is never unioned with it;
* without a binding the assistant's datasets stand, exactly as before;
* a session bound to no dataset retrieves from none, and does not fall back to
  the assistant's;
* an explicit per-request `kb_ids` (the bot/SDK callers) still unions onto
  whichever set is effective.

These tests drive the real `async_completion` with only its IO stubbed, so they
read the datasets the chat path was actually handed.
"""

from types import SimpleNamespace

import pytest

from api.db.services import conversation_service

CHAT_ID = "chat-1"
SESSION_ID = "sess-1"
ASSISTANT_DATASETS = ["kb-agent"]


class _FakeDialogService:
    def __init__(self):
        self.dialog = SimpleNamespace(
            id=CHAT_ID,
            tenant_id="tenant-1",
            kb_ids=list(ASSISTANT_DATASETS),
            prompt_config={"prologue": "hi"},
        )

    def query(self, **_kwargs):
        return [self.dialog]

    def get_by_id(self, _chat_id):
        return True, self.dialog


class _FakeConversation:
    """A session row: `kb_ids` is None when it inherits the assistant's."""

    def __init__(self, kb_ids):
        self.id = SESSION_ID
        self.dialog_id = CHAT_ID
        self.kb_ids = kb_ids
        self.message = [{"role": "assistant", "content": "prologue", "id": "msg-0"}]
        self.reference = []

    def to_dict(self):
        return {"id": self.id, "dialog_id": self.dialog_id, "message": list(self.message), "reference": list(self.reference)}


class _FakeConversationService:
    def __init__(self, conv):
        self.conv = conv

    def query(self, **_kwargs):
        return [self.conv]

    def save(self, **_kwargs):
        return True

    def update_by_id(self, *_args, **_kwargs):
        return 1


@pytest.fixture
def turn(monkeypatch):
    """A session turn whose retrieval call is captured instead of executed."""
    state = {"retrieved": []}

    def install(session_kb_ids):
        conv = _FakeConversation(session_kb_ids)

        async def async_chat(dialog, _messages, _stream, **_kwargs):
            state["retrieved"].append(list(dialog.kb_ids))
            yield {"answer": "ok", "reference": {}}

        monkeypatch.setattr(conversation_service, "DialogService", _FakeDialogService())
        monkeypatch.setattr(conversation_service, "ConversationService", _FakeConversationService(conv))
        monkeypatch.setattr(conversation_service, "async_chat", async_chat)
        return conv

    state["install"] = install
    return state


async def _run_turn(**kwargs):
    async for _chunk in conversation_service.async_completion("tenant-1", CHAT_ID, "question", session_id=SESSION_ID, stream=False, **kwargs):
        pass


@pytest.mark.p1
@pytest.mark.asyncio
async def test_a_session_binding_replaces_the_assistants_datasets(turn):
    turn["install"](["kb-session"])

    await _run_turn()

    assert turn["retrieved"] == [["kb-session"]]


@pytest.mark.p1
@pytest.mark.asyncio
async def test_a_session_without_a_binding_inherits_the_assistants_datasets(turn):
    turn["install"](None)

    await _run_turn()

    assert turn["retrieved"] == [ASSISTANT_DATASETS]


@pytest.mark.p1
@pytest.mark.asyncio
async def test_a_session_bound_to_no_dataset_retrieves_from_none(turn):
    turn["install"]([])

    await _run_turn()

    # `[]` is a binding, not the absence of one: no fallback to the assistant.
    assert turn["retrieved"] == [[]]


@pytest.mark.p1
@pytest.mark.asyncio
async def test_an_explicit_request_binding_still_unions_onto_the_sessions(turn):
    turn["install"](["kb-session"])

    await _run_turn(kb_ids=["kb-extra"])

    assert sorted(turn["retrieved"][0]) == ["kb-extra", "kb-session"]


@pytest.mark.p1
@pytest.mark.asyncio
async def test_an_explicit_request_binding_still_unions_onto_the_assistants(turn):
    turn["install"](None)

    await _run_turn(kb_ids=["kb-extra"])

    assert sorted(turn["retrieved"][0]) == ["kb-agent", "kb-extra"]
