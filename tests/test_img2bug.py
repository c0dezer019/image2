from unittest.mock import MagicMock, patch

import img2bug
import img2log
import img2webhook


def _args(**overrides):
    args = MagicMock()
    args.message = overrides.get("message")
    args.command = overrides.get("command")
    args.log_file = overrides.get("log_file")
    args.log_lines = overrides.get("log_lines", 50)
    return args


def test_cmd_bug_uses_provided_fields():
    args = _args(message="crashes on load", command="img2 ascii x.png")
    with patch.object(
        img2log, "read_log_tail", return_value="traceback..."
    ), patch.object(img2bug, "_copy_to_clipboard") as mock_copy, patch.object(
        img2webhook, "send_webhook"
    ) as mock_send:
        img2bug.cmd_bug(args)
    payload = mock_send.call_args[0][0]
    assert payload["description"] == "crashes on load"
    assert payload["command"] == "img2 ascii x.png"
    assert payload["log"] == "traceback..."
    mock_copy.assert_called_once()


def test_cmd_bug_auto_detects_command_from_history():
    args = _args(message="crashes")
    with patch.object(
        img2log, "get_last_command", return_value="img2 ansi y.png"
    ), patch.object(img2log, "read_log_tail", return_value=""), patch.object(
        img2bug, "_copy_to_clipboard"
    ), patch.object(img2webhook, "send_webhook") as mock_send:
        img2bug.cmd_bug(args)
    assert mock_send.call_args[0][0]["command"] == "img2 ansi y.png"


def test_cmd_bug_prompts_for_missing_description():
    args = _args(command="img2 ascii x.png")
    with patch("builtins.input", return_value="it broke"), patch.object(
        img2log, "read_log_tail", return_value=""
    ), patch.object(img2bug, "_copy_to_clipboard"), patch.object(
        img2webhook, "send_webhook"
    ) as mock_send:
        img2bug.cmd_bug(args)
    assert mock_send.call_args[0][0]["description"] == "it broke"


def test_cmd_bug_prompts_for_missing_command_when_no_history():
    args = _args(message="crashes")
    with patch.object(
        img2log, "get_last_command", return_value=None
    ), patch("builtins.input", return_value=""), patch.object(
        img2log, "read_log_tail", return_value=""
    ), patch.object(img2bug, "_copy_to_clipboard"), patch.object(
        img2webhook, "send_webhook"
    ) as mock_send:
        img2bug.cmd_bug(args)
    assert mock_send.call_args[0][0]["command"] is None


def test_cmd_bug_continues_when_webhook_fails():
    args = _args(message="crashes", command="img2 ascii x.png")
    with patch.object(
        img2log, "read_log_tail", return_value=""
    ), patch.object(img2bug, "_copy_to_clipboard") as mock_copy, patch.object(
        img2webhook,
        "send_webhook",
        side_effect=img2webhook.WebhookError("no url"),
    ):
        img2bug.cmd_bug(args)
    mock_copy.assert_called_once()
