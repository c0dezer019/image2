"""img2 ui — spawn Image2-Web + server locally via Docker Compose."""
from __future__ import annotations

import http.client
import importlib.resources as _pkg
import json
import mimetypes
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as _uuid
import webbrowser
from pathlib import Path

SERVER_URL = "http://localhost:8000"
WEB_URL = "http://localhost:3000"
SERVER_PORT = 8000
WEB_PORT = 3000
HEALTH_TIMEOUT = 30

COMPOSE_DIR = Path.home() / ".image2"
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yml"

# NOTE: the brief's COMPOSE_YAML omits the web service env var. The design
# spec (docs/superpowers/specs/2026-06-17-img2-ui-local-server-design.md)
# explicitly requires NEXT_PUBLIC_IMAGE2_SERVER_URL on the web service so the
# browser-side Next.js app knows where to reach the server. Added here.
COMPOSE_YAML = (
    _pkg.files("_img2ui_data").joinpath("docker-compose.yml").read_text()
)


def _ensure_compose_file() -> None:
    COMPOSE_DIR.mkdir(parents=True, exist_ok=True)
    COMPOSE_FILE.write_text(COMPOSE_YAML)


def check_docker() -> bool:
    """Return True if the docker binary is available on PATH."""
    return shutil.which("docker") is not None


def check_port_free(port: int) -> bool:
    """Return True if *port* is not currently bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(("localhost", port))
            return False
        except (ConnectionRefusedError, OSError):
            return True


def start_stack() -> None:
    """Pull the latest images and start the compose stack detached."""
    _ensure_compose_file()
    subprocess.run(
        [
            "docker", "compose", "-f", str(COMPOSE_FILE),
            "up", "-d", "--pull", "always",
        ],
        check=True,
    )


def stop_stack() -> None:
    """Tear down the compose stack."""
    _ensure_compose_file()
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],
        check=True,
    )


def wait_for_server(timeout: int = HEALTH_TIMEOUT) -> bool:
    """Poll ``/health`` until the server responds or *timeout* seconds pass.

    Returns True on success, False on timeout.
    """
    deadline = time.monotonic() + timeout
    delay = 0.5
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"{SERVER_URL}/health", timeout=2
            ):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(delay)
            delay = min(delay * 2, 5.0)
    return False


def upload_file(path: str) -> str:
    """POST *path* to ``/upload`` as multipart/form-data.

    Returns the ``session_id`` from the JSON response.
    """
    boundary = _uuid.uuid4().hex
    content_type = (
        mimetypes.guess_type(path)[0] or "application/octet-stream"
    )
    filename = Path(path).name

    with open(path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file";'
        f' filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    conn = http.client.HTTPConnection("localhost", SERVER_PORT)
    try:
        conn.request(
            "POST",
            "/upload",
            body=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            },
        )
        resp = conn.getresponse()
        if resp.status != 200:
            raise RuntimeError(f"/upload failed ({resp.status})")
        data = json.loads(resp.read())
        return data["session_id"]
    finally:
        conn.close()


def open_ui(
    session_id: str | None = None,
    params: dict | None = None,
) -> None:
    """Open the web UI in the default browser.

    With no arguments opens the bare ``WEB_URL``. When *session_id* is
    provided, appends ``session=<id>`` plus any extra *params* as query
    string key/value pairs.
    """
    if not session_id:
        webbrowser.open(WEB_URL)
        return
    query_dict = {"session": session_id}
    if params:
        query_dict.update(params)
    query = urllib.parse.urlencode(query_dict)
    webbrowser.open(f"{WEB_URL}?{query}")


def _print_docker_missing() -> None:
    print(
        "Docker not found. Install Docker Desktop:\n"
        "  https://docs.docker.com/get-docker/\n"
        "Or run without Docker: img2 ui --no-docker",
        file=sys.stderr,
    )


def _print_port_conflict(port: int) -> None:
    print(
        f"Port {port} is already in use. Free it and retry.",
        file=sys.stderr,
    )


def _start_and_wait() -> bool:
    """Start the stack and wait for the server. Returns False on timeout."""
    print("Starting Image2-Web...")
    start_stack()
    print(f"Waiting for server (up to {HEALTH_TIMEOUT}s)...")
    if not wait_for_server():
        result = subprocess.run(
            [
                "docker", "compose", "-f", str(COMPOSE_FILE),
                "logs", "server", "--tail=30",
            ],
            capture_output=True,
            text=True,
        )
        print(result.stdout or result.stderr, file=sys.stderr)
        print("Server failed to start. See logs above.", file=sys.stderr)
        return False
    return True


def _check_prerequisites() -> bool:
    """Check Docker and ports. Prints errors and returns False on failure."""
    if not check_docker():
        _print_docker_missing()
        return False
    for port in (SERVER_PORT, WEB_PORT):
        if not check_port_free(port):
            _print_port_conflict(port)
            return False
    return True


def cmd_ui(args) -> None:
    """Entry point for the ``img2 ui`` subcommand."""
    if args.stop:
        stop_stack()
        print("Stack stopped.")
        return

    if args.no_docker:
        print(
            "--no-docker fallback not yet implemented.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _check_prerequisites():
        sys.exit(1)

    if not _start_and_wait():
        sys.exit(1)

    open_ui()
    print(f"Image2 running at {WEB_URL}")
    print("Stop with: img2 ui --stop")


def cmd_ui_with_file(path: str, mode: str, params: dict) -> None:
    """Called by ascii/ansi ``--ui`` flag.

    Skips the CLI render path; uploads *path* and opens the UI pre-seeded
    with the session and render parameters.
    """
    if not _check_prerequisites():
        sys.exit(1)

    if not _start_and_wait():
        sys.exit(1)

    session_id = upload_file(path)
    open_ui(session_id=session_id, params={"mode": mode, **params})
    print(f"Image2 running at {WEB_URL}")
    print("Stop with: img2 ui --stop")
