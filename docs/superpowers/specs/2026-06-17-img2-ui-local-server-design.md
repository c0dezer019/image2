# Design: `img2 ui` Local Server Mode

**Date:** 2026-06-17
**Status:** Approved

## Overview

Add `img2 ui` subcommand and `--ui` flag to the image2 CLI. Spawns a Docker
Compose stack (Image2-Web frontend + FastAPI server) on localhost, opens the
browser automatically. Mirrors the ComfyUI model: navigate *to* localhost,
no hosted-HTTPS mixed-content issues.

Fallback path (`--no-docker`) for users without Docker: download pinned
release artifacts from GitHub Releases, serve locally via Python.

---

## Repos Changed

### image2 (this repo)

| File | Change |
|------|--------|
| `img2ui.py` | New module — all `img2 ui` / `--ui` logic |
| `image2.py` | Wire `img2 ui` subcommand; add `--ui` flag to `ascii`/`ansi` |
| `docker-compose.yml` | New — Compose stack definition |
| `README.md` | New section: UI mode usage, Docker prereq, `--no-docker` |

### Image2-Web repo

| File | Change |
|------|--------|
| `Dockerfile` | New — production Next.js standalone image (root) |
| `.dockerignore` | New — exclude `server/`, `node_modules`, `.next` |
| `.github/workflows/docker-image.yml` | Add conditional `build-and-push-web-*` jobs |
| `server/main.py` | `LOCAL_MODE` env var; `/health` returns `local` flag; new `/upload` + `/session/<id>` endpoints |
| `lib/convert.ts` | Read `local` from health; lift client-side output size clamps when local |
| `components/` | Hide server-limit UI copy in local mode |
| `README.md` | New section: local mode, Docker usage, session pre-seed |

---

## Docker Setup

### `image2/docker-compose.yml`

```yaml
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
    environment:
      - NEXT_PUBLIC_IMAGE2_SERVER_URL=http://localhost:8000
    ports:
      - "3000:3000"
    depends_on:
      - server
    networks:
      - image2-net

networks:
  image2-net:
    driver: bridge
```

Browser calls go through host port mapping (`localhost:8000`). Container-to-container
calls use Docker DNS (`http://server:8000` on `image2-net`). Both work simultaneously.

### Image2-Web `Dockerfile` (root)

Standard Next.js standalone output build. `.dockerignore` excludes `server/`
so the server Dockerfile in `server/` is unaffected.

### GitHub Actions (`docker-image.yml`)

Add two parallel jobs alongside the existing server jobs:

- `build-and-push-web-dev` — triggers when non-`server/` files changed + branch != main
- `build-and-push-web-prod` — triggers when non-`server/` files changed + branch == main

Both jobs mirror the existing server job pattern exactly:
- `docker/setup-buildx-action@v3`
- `docker/login-action@v3`
- `docker buildx build` with `--attest type=provenance,mode=max,version=v1 --sbom=true`
- Pushes to `c0dezer019/image2-web:latest` (prod) or `c0dezer019/image2-web:dev` (dev)

Image name stored as a new repo variable (`DOCKER_WEB_IMAGE`). Build dir is root (`.`).

---

## Local Mode: Server Changes

**`server/main.py`:**

```python
LOCAL_MODE = os.getenv("LOCAL_MODE", "false").lower() == "true"
```

- When `LOCAL_MODE=true`: skip `SlowAPIMiddleware`; remove `MAX_OUTPUT_COLS/ROWS/CELLS` validation
- `/health` returns `{"status": "ok", "version": "...", "local": true|false}`
- New `/upload` endpoint: accepts multipart file, writes to `tempfile`, returns
  `{"session_id": "<uuid>", "expires_in": 3600}`
- New `/session/<session_id>` endpoint: returns the uploaded file as a blob

CORS allowlist gains `http://localhost:3000` (already present) — no change needed.

---

## Local Mode: Frontend Changes

**`lib/convert.ts`:**

- Extend `checkHealth()` return type: `{ status, version, local: boolean }`
- Store `local` flag in module-level state on app load
- When `local: true`: skip `MAX_OUTPUT_COLS`/`MAX_OUTPUT_ROWS`/`MAX_OUTPUT_CELLS`
  client-side clamps; suppress any "server limit" warning copy in components

**Session pre-seed (`?session=<id>` URL param):**

On mount, if `?session=` present:
1. Fetch `/session/<id>` → file blob
2. Populate DropZone with blob (triggers `/analyze` auto-call)
3. Apply additional URL params to controls: `contrast`, `brightness`, `sharpness`,
   `saturate`, `min_lum`, `mode`, `width`
4. Auto-trigger conversion

---

## CLI: `img2 ui` Subcommand

**Location:** `img2ui.py`

### Standalone: `img2 ui`

1. Check `docker` available (`shutil.which("docker")`) — if not, print install
   instructions and suggest `img2 ui --no-docker`
2. Detect port conflicts: `socket.connect("localhost", 8000)` and `3000` —
   exit with conflict message if occupied
3. Locate `docker-compose.yml` via `importlib.resources` (bundled with package)
4. `subprocess.run(["docker", "compose", "up", "-d"])`
5. Poll `http://localhost:8000/health` with exponential backoff, timeout 30s —
   on timeout, print `docker compose logs server` output and exit
6. `webbrowser.open("http://localhost:3000")`
7. Print: `Stack running. Stop with: img2 ui --stop`

### Stop: `img2 ui --stop`

`subprocess.run(["docker", "compose", "down"])` from compose file location.

### `--ui` flag on `ascii`/`ansi` subcommands

`img2 ascii sample.png -c 1.2 -b 1.1 --ui`

Steps 1–5 same as standalone. Then:

6. POST image file to `http://localhost:8000/upload` → `session_id`
7. Build URL: `http://localhost:3000?session=<id>&mode=ascii&contrast=1.2&brightness=1.1&...`
   (all CLI params that have frontend equivalents become query params)
8. `webbrowser.open(url)`
9. Print: `Stack running. Stop with: img2 ui --stop`

When `--ui` is passed, CLI conversion is **skipped entirely** — the browser
UI handles conversion via the local server.

---

## Non-Docker Fallback (`--no-docker`)

`img2 ui --no-docker`

1. Determine current image2 version from `importlib.metadata`
2. Download from GitHub Releases (pinned to version):
   - `image2-server-<version>.whl`
   - `web-dist-<version>.tar.gz`
3. Install wheel into `~/.image2/venv` (created if absent)
4. Extract `web-dist` to `~/.image2/web`
5. Launch server: `~/.image2/venv/bin/uvicorn image2_server.main:app --port 8000`
6. Serve frontend: uvicorn static mount or `python -m http.server 3000` from `~/.image2/web`
7. Same health-poll + browser-open flow

Artifacts cached in `~/.image2/`; re-download only when version changes.

---

## Error Handling

| Condition | Behavior |
|-----------|----------|
| Docker not installed | Print Docker install URL, suggest `--no-docker` |
| Port 8000 or 3000 in use | Print conflict message, name the occupying process if detectable, exit |
| Health check timeout (30s) | Print `docker compose logs server` tail, suggest retry |
| `/upload` file too large | Server returns 413; CLI prints friendly error |
| `--no-docker` download fails | Print GitHub Releases URL for manual download |

---

## README Updates

### image2 `README.md`

New **"Web UI"** section covering:
- Prerequisites: Docker Desktop / Docker Engine
- `img2 ui` — spin up and open browser
- `img2 ui --stop` — tear down stack
- `--ui` flag on `ascii`/`ansi` — open UI pre-seeded with image + params
- `--no-docker` fallback for Docker-free environments

### Image2-Web `README.md`

New **"Local Mode"** section covering:
- What local mode is and how it differs from the hosted version
- Lifted limits (rate limiting, output size caps)
- `LOCAL_MODE` env var for self-hosters
- Session pre-seed URL params (for developers building on the API)

---

## Testing

### image2

`tests/test_img2ui.py` — mock `subprocess.run`, `socket.connect`, `webbrowser.open`,
`urllib.request`. No Docker required in CI. Cover:
- Docker not found path
- Port conflict detection
- Health poll timeout
- Successful startup + browser open
- `--ui` flag session upload + URL construction
- `--stop` teardown

### Image2-Web

Extend existing vitest suite:
- `checkHealth()` returns `local: true/false` correctly
- Client-side clamps disabled when `local: true`
- `?session=` param triggers pre-seed flow (mock `/session/<id>` endpoint)
