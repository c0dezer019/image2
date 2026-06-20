import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

import img2webhook


def test_send_webhook_uses_default_url(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_URL_ENV, raising=False)
    monkeypatch.setenv(img2webhook.WEBHOOK_TOKEN_ENV, "secret123")
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
    monkeypatch.setenv(img2webhook.WEBHOOK_TOKEN_ENV, "secret123")
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


def test_send_webhook_raises_when_token_unset(monkeypatch):
    monkeypatch.delenv(img2webhook.WEBHOOK_TOKEN_ENV, raising=False)
    with pytest.raises(img2webhook.WebhookError):
        img2webhook.send_webhook({"type": "bug"})


def test_send_webhook_raises_on_failure(monkeypatch):
    monkeypatch.setenv(
        img2webhook.WEBHOOK_URL_ENV, "http://example.com/hook"
    )
    monkeypatch.setenv(img2webhook.WEBHOOK_TOKEN_ENV, "secret123")
    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ):
        with pytest.raises(img2webhook.WebhookError):
            img2webhook.send_webhook({"type": "bug"})
