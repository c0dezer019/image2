"""img2 logging — app log + command history for ``img2 bug`` reports."""
from __future__ import annotations

import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

IMAGE2_DIR = Path.home() / ".image2"
LOG_FILE = IMAGE2_DIR / "img2.log"
HISTORY_FILE = IMAGE2_DIR / "history.log"

# Subcommands excluded when looking up "the command that caused it" for a
# bug report, since they're never themselves the cause of a render bug.
_SKIP_STYLES = {"bug", "feedback"}

_logger: logging.Logger | None = None


def get_logger() -> logging.Logger:
    """Return the shared ``img2`` app logger, configuring it on first use.

    Falls back to a no-op handler if the log file can't be opened (e.g. an
    unwritable home directory), since logging must never be the reason a
    command fails.
    """
    global _logger
    if _logger is not None:
        return _logger
    logger = logging.getLogger("img2")
    logger.setLevel(logging.INFO)
    try:
        IMAGE2_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_000_000, backupCount=3
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
    except OSError:
        handler = logging.NullHandler()
    logger.addHandler(handler)
    _logger = logger
    return logger


def log_invocation(argv: list[str]) -> None:
    """Append *argv* (e.g. ``sys.argv``) to the command history file.

    Best-effort: an unwritable home directory must not block the
    requested subcommand from running, since this only enriches later
    bug reports.
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "argv": argv,
    }
    try:
        IMAGE2_DIR.mkdir(parents=True, exist_ok=True)
        with HISTORY_FILE.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def get_last_command() -> str | None:
    """Return the most recently logged command, skipping bug/feedback runs."""
    if not HISTORY_FILE.exists():
        return None
    for line in reversed(HISTORY_FILE.read_text().splitlines()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        argv = entry.get("argv") or []
        style = argv[1] if len(argv) > 1 else None
        if style in _SKIP_STYLES:
            continue
        return " ".join(argv)
    return None


def read_log_tail(n: int = 50, path: Path | None = None) -> str:
    """Return the last *n* lines of the app log file (or *path*)."""
    log_path = path or LOG_FILE
    if not log_path.exists():
        return ""
    lines = log_path.read_text().splitlines()
    return "\n".join(lines[-n:])
