# img2

Convert any image into terminal/text art with one command. Two render styles,
one shared image-prep core:

| Style | Subcommand | Output | Best viewed in |
|-------|------------|--------|----------------|
| Colored **ASCII** — luminance picks a glyph (`$@B%8&…`), each character keeps its own RGB color | `ascii` | HTML or PNG | Browser / image viewer |
| Traditional **ANSI** — half-block `▀` (top pixel = foreground, bottom = background) | `ansi` | `.ans` + optional PNG | Terminal (`cat`) / image viewer |

---

## Examples

<img width="871" height="869" alt="jackinarmorv4_ascii" src="https://github.com/user-attachments/assets/cdef85fc-0522-4874-a52c-d26ea0bc8c20" />

<img width="720" height="600" alt="jackinarmorv4_ansi" src="https://github.com/user-attachments/assets/ec40891d-618f-470a-a5d1-267316e7c59d" />



## Requirements

- Python 3.14+
- [Pillow](https://pypi.org/project/Pillow/) — image loading/processing
- [html2image](https://pypi.org/project/html2image/) — required for PNG output (needs Chrome/Chromium)
- pytest — only for the test suite

### Install system-wide with pipx (recommended)

```bash
./install.sh            # or ./install.sh --editable for dev (live source changes)
```

Puts `img2` on PATH (`~/.local/bin`) in its own isolated venv — no manual venv
activation ever needed. Installs pipx via brew (or `pip install --user`) if missing.

### Install in a venv

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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
| `-c, --contrast` | `1.5` | Contrast multiplier |
| `-s, --sharpness` | `2.5` | Sharpness multiplier |
| `-B, --brightness` | `1.0` | Brightness multiplier |
| `--saturate` | `1.0` | Saturation multiplier |
| `--min-lum` | `0.0` | Minimum HLS luminance floor (0.0–1.0) |
| `--no-gpu` | off | Disable GPU in html2image (PNG only) |
| `-h, --help` | — | Show help |

### ascii-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--html` | off (PNG) | Save HTML instead of a PNG |
| `--img-width` | auto | Force output PNG pixel width |
| `--img-height` | auto | Force output PNG pixel height |
| `-b, --bg` | `#000000` | Background color |
| `--font-size` | `4.0` (HTML) / `6.5` (PNG) | Font size in px |
| `--select` | off | Auto-highlight the text |

Default output: `<input>_ascii.png` (or `<input>_ascii.html` with `--html`).

### ansi-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `truecolor` | `truecolor` \| `256` \| `bbs16` |
| `--png` | off | Also rasterize a PNG |

Default output: `<input>_ansi.ans` (plus `<input>_ansi.png` with `--png`).

Color modes: **truecolor** = 24-bit (needs a truecolor terminal); **256** =
xterm-256 palette; **bbs16** = classic 16-color CP437/VGA (most retro, works
almost everywhere).

---

## Examples

```bash
# Colored ASCII -> high-detail PNG next to the source
img2 ascii enterprise.jpg
#   -> enterprise_ascii.png

# Standalone zoomable HTML
img2 ascii planet.jpg --html
#   -> planet_ascii.html

# Force a 1920px-wide PNG on dark-grey
img2 ascii planet.jpg --img-width 1920 -b "#101010"

# Traditional ANSI, 80-col truecolor .ans
img2 ansi enterprise.jpg
cat enterprise_ansi.ans

# Retro 16-color, wider, also a PNG
img2 ansi planet.jpg -w 100 --mode bbs16 --png

# 256-color, lift the dark areas
img2 ansi planet.jpg --mode 256 --min-lum 0.15
```

---

## Project layout

```
imgcommon.py   Shared helpers: lift_luminance, load_and_enhance, resize_for, write_png_from_html
img2ascii.py   Colored-ASCII render backend
img2ansi.py    Traditional-ANSI render backend
image2.py      Unified CLI (argument parsing, dispatch, output)
tests/         pytest suite
```

---

## PNG output notes

- PNG output uses `html2image` (drives headless Chrome/Chromium). If Chrome
  isn't found or crashes, add `--no-gpu`.
- Output is moved with `shutil.move`, so writing across filesystems works.

---

## Running the tests

```bash
./venv/bin/python -m pytest tests/ -v
```

---

## How it works (short version)

1. `imgcommon.load_and_enhance` opens the image and applies brightness →
   contrast → saturation → sharpness (ANSI path; the ASCII renderer applies the
   same chain internally).
2. The image is resized to the character grid (`cell_aspect` differs per style:
   `0.48` line-spacing for ASCII, `1.0` for ANSI half-blocks which sample 2 rows
   per cell).
3. `imgcommon.lift_luminance` optionally raises dark pixels to a floor
   (`--min-lum`).
4. Each backend renders: ASCII → colored `<span>`s; ANSI → half-block glyphs
   with SGR escape codes (and HTML spans for the PNG preview).
