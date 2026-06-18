# img2

Convert any image into terminal/text art with one command. Two render styles,
one shared image-prep core:

| Style | Subcommand | Output | Best viewed in |
|-------|------------|--------|----------------|
| Colored **ASCII** — luminance picks a glyph (`$@B%8&…`), each character keeps its own RGB color | `ascii` | PNG or HTML | Image viewer / browser |
| Traditional **ANSI** — half-block `▀` (top pixel = foreground, bottom = background) | `ansi` | `.ans` + optional PNG | Terminal (`cat`) / image viewer |

## Features

- **Auto-enhancement** — contrast, brightness, saturation, and a shadow-lift
  floor are derived from the source image's own histogram/stats by default,
  so dark, flat, or washed-out photos render closer to "as shot" with zero
  flags. Override any of them individually, or pass `--no-auto` to fall back
  to fixed historical defaults.
- **PNG output via SVG + cairosvg** — both `ascii` (PNG) and `ansi --png`
  build a small SVG (text/tspans for ascii, rect half-blocks for ansi) and
  rasterize it with `cairosvg`. No browser/Chromium dependency.
- **Three ANSI color modes** — `truecolor` (24-bit), `256` (xterm-256), and
  `bbs16` (classic 16-color CP437/VGA).
- **Auto-highlight overlay** (`--select`, ascii only) — draws a striped band
  overlay over the art, similar to a text-selection highlight.
- **Standalone HTML output** (`--html`, ascii only) — a self-contained
  zoomable `<pre>` page, no PNG rasterization involved.

---

## Examples

<img width="871" height="869" alt="jackinarmorv4_ascii" src="https://github.com/user-attachments/assets/cdef85fc-0522-4874-a52c-d26ea0bc8c20" />

<img width="720" height="600" alt="jackinarmorv4_ansi" src="https://github.com/user-attachments/assets/ec40891d-618f-470a-a5d1-267316e7c59d" />

## Requirements

- Python 3.14+
- [Pillow](https://pypi.org/project/Pillow/) — image loading/processing
- [cairosvg](https://pypi.org/project/CairoSVG/) — SVG-to-PNG rasterization
  for PNG output (requires the native `libcairo` library; installed
  automatically with cairosvg on most platforms)
- pytest — only for the test suite

### Install system-wide with pipx (recommended)

```bash
./install.sh            # or ./install.sh --editable for dev (live source changes)
```

Puts `img2` on PATH (`~/.local/bin`) in its own isolated venv — no manual venv
activation ever needed. Installs pipx via brew (or `pip install --user`) if missing.
Dependencies (Pillow, cairosvg) are pulled from `pyproject.toml` automatically.

### Install in a venv

```bash
python -m venv venv
source venv/bin/activate
pip install -e .          # exposes the `img2` command on PATH
```

Without installing, run it directly: `python3 image2.py <subcommand> <image> ...`.

---

## Usage

```bash
img2 ascii <input_image> [options]
img2 ansi  <input_image> [options]
```

The subcommand is required. Style-specific flags on the wrong subcommand are
rejected with a clear error (exit 2).

### Shared options

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | Path to the source image (positional) |
| `-o, --output` | per style (below) | Output path. Extension respected if given |
| `-w, --width` | `350` (ascii) / `80` (ansi) | Character columns |
| `-c, --contrast` | auto-detected | Contrast multiplier |
| `-s, --sharpness` | `2.5` | Sharpness multiplier (never auto-detected) |
| `-B, --brightness` | auto-detected | Brightness multiplier |
| `--saturate` | auto-detected | Saturation multiplier |
| `--min-lum` | auto-detected | Minimum HLS luminance floor (0.0–1.0) |
| `--no-auto` | off | Disable auto-detection; use fixed defaults (`contrast 1.5`, `brightness 1.0`, `saturate 1.0`, `min-lum 0.0`) for any of the above not explicitly given. Does not affect `--sharpness`. |
| `--no-gpu` | off | Deprecated, ignored (no-op; PNG output no longer uses a GPU-backed renderer) |
| `-h, --help` | — | Show help |

Auto-detection (`compute_auto_params`) inspects the source image's mean/stddev
luminance, shadow percentile, and mean saturation, and picks
contrast/brightness/saturate/min-lum that push it toward a "typical photo"
look. Any of `-c`, `-B`, `--saturate`, `--min-lum` you pass explicitly
overrides only that value.

### ascii-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--html` | off (PNG) | Save HTML instead of a PNG |
| `--img-width` | source image width | Output PNG pixel width (cairosvg scales the rendered grid to this size) |
| `--img-height` | source image height | Output PNG pixel height |
| `-b, --bg` | `#000000` | Background color |
| `--font-size` | `4.0` (HTML) / `13` (PNG) | Font size in px |
| `--select` | off | Overlay a striped auto-highlight band pattern |

Default output: `<input>_ascii.png` (or `<input>_ascii.html` with `--html`).
If neither `--img-width` nor `--img-height` is given, the PNG is rendered at
the source image's pixel dimensions.

### ansi-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `truecolor` | `truecolor` \| `256` \| `bbs16` |
| `--png` | off | Also rasterize a PNG (always truecolor, regardless of `--mode`) |

Default output: `<input>_ansi.ans` (plus `<input>_ansi.png` with `--png`).

Color modes: **truecolor** = 24-bit (needs a truecolor terminal); **256** =
xterm-256 palette; **bbs16** = classic 16-color CP437/VGA (most retro, works
almost everywhere). The `--png` preview is always rendered truecolor as
stacked `<rect>` half-blocks; the `.ans` file carries the quantized color for
whichever `--mode` was chosen.

---

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

---

## Examples

```bash
# Colored ASCII -> high-detail PNG next to the source, auto-enhanced,
# rendered at the source image's resolution
img2 ascii enterprise.jpg
#   -> enterprise_ascii.png

# Standalone zoomable HTML
img2 ascii planet.jpg --html
#   -> planet_ascii.html

# Force a 1920px-wide PNG on dark-grey, with the striped highlight overlay
img2 ascii planet.jpg --img-width 1920 -b "#101010" --select

# Wider grid, bigger glyphs, fixed (non-auto) enhancement
img2 ascii enterprise.jpg -w 500 --font-size 16 --no-auto

# Override just the contrast, leave brightness/saturation/min-lum auto
img2 ascii enterprise.jpg -c 1.8

# Lift shadows manually on a very dark photo
img2 ascii nightshot.jpg --min-lum 0.2

# Traditional ANSI, 80-col truecolor .ans
img2 ansi enterprise.jpg
cat enterprise_ansi.ans

# Retro 16-color, wider, also a PNG preview
img2 ansi planet.jpg -w 100 --mode bbs16 --png
#   -> planet_ansi.ans, planet_ansi.png

# 256-color .ans, fixed enhancement defaults
img2 ansi planet.jpg --mode 256 --no-auto

# Custom output path with explicit extension
img2 ansi enterprise.jpg -o renders/enterprise.ans --png
#   -> renders/enterprise.ans, renders/enterprise.png
```

---

## Project layout

```
imgcommon.py   Shared helpers: lift_luminance, load_and_enhance, resize_for,
               compute_auto_params, build_ascii_grid, build_halfblock_grid
imgsvg.py      Builds SVG art from pixel grids (ascii text/tspans, ansi
               half-block rects) and rasterizes it to PNG via cairosvg
img2ascii.py   Colored-ASCII HTML render backend
img2ansi.py    Traditional-ANSI .ans render backend
image2.py      Unified CLI (argument parsing, dispatch, output)
tests/         pytest suite
```

---

## PNG output notes

- PNG output is built as an SVG (`imgsvg.ascii_grid_to_svg` /
  `imgsvg.ansi_grid_to_svg`) and rasterized with `cairosvg.svg2png`, writing
  directly to the requested output path on any filesystem.
- `--no-gpu` is accepted for backward compatibility with old scripts but is a
  no-op — cairosvg has no GPU-accelerated path.
- `ansi --png` always renders truecolor `<rect>` half-blocks regardless of
  `--mode`; the `.ans` text file carries the mode-quantized color.

---

## Running the tests

```bash
venv/bin/pytest
```

---

## How it works (short version)

1. `imgcommon.resolve_enhance_params` fills in any unset
   contrast/brightness/saturate/min-lum from `compute_auto_params` (source
   image stats), unless `--no-auto` is given.
2. `imgcommon.load_and_enhance` applies brightness → contrast → saturation →
   sharpness.
3. The image is mapped to a per-cell grid: `imgcommon.build_ascii_grid`
   (cell aspect `0.75`, each cell -> `(r, g, b, glyph)`) for `ascii`, or
   `imgcommon.build_halfblock_grid` (cell aspect `1.0`, each cell ->
   `(top_rgb, bottom_rgb)`, sampling 2 source rows per cell) for `ansi`.
4. `imgcommon.lift_luminance` raises pixels below `--min-lum` to that floor.
5. Output:
   - `ascii --html`: `img2ascii.image_to_ascii_html` emits colored `<span>`
     runs in a `<pre>`.
   - `ascii` (PNG) / `ansi --png`: `imgsvg.ascii_grid_to_svg` /
     `imgsvg.ansi_grid_to_svg` build an SVG, then `imgsvg.render_svg_to_png`
     rasterizes it with cairosvg.
   - `ansi` (`.ans`): `img2ansi.image_to_ansi` emits half-block glyphs with
     SGR escape codes, quantized per `--mode`.
