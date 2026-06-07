# Traditional ANSI Generation — Design

**Date:** 2026-06-06
**Status:** Approved

## Goal

Add traditional ANSI art generation to the pico_ansii toolkit, alongside the
existing colored-ASCII pipeline (`img2ascii.py`). "Traditional ANSI" = block
glyphs colored with ANSI escape codes, viewable in a terminal as `.ans`/`.txt`,
with optional PNG rasterization.

## Architecture

Shared module + two CLIs.

- **`imgcommon.py`** (new) — image-prep helpers shared by both scripts:
  - `lift_luminance(r, g, b, min_l) -> (r, g, b)` — moved verbatim from
    `img2ascii.py`.
  - `load_and_enhance(path, contrast, sharpness, brightness, saturate) -> Image`
    — open + apply the ImageEnhance chain (brightness, contrast, color,
    sharpness). Same order as current `img2ascii.py`.
  - `resize_for(img, width, cell_aspect) -> Image` — resize to
    `width x round(width * (img.h/img.w) * cell_aspect)`, LANCZOS, convert RGB.
    `cell_aspect` lets callers control vertical squash:
    - ASCII path passes `0.48` (current behavior).
    - ANSI half-block path passes `1.0` then samples 2 rows per cell.
- **`img2ascii.py`** — refactored to import the three helpers. No behavior
  change; output of existing test images must be byte-identical where the
  enhance/resize logic is reused.
- **`img2ansi.py`** (new) — ANSI render pipeline + CLI.

## Render: half-block `▀`

Each character cell stacks two source pixels:

- Foreground color = **top** pixel.
- Background color = **bottom** pixel.
- Glyph = `▀` (U+2580 upper half block).

So the image is sampled at `width x (2 * rows)`. Implementation: resize image
to height `2 * rows` (even), then loop:

```
for cy in range(rows):
    y = cy * 2
    for x in range(width):
        top = img.getpixel((x, y))
        bot = img.getpixel((x, y + 1))
        emit cell(fg=top, bg=bot)
```

`rows = height // 2`. Drop a trailing odd row if present.

## Color modes (`--mode`)

- **`truecolor`** (default) — 24-bit SGR:
  `\033[38;2;{r};{g};{b}m\033[48;2;{r2};{g2};{b2}m▀`, reset `\033[0m` at line end.
- **`256`** — quantize each RGB to the xterm-256 color cube
  (`16 + 36*r6 + 6*g6 + b6` with grayscale ramp fallback):
  `\033[38;5;{N}m\033[48;5;{M}m▀`.
- **`bbs16`** — quantize to the classic 16-color CP437 palette
  (nearest by Euclidean RGB distance). FG uses SGR `30–37` (normal) / `90–97`
  (bright), BG uses `40–47` / `100–107`. Most "traditional" / BBS-authentic.

Quantizers live in `img2ansi.py`:
- `rgb_to_256(r, g, b) -> int`
- `rgb_to_16(r, g, b) -> (sgr_fg, sgr_bg)` backed by a fixed 16-entry palette
  table.

## Outputs

- **`.ans` / `.txt`** — raw escape codes for all three modes. Written for every
  run. Default extension `.ans`. View with `cat file.ans`.
- **PNG** (`--png`) — reuse the existing HTML → `html2image` path. Emit HTML
  where each cell is
  `<span style="color:rgb(top);background:rgb(bot)">▀</span>`, monospace `pre`,
  `line-height` tuned so half-blocks tile without gaps. Keeps a single render
  dependency (`html2image`) across both scripts. Color always truecolor in the
  HTML regardless of `--mode` (the `.ans` carries the quantized version; PNG is
  a faithful preview).

## CLI flags

Mirror `img2ascii.py` where sensible.

| Flag | Default | Notes |
|------|---------|-------|
| `input` | — | positional image path |
| `-o, --output` | `<input>_ansi.ans` | extension respected if given |
| `-w, --width` | `80` | BBS-authentic column count |
| `--mode` | `truecolor` | `truecolor` \| `256` \| `bbs16` |
| `--png` | off | also rasterize to PNG via html2image |
| `-c, --contrast` | `1.5` | |
| `-s, --sharpness` | `2.5` | |
| `-B, --brightness` | `1.0` | |
| `--saturate` | `1.0` | |
| `--min-lum` | `0.0` | |
| `--no-gpu` | off | passthrough to html2image (PNG only) |
| `-h, --help` | — | |

## Error handling

- Missing/invalid input → friendly message + `sys.exit(1)` (match existing
  voice).
- `--png` without `html2image` installed → message telling user to
  `pip install html2image`; still writes the `.ans`.
- Pillow missing → import-time message (match `img2ascii.py`).

## Testing

- **`imgcommon`**: `resize_for` returns expected dims for known input + cell
  aspect; `lift_luminance` clamps below `min_l`, passes through above.
- **`img2ansi` render**: build small synthetic `Image` objects in-memory:
  - 1x2 solid → one cell, correct `▀` with matching fg/bg escapes.
  - 2-color vertical split → fg != bg in the cell.
  - Assert escape-sequence substrings per mode and total cell count == width.
- **Quantizers**: `rgb_to_256(0,0,0)==16`, `rgb_to_256(255,255,255)==231`;
  `rgb_to_16` maps pure red → red SGR pair.
- **PNG path**: skip if `html2image` absent; else assert output file exists and
  is non-empty. No pixel assertions.
- **`img2ascii` regression**: existing image still produces unchanged ASCII
  (helper extraction must not alter output).

## Out of scope (YAGNI)

- Shade-block (`░▒▓█`) glyph mode — not selected.
- Animated ANSI / SAUCE records.
- Custom palettes beyond the three modes.
