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
WEBHOOK_TOKEN_ENV = "IMG2_BUG_TOKEN"
DEFAULT_WEBHOOK_URL = "https://image2.theappfoundry.tech/api/bug"


class WebhookError(RuntimeError):
    """Raised when the webhook request fails."""


def send_webhook(payload: dict, timeout: float = 10.0) -> None:
    """POST *payload* as JSON to the img2 report endpoint.

    Defaults to :data:`DEFAULT_WEBHOOK_URL`; set ``$IMG2_WEBHOOK_URL`` to
    override (e.g. for staging). The server (``app/api/bug/route.ts``)
    validates the request against a single shared secret read from its
    own ``IMG2_BUG_TOKEN`` env var, so the client must set ``$IMG2_BUG_TOKEN``
    to that same value — there is no per-client token; a locally generated
    one can never match and would just 401 silently.
    """
    token = os.environ.get(WEBHOOK_TOKEN_ENV)
    if not token:
        raise WebhookError(
            f"{WEBHOOK_TOKEN_ENV} is not set. Set it to the shared report "
            "token (ask the maintainer) before sending a report."
        )
    url = os.environ.get(WEBHOOK_URL_ENV, DEFAULT_WEBHOOK_URL)
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except (urllib.error.URLError, OSError) as exc:
        raise WebhookError(f"failed to reach webhook: {exc}") from exc
