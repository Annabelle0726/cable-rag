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
"""The three shapes a stored answer can render wrong, without a database."""

from tools.scripts.audit_answer_rendering import analyse, answer_pools, inspect_answer

LEAKED = "[Formalize][pre_summary] question='问题' pre_summary_len=0 evidence_len=3392\n" "pre_summary=''直接说结论：**没有发现相关条款。**\n" "\n" "另外，规范里留了口子 [ID:1][ID:3][ID:5]。"
CLEAN = "[Formalize] Single-turn — kept verbatim: 问题\n直接说结论：没有发现相关条款 [ID:1]。"


def _conversation(answer: str, chunks: int = 0, dialog: str = "助手"):
    """A conversation with a prologue and one answer, as the API stores it."""
    messages = [
        {"role": "assistant", "content": "你好"},
        {"role": "user", "content": "问题"},
        {"role": "assistant", "content": answer},
    ]
    reference = [{"chunks": [{"chunk_id": f"c{i}"} for i in range(chunks)], "doc_aggs": []}]
    return ("conv-1", dialog, messages, reference, "2026-09-19 15:50:50")


class TestOneAnswer:
    def test_field_payload_glued_to_the_answer_is_reported(self):
        result = inspect_answer(LEAKED)

        assert result["leaked_fields"], "the pre_summary payload should be flagged"
        assert "pre_summary" in result["leaked_fields"][0]

    def test_log_line_that_is_no_payload_is_reported(self):
        result = inspect_answer("[Action Session:init] d0(.+)\n- id=0 type=slot\n\n答案是 42。")

        assert result["leaked_logs"] == ["- id=0 type=slot"]

    def test_a_clean_answer_reports_nothing(self):
        result = inspect_answer(CLEAN)

        assert result["leaked_fields"] == []
        assert result["leaked_logs"] == []
        assert result["markers"] == [1]

    def test_unbalanced_think_markers_are_reported(self):
        assert inspect_answer("<think>写到一半就断了。答案是 42。")["think_open"] == 1
        assert inspect_answer("<think>想完了</think>答案是 42。")["think_open"] == inspect_answer("<think>想完了</think>答案是 42。")["think_closed"]


class TestPoolResolution:
    def test_an_empty_entry_inherits_the_pool_before_it(self):
        reference = [{"chunks": [1, 2]}, {"chunks": [], "doc_aggs": []}]

        assert answer_pools(reference) == [2, 2]

    def test_a_leading_empty_entry_stays_unresolved(self):
        assert answer_pools([{"chunks": [], "doc_aggs": []}, {"chunks": [1]}])[0] == 0

    def test_no_reference_at_all(self):
        assert answer_pools(None) == []


class TestTheReport:
    def test_counts_the_three_shapes(self):
        conversations = [
            _conversation(LEAKED, chunks=0),  # leak + no pool
            _conversation(CLEAN, chunks=1),  # clean
            _conversation("结论 [ID:9]。", chunks=3),  # marker past every pool
        ]

        totals, findings = analyse(conversations)

        assert totals["answers"] == 3
        assert totals["answers_with_leaked_field"] == 1
        assert totals["answers_with_markers"] == 3
        # The leaked answer's pool is empty and nothing precedes it, so its markers
        # cannot open either; the third answer cites past its pool.
        assert totals["answers_with_unresolvable_markers"] == 2
        assert len(findings) == 2

    def test_an_answer_that_inherits_a_pool_is_not_reported(self):
        # The direct-answer path: no retrieval of its own, markers copied from the
        # previous answer, which did have a pool. Nothing renders wrong, so it is
        # counted as context rather than as a failure.
        messages = [
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "答一 [ID:1]。"},
            {"role": "user", "content": "第二问"},
            {"role": "assistant", "content": "答二 [ID:1][ID:2]。"},
        ]
        reference = [
            {"chunks": [{"chunk_id": "a"}, {"chunk_id": "b"}]},
            {"chunks": [], "doc_aggs": []},
        ]

        totals, findings = analyse([("conv-2", "助手", messages, reference, "now")])

        assert totals["answers_with_markers"] == 2
        assert totals["answers_resolving_via_inherited_pool"] == 1
        assert totals["answers_with_unresolvable_markers"] == 0
        assert findings == []

    def test_a_marker_past_the_inherited_pool_is_reported(self):
        messages = [
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "第一问"},
            {"role": "assistant", "content": "答一 [ID:1]。"},
            {"role": "user", "content": "第二问"},
            {"role": "assistant", "content": "答二 [ID:5]。"},
        ]
        reference = [
            {"chunks": [{"chunk_id": "a"}, {"chunk_id": "b"}]},
            {"chunks": [], "doc_aggs": []},
        ]

        totals, findings = analyse([("conv-4", "助手", messages, reference, "now")])

        assert totals["answers_with_unresolvable_markers"] == 1
        assert len(findings) == 1
        assert "markers reach 5" in findings[0].problems[0]

    def test_error_answers_and_the_prologue_are_skipped(self):
        messages = [
            {"role": "assistant", "content": "你好 [ID:1]"},
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": "**ERROR**: boom [ID:9]"},
        ]

        totals, findings = analyse([("conv-3", "助手", messages, [], "now")])

        assert totals["answers"] == 0
        assert findings == []


class TestTimestampsAndSince:
    """An old answer's text is never rewritten, so the report has to say when the
    answer was written — and `--since` has to be able to hide the old ones."""

    def conversation(self, answered_at: float, answer: str = LEAKED):
        messages = [
            {"role": "assistant", "content": "你好", "created_at": answered_at - 60},
            {"role": "user", "content": "问题", "created_at": answered_at - 30},
            {"role": "assistant", "content": answer, "created_at": answered_at},
        ]
        # A conversation-level timestamp far newer than the message: this is what
        # made an old answer look freshly generated.
        return ("conv-ts", "助手", messages, [{"chunks": [], "doc_aggs": []}], "2099-01-01 00:00:00")

    def test_the_answer_reports_its_own_time_not_the_conversation_activity(self):
        _, findings = analyse([self.conversation(1789804250.43)])  # 2026-09-19 15:50:50

        assert findings[0].answered_at == "2026-09-19 15:50:50"

    def test_a_message_without_a_timestamp_falls_back_and_says_so(self):
        messages = [
            {"role": "assistant", "content": "你好"},
            {"role": "user", "content": "问题"},
            {"role": "assistant", "content": LEAKED},
        ]

        _, findings = analyse([("conv-ns", "助手", messages, [], "2026-09-19 15:50:50")])

        assert findings[0].answered_at == "2026-09-19 15:50:50 (conversation update_time)"

    def test_since_hides_answers_written_before_it(self):
        old = self.conversation(1789804250.43)  # 15:50
        new = self.conversation(1789814457.60)  # 18:40, same leaky text

        totals, findings = analyse([old, new], since="2026-09-19 17:00")

        assert totals["answers"] == 1
        assert len(findings) == 1
        assert findings[0].answered_at.startswith("2026-09-19 18:40")

    def test_without_since_every_answer_is_reported(self):
        totals, findings = analyse([self.conversation(1789804250.43), self.conversation(1789814457.60)])

        assert totals["answers"] == 2
        assert len(findings) == 2
