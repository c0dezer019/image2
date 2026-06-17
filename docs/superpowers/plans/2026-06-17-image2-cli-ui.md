# image2 CLI UI Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `img2 ui` subcommand and `--ui` flag to the image2 CLI, spawning a Docker Compose stack (image2-web + server) on localhost and opening the browser, with optional session pre-seed when `--ui` is combined with `ascii`/`ansi` subcommands.

**Architecture:** New `img2ui.py` module handles all orchestration: Docker availability check, port conflict detection, Compose stack management (compose YAML embedded as string, written to `~/.image2/`), server health polling, file upload via `/upload`, and browser open. `image2.py` wires the `ui` subcommand and `--ui` flag. When `--ui` is passed to `ascii`/`ansi`, the normal render pipeline is skipped entirely and `img2ui.cmd_ui_with_file` is called instead.

**Tech Stack:** Python 3.14, stdlib only (`subprocess`, `socket`, `urllib.request`, `http.client`, `webbrowser`, `shutil`, `importlib.metadata`), pytest, Docker Compose V2 (`docker compose` not `docker-compose`).

## Global Constraints

- Line-length 79 (Black config in pyproject.toml).
- No third-party deps added to `pyproject.toml` — `img2ui.py` uses stdlib only.
- Docker Compose V2 syntax: `docker compose` (space, not hyphen).
- Tests mock all subprocess/network calls — no Docker required in CI.
- Run tests: `.venv/bin/pytest`
- Run linter: `.venv/bin/flake8`
- `img2ui.py` added to `py-modules` in `pyproject.toml`.
- **Plan 1 prerequisite:** `c0dezer019/image2-web:latest` Docker image must exist on Docker Hub before `img2 ui` can pull it. Complete Image2-Web plan first.

---

### Task 1: img2ui.py — core orchestration module

**Files:**
- Create: `img2ui.py`
- Create: `tests/test_img2ui.py`

**Interfaces:**
- Produces:
  - `check_docker() -> bool`
  - `check_port_free(port: int) -> bool`
  - `start_stack() -> None` — `docker compose up -d --pull always`
  - `stop_stack() -> None` — `docker compose down`
  - `wait_for_server(timeout: int = 30) -> bool`
  - `upload_file(path: str) -> str` — returns `session_id`
  - `open_ui(session_id: str | None, params: dict | None) -> None`
  - `cmd_ui(args) -> None` — entry for `img2 ui` subcommand
  - `cmd_ui_with_file(path: str, mode: str, params: dict) -> None` — called by `--ui` flag

- [ ] **Step 1: Write failing tests**

Create `tests/test_img2ui.py`:

```python
import http.client
import json
import socket
import subprocess
import urllib.error
import webbrowser
from unittest.mock import MagicMock, call, patch

import pytest

import img2ui


def test_check_docker_found():
    with patch("shutil.which", return_value="/usr/bin/docker"):
        assert img2ui.check_docker() is True


def test_check_docker_not_found():
    with patch("shutil.which", return_value=None):
        assert img2ui.check_docker() is False


def test_check_port_free_when_free():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.connect.side_effect = ConnectionRefusedError
    with patch("socket.socket", return_value=mock_sock):
        assert img2ui.check_port_free(8000) is True


def test_check_port_free_when_in_use():
    mock_sock = MagicMock()
    mock_sock.__enter__ = lambda s: s
    mock_sock.__exit__ = MagicMock(return_value=False)
    mock_sock.connect.return_value = None
    with patch("socket.socket", return_value=mock_sock):
        assert img2ui.check_port_free(8000) is False


def test_wait_for_server_success():
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert img2ui.wait_for_server(timeout=5) is True


def test_wait_for_server_timeout():
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("err")):
        with patch("time.sleep"):
            result = img2ui.wait_for_server(timeout=1)
    assert result is False


def test_start_stack_calls_compose_up():
    with patch("subprocess.run") as mock_run:
        with patch.object(img2ui, "_ensure_compose_file"):
            img2ui.start_stack()
    args = mock_run.call_args[0][0]
    assert "docker" in args
    assert "compose" in args
    assert "up" in args
    assert "-d" in args


def test_stop_stack_calls_compose_down():
    with patch("subprocess.run") as mock_run:
        with patch.object(img2ui, "_ensure_compose_file"):
            img2ui.stop_stack()
    args = mock_run.call_args[0][0]
    assert "down" in args


def test_open_ui_no_session():
    with patch("webbrowser.open") as mock_open:
        img2ui.open_ui()
    mock_open.assert_called_once_with(img2ui.WEB_URL)


def test_open_ui_with_session_and_params():
    with patch("webbrowser.open") as mock_open:
        img2ui.open_ui(session_id="abc", params={"mode": "ascii", "contrast": "1.2"})
    url = mock_open.call_args[0][0]
    assert "session=abc" in url
    assert "mode=ascii" in url
    assert "contrast=1.2" in url


def test_upload_file_returns_session_id(tmp_path):
    png = tmp_path / "test.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(
        {"session_id": "test-uuid", "expires_in": 3600}
    ).encode()

    mock_conn = MagicMock()
    mock_conn.getresponse.return_value = mock_resp

    with patch("http.client.HTTPConnection", return_value=mock_conn):
        session_id = img2ui.upload_file(str(png))

    assert session_id == "test-uuid"


def test_cmd_ui_stop():
    args = MagicMock()
    args.stop = True
    args.no_docker = False
    with patch.object(img2ui, "stop_stack") as mock_stop:
        img2ui.cmd_ui(args)
    mock_stop.assert_called_once()


def test_cmd_ui_exits_when_docker_missing():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=False):
        with pytest.raises(SystemExit):
            img2ui.cmd_ui(args)


def test_cmd_ui_exits_on_port_conflict():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=True):
        with patch.object(img2ui, "check_port_free", return_value=False):
            with pytest.raises(SystemExit):
                img2ui.cmd_ui(args)


def test_cmd_ui_full_happy_path():
    args = MagicMock()
    args.stop = False
    args.no_docker = False
    with patch.object(img2ui, "check_docker", return_value=True), \
         patch.object(img2ui, "check_port_free", return_value=True), \
         patch.object(img2ui, "start_stack"), \
         patch.object(img2ui, "wait_for_server", return_value=True), \
         patch.object(img2ui, "open_ui") as mock_open:
        img2ui.cmd_ui(args)
    mock_open.assert_called_once_with()


def test_cmd_ui_with_file_happy_path(tmp_path):
    png = tmp_path / "img.png"
    png.write_bytes(b"data")
    with patch.object(img2ui, "check_docker", return_value=True), \
         patch.object(img2ui, "check_port_free", return_value=True), \
         patch.object(img2ui, "start_stack"), \
         patch.object(img2ui, "wait_for_server", return_value=True), \
         patch.object(img2ui, "upload_file", return_value="sess-xyz"), \
         patch.object(img2ui, "open_ui") as mock_open:
        img2ui.cmd_ui_with_file(str(png), "ascii", {"contrast": "1.2"})
    mock_open.assert_called_once_with(
        session_id="sess-xyz",
        params={"mode": "ascii", "contrast": "1.2"},
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_img2ui.py -v
```

Expected: FAIL — `img2ui` module does not exist.

- [ ] **Step 3: Create img2ui.py**

```python
"""img2 ui — spawn Image2-Web + server locally via Docker Compose."""
from __future__ import annotations

import http.client
import json
import mimetypes
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
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

COMPOSE_YAML = """\
services:
  server:
    image: c0dezer019/image2-server:latest
    environment:
      - LOCAL_MODE=true
    ports:
      - "8000:8000"
    networks:
      - image2-net

  web:
    image: c0dezer019/image2-web:latest
    ports:
      - "3000:3000"
    depends_on:
      - server
    networks:
      - image2-net

networks:
  image2-net:
    driver: bridge
"""


def _ensure_compose_file() -> None:
    COMPOSE_DIR.mkdir(parents=True, exist_ok=True)
    if not COMPOSE_FILE.exists():
        COMPOSE_FILE.write_text(COMPOSE_YAML)


def check_docker() -> bool:
    return shutil.which("docker") is not None


def check_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(("localhost", port))
            return False
        except ConnectionRefusedError:
            return True


def start_stack() -> None:
    _ensure_compose_file()
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE),
         "up", "-d", "--pull", "always"],
        check=True,
    )


def stop_stack() -> None:
    _ensure_compose_file()
    subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "down"],
        check=True,
    )


def wait_for_server(timeout: int = HEALTH_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"{SERVER_URL}/health", timeout=2
            ):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(1)
    return False


def upload_file(path: str) -> str:
    """POST file to /upload, return session_id."""
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


def open_ui(
    session_id: str | None = None,
    params: dict | None = None,
) -> None:
    if not session_id:
        webbrowser.open(WEB_URL)
        return
    query_parts = [f"session={session_id}"]
    if params:
        for k, v in params.items():
            query_parts.append(f"{k}={v}")
    webbrowser.open(f"{WEB_URL}?{'&'.join(query_parts)}")


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
            ["docker", "compose", "-f", str(COMPOSE_FILE),
             "logs", "server", "--tail=30"],
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
    if args.stop:
        stop_stack()
        print("Stack stopped.")
        return

    if args.no_docker:
        print("--no-docker fallback not yet implemented.", file=sys.stderr)
        sys.exit(1)

    if not _check_prerequisites():
        sys.exit(1)

    if not _start_and_wait():
        sys.exit(1)

    open_ui()
    print(f"Image2 running at {WEB_URL}")
    print("Stop with: img2 ui --stop")


def cmd_ui_with_file(path: str, mode: str, params: dict) -> None:
    """Called by ascii/ansi --ui flag. Skips CLI render; opens UI pre-seeded."""
    if not _check_prerequisites():
        sys.exit(1)

    if not _start_and_wait():
        sys.exit(1)

    session_id = upload_file(path)
    open_ui(session_id=session_id, params={"mode": mode, **params})
    print(f"Image2 running at {WEB_URL}")
    print("Stop with: img2 ui --stop")
```

- [ ] **Step 4: Run tests**

```bash
.venv/bin/pytest tests/test_img2ui.py -v
```

Expected: all pass.

- [ ] **Step 5: Run linter**

```bash
.venv/bin/flake8 img2ui.py
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add img2ui.py tests/test_img2ui.py
git commit -m "feat: add img2ui module for Docker Compose orchestration"
```

---

### Task 2: image2.py — wire ui subcommand + --ui flag

**Files:**
- Modify: `image2.py`
- Modify: `tests/test_image2.py`

**Interfaces:**
- Consumes: `img2ui.cmd_ui(args)`, `img2ui.cmd_ui_with_file(path, mode, params)` from Task 1
- Produces:
  - `img2 ui` subcommand (with `--stop` and `--no-docker` flags)
  - `--ui` flag on `ascii` and `ansi` subcommands (bypasses render, calls `cmd_ui_with_file`)

- [ ] **Step 1: Write failing tests**

Add to `tests/test_image2.py`:

```python
from unittest.mock import patch


def test_ui_subcommand_parsed():
    from image2 import build_parser
    p = build_parser()
    args = p.parse_args(["ui"])
    assert args.style == "ui"
    assert args.stop is False
    assert args.no_docker is False


def test_ui_stop_flag_parsed():
    from image2 import build_parser
    p = build_parser()
    args = p.parse_args(["ui", "--stop"])
    assert args.stop is True


def test_ascii_ui_flag_parsed():
    from image2 import build_parser
    p = build_parser()
    args = p.parse_args(["ascii", "sample.png", "--ui"])
    assert args.ui is True


def test_ansi_ui_flag_parsed():
    from image2 import build_parser
    p = build_parser()
    args = p.parse_args(["ansi", "sample.png", "--ui"])
    assert args.ui is True


def test_main_routes_ui_subcommand(tmp_path):
    from image2 import main
    import sys
    with patch("sys.argv", ["img2", "ui"]):
        with patch("img2ui.cmd_ui") as mock_cmd:
            main()
    mock_cmd.assert_called_once()


def test_main_routes_ascii_ui_flag(tmp_path):
    img = tmp_path / "test.png"
    img.write_bytes(b"data")
    from image2 import main
    with patch("sys.argv", ["img2", "ascii", str(img), "--ui"]):
        with patch("img2ui.cmd_ui_with_file") as mock_cmd:
            main()
    mock_cmd.assert_called_once()
    call_args = mock_cmd.call_args
    assert call_args[0][0] == str(img)
    assert call_args[0][1] == "ascii"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/pytest tests/test_image2.py::test_ui_subcommand_parsed tests/test_image2.py::test_ascii_ui_flag_parsed -v
```

Expected: FAIL — `ui` subcommand and `--ui` flag not registered.

- [ ] **Step 3: Add import of img2ui to image2.py**

After the existing imports in `image2.py` (after `from imgsvg import ...`), add:

```python
import img2ui
```

- [ ] **Step 4: Add ui subparser in build_parser()**

In `build_parser()`, after the `ansi_p` block and before `return p`, add:

```python
    ui_p = sub.add_parser(
        "ui",
        help="Launch Image2-Web UI locally via Docker Compose",
    )
    ui_p.add_argument(
        "--stop",
        action="store_true",
        default=False,
        help="Stop the running Docker Compose stack",
    )
    ui_p.add_argument(
        "--no-docker",
        action="store_true",
        default=False,
        help="Run without Docker (downloads release artifacts)",
    )
```

- [ ] **Step 5: Add --ui flag to ascii and ansi subparsers**

In `build_parser()`, add to `ascii_p` (after the `--min` line):

```python
    ascii_p.add_argument(
        "--ui",
        action="store_true",
        default=False,
        help="Open Image2-Web UI pre-seeded with this image and params",
    )
```

Add the same to `ansi_p` (after `--png`):

```python
    ansi_p.add_argument(
        "--ui",
        action="store_true",
        default=False,
        help="Open Image2-Web UI pre-seeded with this image and params",
    )
```

- [ ] **Step 6: Route ui subcommand and --ui flag in main()**

In `main()`, change the existing validation block that checks `args.input`. Replace:

```python
    if not args.input or not os.path.exists(args.input):
        print("Error: a valid input image path is required.")
        sys.exit(1)
```

With:

```python
    if args.style == "ui":
        img2ui.cmd_ui(args)
        return

    if not args.input or not os.path.exists(args.input):
        print("Error: a valid input image path is required.")
        sys.exit(1)
```

Then, after the `resolve_enhance_params` call and before the `if args.style == "ansi":` dispatch, add:

```python
    if getattr(args, "ui", False):
        ui_params = {
            "contrast": str(args.contrast),
            "brightness": str(args.brightness),
            "sharpness": str(args.sharpness),
            "saturate": str(args.saturate),
            "min_lum": str(args.min_lum),
            "width": str(width),
        }
        img2ui.cmd_ui_with_file(args.input, args.style, ui_params)
        return
```

- [ ] **Step 7: Run all tests**

```bash
.venv/bin/pytest -v
```

Expected: all pass.

- [ ] **Step 8: Run linter**

```bash
.venv/bin/flake8 image2.py
```

Expected: no output.

- [ ] **Step 9: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add img2 ui subcommand and --ui flag to ascii/ansi"
```

---

### Task 3: pyproject.toml — register img2ui module

**Files:**
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `img2ui` included in installed package so `import img2ui` works after `pip install`

- [ ] **Step 1: Add img2ui to py-modules**

In `pyproject.toml`, find:

```toml
[tool.setuptools]
py-modules = ["image2", "img2ansi", "img2ascii", "imgcommon", "imgsvg"]
```

Replace with:

```toml
[tool.setuptools]
py-modules = ["image2", "img2ansi", "img2ascii", "imgcommon", "imgsvg", "img2ui"]
```

- [ ] **Step 2: Verify package installs correctly**

```bash
.venv/bin/pip install -e . --quiet && .venv/bin/python -c "import img2ui; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add img2ui to py-modules in pyproject.toml"
```

---

### Task 4: README — Web UI section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read current README**

```bash
cat README.md
```

- [ ] **Step 2: Add Web UI section**

Add the following section after the existing usage/CLI documentation section:

```markdown
## Web UI

`img2 ui` spins up the [Image2-Web](https://github.com/c0dezer019/image2-web)
interface locally via Docker Compose and opens your browser.

### Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (or Docker Engine + Compose V2)

### Usage

```bash
# Spin up and open browser
img2 ui

# Open UI pre-seeded with an image and conversion params
img2 ascii photo.jpg -c 1.2 -B 1.1 --ui
img2 ansi photo.jpg --mode truecolor --ui

# Stop the stack
img2 ui --stop
```

When running locally, the server operates with:
- Rate limiting **disabled**
- Output size caps **lifted** (no 600×600 / 250,000-cell limit)

### Without Docker

```bash
img2 ui --no-docker
```

Downloads a pinned server wheel and frontend build from GitHub Releases and
serves them locally without Docker. Internet required on first run; artifacts
are cached in `~/.image2/`.

### How --ui Works

When `--ui` is passed to `ascii` or `ansi`, the CLI skips rendering to disk
and instead:

1. Starts the Docker Compose stack (or reuses it if already running)
2. Uploads the source image to the local server → receives a `session_id`
3. Opens `http://localhost:3000?session=<id>&mode=ascii&contrast=1.2&...`
4. The browser UI auto-loads the image and parameters, then converts

The Docker Compose stack runs two containers on a shared `image2-net` network:
- `c0dezer019/image2-server:latest` on port 8000
- `c0dezer019/image2-web:latest` on port 3000
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add Web UI section to README"
```
