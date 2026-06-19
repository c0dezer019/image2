"""img2 bug — capture a bug report, copy it to the clipboard, and send it
via the configured webhook."""
from __future__ import annotations

import platform
import sys
from datetime import datetime, timezone

import img2log
import img2webhook

try:
    import pyperclip
except ImportError:
    pyperclip = None


def _build_report(description: str, command: str | None, log: str) -> str:
    lines = [
        "img2 bug report",
        f"Description: {description}",
        f"Command: {command or '(unknown)'}",
    ]
    if log:
        lines.append("Recent log:")
        lines.append(log)
    return "\n".join(lines)


def _copy_to_clipboard(text: str) -> None:
    if pyperclip is None:
        print(
            "Warning: pyperclip not installed; skipping clipboard copy.",
            file=sys.stderr,
        )
        return
    try:
        pyperclip.copy(text)
    except Exception as exc:
        print(
            f"Warning: could not copy to clipboard: {exc}", file=sys.stderr
        )


def cmd_bug(args) -> None:
    """Entry point for the ``img2 bug`` subcommand."""
    description = args.message or input("Describe the bug: ").strip()
    if not description:
        print("Error: bug description cannot be empty.", file=sys.stderr)
        sys.exit(1)

    command = args.command or img2log.get_last_command()
    if not command:
        command = input(
            "Command that caused it (press Enter to skip): "
        ).strip() or None

    log = img2log.read_log_tail(args.log_lines, args.log_file)

    report = _build_report(description, command, log)
    _copy_to_clipboard(report)

    payload = {
        "type": "bug",
        "description": description,
        "command": command,
        "log": log,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python_version": sys.version,
    }
    try:
        img2webhook.send_webhook(payload)
    except img2webhook.WebhookError as exc:
        print(f"Warning: {exc}", file=sys.stderr)
        print("Bug report copied to clipboard but not sent.")
        return

    print("Bug report copied to clipboard and sent.")
