## Runtime Gotchas

- `img2 ui` subcommand: spawns Image2-Web + server via Docker Compose; reuses stack if ports already bound.
- Compose file deployed to `~/.image2/docker-compose.yml` at first `img2 ui` run (via `importlib.resources` from `_img2ui_data/`).
- CLI usage: `img2 [ascii|ansi] ...` — subcommand `style`, no `--mode` flag.
- PNG output (ascii and `ansi --png`) is built via `imgsvg`: hand-rolled SVG
  (`<text>`/`<tspan>` for ascii, `<rect>` half-block pairs for ansi) +
  `cairosvg.svg2png`. Writes directly to the output path — no CWD/`shutil.move`
  workaround needed.
- `--no-gpu` is deprecated/no-op (cairosvg has no GPU path); kept for
  backward-compat with existing scripts.
- ANSI PNG preview (`--png`) always renders truecolor regardless of `ansi --color`
  mode (rendered as `<rect>` blocks, not glyphs); `.ans` file carries quantized color.
- `ascii_chars` is reversed (index 0 = darkest). Brightness maps to `lum/255 * (len-1)`.
- ANSI cell aspect = 1.0 (half-block doubles vertical res). ASCII cell aspect = 0.75 (char_width/line_height = 0.6/0.8).
- `pico_ascii` installs via SSH git ref — requires SSH key; `pip install -e .` fails without it.

## Architecture Decisions

- Flat module layout: `image2.py` (CLI), `img2ansi.py`, `img2ascii.py`, `imgcommon.py`, `imgsvg.py`. No package dir.
- `img2ui.py` + `_img2ui_data/` (Docker compose data package) — `img2 ui` stack launcher.
- `build/` and `*.egg-info/` are artifacts. Never edit.
- `packaging/` — PyInstaller spec (`img2.spec`), deb packaging (`make-deb.sh`), hooks. Never edit output artifacts.
- `packaging/img2.spec`: must include `copy_metadata('image2')` so `--version` works in bundled binary.

## Conventions Not Enforced by Tooling

- Version in `pyproject.toml` — update before tagging. Tags use `vX.Y.Z` format.
- Tests live in `tests/`, not next to source.
- Run tests: `.venv/bin/pytest`
- Lint: `.venv/bin/flake8` (line-length 79 via Black config)
- Dev deps (pytest/flake8/black/Pillow/cairosvg) pinned in `requirements.txt`;
  install via `.venv/bin/pip install -r requirements.txt`.
- Always use caveman-commit when committing and PRing
