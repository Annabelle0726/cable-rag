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
"""What a client is told when a model provider refuses a request.

Every assertion here is about a failure a reader has to react to: the shape of
the response they get, and whether the one field they see says "wait" or "this
account is out of quota".
"""

import pytest

from common import model_errors
from rag.llm.embedding_model import (
    EmbeddingError,
    EmbeddingQuotaExhausted,
    EmbeddingRateLimited,
    embedding_failure,
)

#: The body Google answered with when the free tier ran out. It is a 429, and
#: nothing but the quota id separates it from a per-minute limit.
GEMINI_DAILY_QUOTA = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, "
    "please check your plan and billing details.', 'status': 'RESOURCE_EXHAUSTED', "
    "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': "
    "[{'quotaMetric': 'generativelanguage.googleapis.com/embed_content_free_tier_requests', "
    "'quotaId': 'EmbedContentRequestsPerDayPerProjectPerModel-FreeTier', 'quotaValue': '1000'}]}]}}"
)

#: The same provider, a minute later than it would like.
GEMINI_RATE_LIMIT = (
    "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Quota exceeded for metric: "
    "generativelanguage.googleapis.com/embed_content_free_tier_requests, limit: 100, model: "
    "gemini-embedding-1.0', 'status': 'RESOURCE_EXHAUSTED', 'details': "
    "[{'quotaId': 'EmbedContentRequestsPerMinutePerProjectPerModel-FreeTier', "
    "'retryDelay': '20s'}]}}"
)

OPENAI_SPENT_ACCOUNT = 'Error code: 429 - {"error": {"message": "You exceeded your current quota", "type": "insufficient_quota"}}'

OPENAI_PACING = 'Error code: 429 - {"error": {"message": "Rate limit reached for text-embedding-3-small", "type": "rate_limit_exceeded"}}'


def test_a_spent_quota_is_not_reported_as_pacing():
    """The two arrive as the same status code and mean opposite things."""
    assert model_errors.classify(GEMINI_DAILY_QUOTA) == model_errors.EMBEDDING_QUOTA_EXHAUSTED
    assert model_errors.classify(GEMINI_RATE_LIMIT) == model_errors.EMBEDDING_RATE_LIMITED
    assert model_errors.classify(OPENAI_SPENT_ACCOUNT) == model_errors.EMBEDDING_QUOTA_EXHAUSTED
    assert model_errors.classify(OPENAI_PACING) == model_errors.EMBEDDING_RATE_LIMITED


def test_an_unrelated_failure_is_left_alone():
    assert model_errors.classify("Connection reset by peer") is None
    assert model_errors.model_failure_response(ValueError("boom")) is None


def test_the_response_carries_a_readable_message_and_keeps_the_raw_text_aside():
    payload = model_errors.model_failure_response(EmbeddingQuotaExhausted("GeminiEmbed", GEMINI_DAILY_QUOTA))

    assert payload is not None
    assert payload["code"] == 429
    assert payload["error_type"] == model_errors.EMBEDDING_QUOTA_EXHAUSTED
    assert payload["message"] == model_errors.MESSAGES[model_errors.EMBEDDING_QUOTA_EXHAUSTED]
    # The reader's field is the sentence, not the provider's JSON.
    assert "RESOURCE_EXHAUSTED" not in payload["message"]
    assert "quotaId" in payload["raw_message"]


def test_the_raw_text_travels_truncated():
    """It is a diagnostic, and an upstream body runs to kilobytes."""
    payload = model_errors.model_failure_response(EmbeddingRateLimited("GeminiEmbed", "x" * 5000))

    assert payload is not None
    assert len(payload["raw_message"]) == model_errors.MAX_RAW_MESSAGE


def test_a_providers_own_exception_is_still_recognised():
    """A connector that leaks its SDK error must not leak it to the screen."""
    payload = model_errors.model_failure_response(RuntimeError(OPENAI_SPENT_ACCOUNT))

    assert payload is not None
    assert payload["error_type"] == model_errors.EMBEDDING_QUOTA_EXHAUSTED


def test_a_rate_limit_is_worth_retrying_and_a_spent_quota_is_not():
    assert embedding_failure("GeminiEmbed", GEMINI_RATE_LIMIT).retryable is True
    assert embedding_failure("GeminiEmbed", GEMINI_DAILY_QUOTA).retryable is False


def test_the_embedding_error_keeps_its_own_text_for_the_log():
    """The exception still says what happened, even though the client does not."""
    error = embedding_failure("GeminiEmbed", GEMINI_DAILY_QUOTA)

    assert isinstance(error, EmbeddingQuotaExhausted)
    assert "GeminiEmbed" in str(error)
    assert error.raw_message == GEMINI_DAILY_QUOTA


def test_an_unrecognised_failure_stays_a_plain_embedding_error():
    error = embedding_failure("SomeEmbed", "socket closed")

    assert type(error) is EmbeddingError
    assert model_errors.model_failure_response(error) is None
    assert error.raw_message == "socket closed"


@pytest.mark.parametrize(
    "detail",
    [
        "429 Too Many Requests",
        "rate limit exceeded",
        "RESOURCE_EXHAUSTED",
    ],
)
def test_a_bare_429_is_never_mistaken_for_a_spent_quota(detail):
    """A body that says nothing beyond "429" is the retryable case."""
    assert model_errors.classify(detail) == model_errors.EMBEDDING_RATE_LIMITED
