"""Webhook delivery for ``img2 bug`` and ``img2 feedback`` reports.

The webhook sits between the CLI and an n8n workflow, which is responsible
for actually sending email and/or filing the report.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

WEBHOOK_URL_ENV = "IMG2_WEBHOOK_URL"
WEBHOOK_TOKEN_ENV = "IMG2_WEBHOOK_TOKEN"
DEFAULT_WEBHOOK_URL = "https://image2.theappfoundry.tech/api/bug"

IMAGE2_DIR = Path.home() / ".image2"
CONFIG_FILE = IMAGE2_DIR / "config.json"


class WebhookError(RuntimeError):
    """Raised when the webhook request fails."""

def _get_or_create_token() -> str | None:
    """Return a persisted webhook token, generating one on first use.

    Checked into :data:`CONFIG_FILE` so every ``img2 bug``/``feedback``
    run authenticates without the user ever setting an env var. Returns
    ``None`` on any I/O or parse failure (e.g. unwritable home directory)
    — a missing token must never block sending a report, it just goes
    out unauthenticated.
    """
    data: dict = {}
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text())
            token = data.get("webhook_token")
            if token:
                return token
    except (OSError, json.JSONDecodeError):
        data = {}
    token = secrets.token_hex(32)
    try:
        data["webhook_token"] = token
        IMAGE2_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(data))
        CONFIG_FILE.chmod(0o600)
    except OSError:
        pass
    return token


def send_webhook(payload: dict, timeout: float = 10.0) -> None:
    """POST *payload* as JSON to the img2 report endpoint.

    Defaults to :data:`DEFAULT_WEBHOOK_URL`; set ``$IMG2_WEBHOOK_URL`` to
    override (e.g. for staging). Sends a ``Bearer`` token in the
    ``Authorization`` header: ``$IMG2_WEBHOOK_TOKEN`` if set, otherwise a
    token silently generated and persisted on first run (see
    :func:`_get_or_create_token`).
    """
    url = os.environ.get(WEBHOOK_URL_ENV, DEFAULT_WEBHOOK_URL)
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = os.environ.get(WEBHOOK_TOKEN_ENV) or _get_or_create_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            pass
    except (urllib.error.URLError, OSError) as exc:
        raise WebhookError(f"failed to reach webhook: {exc}") from exc
