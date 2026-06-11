## Runtime Gotchas

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
- `build/` and `*.egg-info/` are artifacts. Never edit.

## Conventions Not Enforced by Tooling

- Tests live in `tests/`, not next to source.
- Run tests: `venv/bin/pytest`
- Lint: `venv/bin/flake8` (line-length 79 via Black config)
