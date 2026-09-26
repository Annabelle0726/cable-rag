import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import valkey as redis
from peewee import SqliteDatabase
from werkzeug.security import check_password_hash

from api.db.db_models import User
from api.db.services import password_reset_service as service
from api.utils.crypt import crypt


@pytest.fixture
def recovery(monkeypatch):
    url = os.environ.get("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL must point to an isolated test Redis")
    client = redis.Redis.from_url(url)
    client.ping()
    db = SqliteDatabase(":memory:")
    with db.bind_ctx([User]), db:
        db.create_tables([User])
        User.create(id="member", nickname="Member", email="reset-test@example.com", password="old", access_token="old-token", login_channel="password")
        monkeypatch.setattr(service, "REDIS_CONN", SimpleNamespace(REDIS=client))
        monkeypatch.setattr(service, "_account", service._account.__wrapped__)
        monkeypatch.setattr(service.settings, "MAIL_SERVER", "test.invalid")
        monkeypatch.setattr(service.settings, "MAIL_PORT", 465)
        monkeypatch.setattr(service.settings, "MAIL_DEFAULT_SENDER", ("Test", "test@example.com"))
        monkeypatch.setattr(service.settings, "get_secret_key", lambda: "test-key")
        mail = AsyncMock()
        monkeypatch.setattr(service, "send_email_html", mail)
        for email in ("reset-test@example.com", "missing@example.com"):
            client.delete(service._key(email), service._key(email) + ":cooldown")
        yield client, mail
        for email in ("reset-test@example.com", "missing@example.com"):
            client.delete(service._key(email), service._key(email) + ":cooldown")
        client.close()


async def test_missing_smtp_has_controlled_error(monkeypatch):
    monkeypatch.setattr(service.settings, "MAIL_SERVER", "")
    with pytest.raises(ValueError, match="not configured"):
        await service.send_code("reset-test@example.com")


async def test_code_is_six_digits_expires_and_is_single_use(recovery):
    client, mail = recovery
    await service.send_code("reset-test@example.com")
    code = mail.call_args.kwargs["code"]
    assert len(code) == 6 and code.isdigit()
    assert 0 < client.ttl(service._key("reset-test@example.com")) <= 300
    service.reset_password.__wrapped__("reset-test@example.com", code, crypt("New-password-123"))
    user = User.get_by_id("member")
    assert user.access_token != "old-token"
    assert check_password_hash(user.password, service.password_value(crypt("New-password-123")))
    with pytest.raises(PermissionError):
        service.reset_password.__wrapped__("reset-test@example.com", code, crypt("Another-password"))


async def test_five_wrong_attempts_exhaust_code(recovery):
    _, mail = recovery
    await service.send_code("reset-test@example.com")
    code = mail.call_args.kwargs["code"]
    wrong = "111111" if code != "111111" else "222222"
    for _ in range(5):
        with pytest.raises(PermissionError):
            service.reset_password.__wrapped__("reset-test@example.com", wrong, crypt("New-password-123"))
    with pytest.raises(PermissionError):
        service.reset_password.__wrapped__("reset-test@example.com", code, crypt("New-password-123"))
    assert User.get_by_id("member").password == "old"


async def test_expired_code_cannot_reset(recovery):
    client, mail = recovery
    await service.send_code("reset-test@example.com")
    client.expire(service._key("reset-test@example.com"), 0)
    with pytest.raises(PermissionError):
        service.reset_password.__wrapped__("reset-test@example.com", mail.call_args.kwargs["code"], crypt("New-password-123"))


async def test_unknown_email_and_cooldown(recovery):
    _, mail = recovery
    await service.send_code("missing@example.com")
    mail.assert_not_called()
    with pytest.raises(ValueError, match="wait"):
        await service.send_code("missing@example.com")


async def test_smtp_failure_removes_code(recovery):
    client, mail = recovery
    mail.side_effect = RuntimeError("SMTP unavailable")
    with pytest.raises(ValueError, match="Unable to send"):
        await service.send_code("reset-test@example.com")
    assert not client.exists(service._key("reset-test@example.com"))
