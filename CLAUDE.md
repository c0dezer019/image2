## Runtime Gotchas

- `write_png_from_html` saves to CWD then `shutil.move` — html2image can't target arbitrary paths directly.
- CLI usage: `img2 [ascii|ansi] ...` — subcommand `style`, no `--mode` flag.
- ANSI PNG preview (`--png`) always renders truecolor regardless of `ansi --color` mode; `.ans` file carries quantized color.
- `img2ascii.image_to_ascii_html` runs its own enhancement inline — does NOT call `load_and_enhance`. Changes to shared enhancement logic need mirroring in both modules.
- `ascii_chars` is reversed (index 0 = darkest). Brightness maps to `lum/255 * (len-1)`.
- ANSI cell aspect = 1.0 (half-block doubles vertical res). ASCII cell aspect = 0.75 (char_width/line_height = 0.6/0.8).
- `pico_ascii` installs via SSH git ref — requires SSH key; `pip install -e .` fails without it.

## Architecture Decisions

- Flat module layout: `image2.py` (CLI), `img2ansi.py`, `img2ascii.py`, `imgcommon.py`. No package dir.
- `build/` and `*.egg-info/` are artifacts. Never edit.

## Conventions Not Enforced by Tooling

- Tests live in `tests/`, not next to source.
- Run tests: `venv/bin/pytest`
- Lint: `venv/bin/flake8` (line-length 79 via Black config)
