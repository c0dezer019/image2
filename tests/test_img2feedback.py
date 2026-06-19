from unittest.mock import MagicMock, patch

import pytest

import img2feedback
import img2webhook


def test_cmd_feedback_sends_webhook():
    args = MagicMock()
    args.message = "love the tool"
    with patch.object(img2webhook, "send_webhook") as mock_send:
        img2feedback.cmd_feedback(args)
    payload = mock_send.call_args[0][0]
    assert payload["type"] == "feedback"
    assert payload["message"] == "love the tool"


def test_cmd_feedback_prompts_when_message_missing():
    args = MagicMock()
    args.message = None
    with patch("builtins.input", return_value="great app"), patch.object(
        img2webhook, "send_webhook"
    ) as mock_send:
        img2feedback.cmd_feedback(args)
    assert mock_send.call_args[0][0]["message"] == "great app"


def test_cmd_feedback_exits_on_empty_message():
    args = MagicMock()
    args.message = None
    with patch("builtins.input", return_value="  "):
        with pytest.raises(SystemExit):
            img2feedback.cmd_feedback(args)


def test_cmd_feedback_exits_on_webhook_error():
    args = MagicMock()
    args.message = "hi"
    with patch.object(
        img2webhook,
        "send_webhook",
        side_effect=img2webhook.WebhookError("x"),
    ):
        with pytest.raises(SystemExit):
            img2feedback.cmd_feedback(args)
