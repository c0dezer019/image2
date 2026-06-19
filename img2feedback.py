"""img2 feedback — send a feedback message via the configured webhook."""
from __future__ import annotations

import sys
from datetime import datetime, timezone

import img2webhook


def cmd_feedback(args) -> None:
    """Entry point for the ``img2 feedback`` subcommand."""
    message = args.message or input("Feedback: ").strip()
    if not message:
        print("Error: feedback message cannot be empty.", file=sys.stderr)
        sys.exit(1)

    payload = {
        "type": "feedback",
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        img2webhook.send_webhook(payload)
    except img2webhook.WebhookError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Thanks! Your feedback has been sent.")
