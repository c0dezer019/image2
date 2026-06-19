import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import img2webhook


def test_send_webhook_uses_default_url(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_URL_ENV, raising=False)
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "urllib.request.urlopen", return_value=mock_resp
    ) as mock_open:
        img2webhook.send_webhook({"type": "feedback"})
    request = mock_open.call_args[0][0]
    assert request.full_url == img2webhook.DEFAULT_WEBHOOK_URL


def test_send_webhook_posts_json(monkeypatch):
    monkeypatch.setenv(
        img2webhook.WEBHOOK_URL_ENV, "http://example.com/hook"
    )
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "urllib.request.urlopen", return_value=mock_resp
    ) as mock_open:
        img2webhook.send_webhook({"type": "feedback", "message": "hi"})
    request = mock_open.call_args[0][0]
    assert request.full_url == "http://example.com/hook"
    assert json.loads(request.data) == {"type": "feedback", "message": "hi"}


def test_send_webhook_sends_bearer_token_when_set(monkeypatch):
    monkeypatch.setenv(img2webhook.WEBHOOK_TOKEN_ENV, "secret123")
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "urllib.request.urlopen", return_value=mock_resp
    ) as mock_open:
        img2webhook.send_webhook({"type": "bug"})
    request = mock_open.call_args[0][0]
    assert request.get_header("Authorization") == "Bearer secret123"


def test_send_webhook_generates_token_when_env_unset(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_TOKEN_ENV, raising=False)
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch(
        "urllib.request.urlopen", return_value=mock_resp
    ) as mock_open:
        img2webhook.send_webhook({"type": "bug"})
    request = mock_open.call_args[0][0]
    auth = request.get_header("Authorization")
    assert auth is not None and auth.startswith("Bearer ")
    assert img2webhook.CONFIG_FILE.exists()


def test_send_webhook_reuses_persisted_token(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_TOKEN_ENV, raising=False)
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
        img2webhook.send_webhook({"type": "bug"})
        first = mock_open.call_args[0][0].get_header("Authorization")
        img2webhook.send_webhook({"type": "bug"})
        second = mock_open.call_args[0][0].get_header("Authorization")
    assert first == second


def test_send_webhook_env_token_overrides_persisted(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_TOKEN_ENV, raising=False)
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        img2webhook.send_webhook({"type": "bug"})  # persists a token
    monkeypatch.setenv(img2webhook.WEBHOOK_TOKEN_ENV, "override")
    with patch(
        "urllib.request.urlopen", return_value=mock_resp
    ) as mock_open:
        img2webhook.send_webhook({"type": "bug"})
    request = mock_open.call_args[0][0]
    assert request.get_header("Authorization") == "Bearer override"


def test_get_or_create_token_survives_corrupt_config(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_TOKEN_ENV, raising=False)
    img2webhook.IMAGE2_DIR.mkdir(parents=True, exist_ok=True)
    img2webhook.CONFIG_FILE.write_text("not json")
    token = img2webhook._get_or_create_token()
    assert token


def test_send_webhook_raises_on_failure(monkeypatch):
    monkeypatch.setenv(
        img2webhook.WEBHOOK_URL_ENV, "http://example.com/hook"
    )
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ):
        with pytest.raises(img2webhook.WebhookError):
            img2webhook.send_webhook({"type": "bug"})
