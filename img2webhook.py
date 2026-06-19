"""Webhook delivery for ``img2 bug`` and ``img2 feedback`` reports.

The webhook sits between the CLI and an n8n workflow, which is responsible
for actually sending email and/or filing the report.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

WEBHOOK_URL_ENV = "IMG2_WEBHOOK_URL"
DEFAULT_WEBHOOK_URL = "https://image2.theappfoundry.tech/bug"


class WebhookError(RuntimeError):
    """Raised when the webhook request fails."""


def send_webhook(payload: dict, timeout: float = 10.0) -> None:
    """POST *payload* as JSON to the img2 report endpoint.

    Defaults to :data:`DEFAULT_WEBHOOK_URL`; set ``$IMG2_WEBHOOK_URL`` to
    override (e.g. for staging).
    """
    url = os.environ.get(WEBHOOK_URL_ENV, DEFAULT_WEBHOOK_URL)
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except (urllib.error.URLError, OSError) as exc:
        raise WebhookError(f"failed to reach webhook: {exc}") from exc
