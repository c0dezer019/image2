# pico_ansii

Convert any image into terminal/text art. Two renderers, one shared image-prep
core:

| Script | Style | Output | Best viewed in |
|--------|-------|--------|----------------|
| `img2ascii.py` | Colored **ASCII** — luminance picks a glyph (`$@B%8&…`), each character keeps its own RGB color | HTML or PNG | Browser / image viewer |
| `img2ansi.py`  | Traditional **ANSI** — half-block `▀` (top pixel = foreground, bottom = background); color does the work | `.ans`/`.txt` + optional PNG | Terminal (`cat`) / image viewer |

They are **not redundant**: different medium (HTML spans vs raw ANSI escape
codes), different look (glyph detail vs color blocks), different default scale
(350 cols vs 80 cols).

---

## Requirements

- Python 3.14+
- [Pillow](https://pypi.org/project/Pillow/) — image loading/processing
- [html2image](https://pypi.org/project/html2image/) — **only** needed for PNG
  output (requires a Chrome/Chromium install)
- pytest — only for running the test suite

Install in a venv:

```bash
python -m venv venv
source venv/bin/activate # must be ran before use.
pip install -r requirements.txt
```

---

## Project layout

```
imgcommon.py     Shared helpers: lift_luminance, load_and_enhance, resize_for
img2ascii.py     Colored ASCII renderer (HTML/PNG)
img2ansi.py      Traditional ANSI renderer (.ans/PNG)
tests/           pytest suite (19 tests)
docs/superpowers/ Design spec + implementation plan
```

---

## img2ansi.py — traditional ANSI art

Each character cell is an upper-half block `▀`. The **top** source pixel becomes
the foreground color and the **bottom** pixel the background color, doubling
vertical resolution. The result is real ANSI escape codes you can `cat` in any
truecolor terminal.

### Usage

```bash
python3 img2ansi.py <input_image> [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | Path to the source image (positional) |
| `-o, --output` | `<input>_ansi.ans` | Output path. Extension respected if given |
| `-w, --width` | `80` | Character columns (80 = BBS-authentic) |
| `--mode` | `truecolor` | `truecolor` \| `256` \| `bbs16` |
| `--png` | off | Also rasterize a PNG (needs html2image + Chrome) |
| `-c, --contrast` | `1.5` | Contrast multiplier |
| `-s, --sharpness` | `2.5` | Sharpness multiplier |
| `-B, --brightness` | `1.0` | Brightness multiplier |
| `--saturate` | `1.0` | Saturation multiplier |
| `--min-lum` | `0.0` | Minimum HLS luminance floor (0.0–1.0); lifts dark pixels |
| `--no-gpu` | off | Disable GPU in html2image (PNG only; fixes some headless-Chrome issues) |
| `-h, --help` | — | Show help |

### Color modes

- **`truecolor`** — 24-bit color (`\033[38;2;r;g;b`). Most accurate. Needs a
  truecolor terminal (most modern ones).
- **`256`** — quantized to the xterm-256 palette. Works in older 256-color
  terminals.
- **`bbs16`** — quantized to the classic 16-color CP437/VGA palette. The most
  "traditional" / retro BBS look. Works almost everywhere.

### Examples

```bash
# Default: 80-col truecolor .ans next to the source image
python3 img2ansi.py enterprise.jpg
cat enterprise_ansi.ans

# Retro 16-color, wider
python3 img2ansi.py planet.jpg -w 100 --mode bbs16 -o planet.ans
cat planet.ans

# 256-color, brighten the dark areas
python3 img2ansi.py planet.jpg --mode 256 --min-lum 0.15

# Also produce a PNG render of the ANSI art
python3 img2ansi.py enterprise.jpg -w 80 --png
#   -> enterprise_ansi.ans  AND  enterprise_ansi.png
```

> **Tip:** wider `--width` = more detail but needs a wider terminal to view the
> `.ans` without wrapping. For sharing as an image, add `--png`.

---

## img2ascii.py — colored ASCII art

Maps each pixel's brightness to an ASCII character (dense → bright) and colors
that character with the pixel's RGB. Renders to a standalone HTML file or a PNG.

### Usage

```bash
python3 img2ascii.py <input_image> [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | Path to the source image (positional) |
| `-o, --output` | `<input>_ascii.png` / `.html` | Output path |
| `--html` | off (PNG) | Save an HTML file instead of a PNG |
| `--img-width` | auto | Force output PNG pixel width (auto-scales height + text) |
| `--img-height` | auto | Force output PNG pixel height (auto-scales width + text) |
| `-w, --width` | `350` | Character columns. Narrower sources are upsampled first |
| `-c, --contrast` | `1.5` | Contrast multiplier |
| `-s, --sharpness` | `2.5` | Sharpness multiplier |
| `-B, --brightness` | `1.0` | Brightness multiplier |
| `--min-lum` | `0.0` | Minimum HLS luminance floor (0.0–1.0) |
| `--saturate` | `1.0` | Saturation multiplier |
| `-b, --bg` | `#000000` | HTML/PNG background color |
| `--font-size` | `4.0` (HTML), `6.5` (PNG) | Font size in px |
| `--select` | off | Auto-highlight the text (replicate OS selection effect) |
| `--no-gpu` | off | Disable GPU in html2image (PNG only) |
| `-h, --help` | — | Show help |

### Examples

```bash
# Default: high-detail PNG next to the source
python3 img2ascii.py enterprise.jpg
#   -> enterprise_ascii.png

# Standalone HTML you can open in a browser / zoom infinitely
python3 img2ascii.py planet.jpg --html
#   -> planet_ascii.html

# Force a 1920px-wide PNG on a dark-grey background
python3 img2ascii.py planet.jpg --img-width 1920 -b "#101010"

# Lower character resolution (faster, blockier)
python3 img2ascii.py enterprise.jpg -w 150
```

---

## PNG output notes

- PNG requires `html2image`, which drives a headless Chrome/Chromium. If Chrome
  isn't found or crashes, try `--no-gpu`.
- Without `html2image` installed, `img2ansi.py --png` still writes the `.ans`
  and prints a hint; `img2ascii.py` (PNG mode) prints a hint and skips the PNG.
- Output is moved with `shutil.move`, so writing across filesystems
  (e.g. `-o /tmp/out.png` from a home-partition project) works.

---

## Running the tests

```bash
./venv/bin/python -m pytest tests/ -v
```

19 tests cover the shared helpers, both quantizers, the half-block renderer, the
HTML preview, and an `img2ascii` output-stability regression.

---

## How it works (short version)

1. `imgcommon.load_and_enhance` opens the image and applies the
   brightness → contrast → saturation → sharpness chain.
2. `imgcommon.resize_for` scales it to the requested character grid
   (`cell_aspect` differs per renderer: `0.48` for ASCII line spacing, `1.0` for
   ANSI half-blocks which then sample 2 rows per cell).
3. `imgcommon.lift_luminance` optionally raises dark pixels to a luminance floor
   (`--min-lum`).
4. Each renderer turns the pixel grid into its own output:
   - ASCII → per-character colored `<span>`s in HTML.
   - ANSI → half-block glyphs with ANSI SGR escape codes (or HTML spans for the
     PNG preview).
```
