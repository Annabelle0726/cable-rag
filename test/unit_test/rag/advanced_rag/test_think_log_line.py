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
"""The forwarded record is always one line, so the tag rule can never miss."""

import logging

from rag.advanced_rag.think_log import ThinkLogHandler, render_think_log_line, set_think_log_sink, reset_think_log_sink


def _forward(logger_name: str, message: str, *args) -> list:
    """Run one record through the handler and collect what the sink received."""
    seen: list = []
    token = set_think_log_sink(seen.append)
    try:
        handler = ThinkLogHandler(level=logging.INFO)
        record = logging.LogRecord(
            name=logger_name,
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg=message,
            args=args,
            exc_info=None,
        )
        handler.emit(record)
    finally:
        reset_think_log_sink(token)
    return seen


class TestRecordStaysOnOneLine:
    def test_two_line_record_is_escaped_into_one_line(self):
        # The shape that leaked: the compose stage logs the field assignment on a
        # second line, and the answer is glued to it.
        seen = _forward(
            "rag.advanced_rag.agentic_rag_graph",
            "[Formalize][pre_summary] question=%r pre_summary_len=%d evidence_len=%d\npre_summary=%r",
            "问题",
            0,
            3392,
            "直接说结论：没有相关条款",
        )

        assert len(seen) == 1
        payload = seen[0]
        # Exactly one line: the sink's break markers are the only line breaks, and
        # no bare newline survives anywhere in the payload.
        assert payload.count("<br>") == 2
        assert "\n" not in payload
        assert payload.startswith("<br>[Formalize][pre_summary]")
        assert payload.endswith("<br>")
        # The content is preserved, just escaped — the panel still shows it.
        assert "evidence_len=3392" in payload
        assert "pre_summary='直接说结论：没有相关条款'" in payload
        assert "\\npre_summary=" in payload


class TestOnlyForwardedCopyIsEscaped:
    def test_log_file_keeps_its_own_formatting(self):
        record = logging.LogRecord(
            name="rag.advanced_rag.x",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="[Stage] first\nsecond",
            args=(),
            exc_info=None,
        )

        assert record.getMessage() == "[Stage] first\nsecond"
        assert render_think_log_line(record.getMessage()) == "<br>[Stage] first\\nsecond<br>"


class TestFilteringIsUnchanged:
    def test_untagged_and_out_of_scope_records_are_skipped(self):
        assert _forward("rag.advanced_rag.x", "no stage tag\nstill no tag") == []
        assert _forward("api.db.services.dialog_service", "[Not scoped] x") == []

    def test_bracket_tagged_in_scope_record_is_forwarded(self):
        seen = _forward("rag.llm.chat_model", "[Tool loop] deciding what to do next")

        assert seen == ["<br>[Tool loop] deciding what to do next<br>"]
