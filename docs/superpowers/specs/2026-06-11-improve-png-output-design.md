# Replace headless-Chromium PNG generation with SVG + cairosvg

## Problem

`imgcommon.write_png_from_html` rasterizes HTML via headless Chrome
(`html2image`) for both `ascii` PNG output and `ansi --png`. This is a heavy
dependency (chromium binary, GPU flags, `--no-gpu` workarounds), requires
`shutil.move` because html2image can only write to CWD, and the project's
checked-in `venv/` already has a stale interpreter symlink that breaks
`pip install`/test/lint for this and other reasons.

## Goal

Replace the chromium rasterization step with: build an SVG describing the
art, rasterize it with `cairosvg`. `--html` output (raw HTML file, ascii
only) is unchanged — no chromium needed there today and none is needed after
this change either.

## Performance investigation (why this isn't a 1:1 swap)

Baseline (current chromium path, `jackinarmorv4.png`):

| Mode | Grid | Output px | total |
|---|---|---|---|
| ascii (default w=350) | 350x262 | 2730x2725 | 8.23s |
| ansi (default w=80) | 80x40 | 384x320 | 1.06s |

`rich.Console.export_svg()` (one `<text>` per styled run) + `cairosvg`:
22,528 elements / 3.64MB SVG -> 28.3s for ascii. `resvg_py` is worse at every
scale tested (e.g. 118.8s vs cairosvg's 71.0s on the unmerged 80,765-element
SVG) and is dropped from consideration entirely.

A hand-rolled SVG — one `<text>` per row containing `<tspan fill="rgb(...)">`
per color-run (262 `<text>`, 34,561 `<tspan>`, 1.40MB) — gets ascii down to
**21.0s** with cairosvg. Still ~2.5x the chromium baseline, but the best
result found across rasterizers and SVG shapes.

**Decision:** use the hand-rolled tspan-grouped approach. `rich` adds nothing
in this path (we already have RGB tuples; `export_svg`'s value — terminal
chrome, theming, CDN fonts — is all stripped for this use case anyway), so
**`rich` is dropped as a dependency entirely**. New native dependency is
`cairosvg` (libcairo via cffi) replacing html2image (chromium binary) —
strictly lighter.

For `ansi --png`, the half-block glyph `▀` is visually just two stacked solid
colors (top = fg, bottom = bg). Rendering it as two `<rect>`s per run instead
of a glyph avoids font/text rasterization entirely for this path — expected
to be faster than the current chromium baseline (1.06s), not just "acceptable
like rich/SVG would be for text".

## Design

### New module: `imgsvg.py`

Flat module (5th alongside `image2.py`, `img2ascii.py`, `img2ansi.py`,
`imgcommon.py`), single responsibility: build SVG strings from pixel grids
and rasterize them.

```python
def merge_runs(
    colors: list[tuple[int, int, int]], threshold: int = 10
) -> list[tuple[int, int, int, int, int]]:
    """Segment a row of RGB colors into runs of similar color.

    Anchor color = first pixel of each run; a pixel continues the run if
    abs(channel diff) < threshold for all of r,g,b vs the anchor (matches the
    existing img2ascii merge semantics). Returns
    [(r, g, b, start_idx, length), ...] covering the full row.
    """


def ascii_grid_to_svg(
    grid: list[list[tuple[int, int, int, str]]],
    font_size: float,
    bg_color: str,
    px_w: int,
    px_h: int,
    auto_select: bool = False,
) -> str:
    """One <text> per row, one <tspan fill="rgb(r,g,b)"> per merge_runs() run
    (text = the run's glyphs, sliced from the grid). cell_w = font_size*0.6,
    cell_h = font_size*0.8 (matches existing chromium-tuned constants).
    viewBox = "0 0 {cols*cell_w} {rows*cell_h}"; width/height = px_w/px_h
    (cairosvg scales viewBox -> output dims). Background: full-size <rect
    fill="{bg_color}">. font-family: monospace (generic, no CDN reference —
    offline-deterministic).

    If auto_select is True [see CLI wiring], additionally draws the striped
    repeating-band overlay (same half_row/row_height bands as the current
    CSS repeating-linear-gradient) as semi-transparent <rect>s.
    """


def ansi_grid_to_svg(
    grid: list[list[tuple[tuple[int, int, int], tuple[int, int, int]]]],
    cell_w: float,
    cell_h: float,
    px_w: int,
    px_h: int,
    bg_color: str,
) -> str:
    """grid[row][col] = (top_rgb, bot_rgb). merge_runs() applied separately to
    the top-color row and the bottom-color row; each run emits one <rect> at
    (run_start*cell_w, row*cell_h [+cell_h/2 for bottom], run_length*cell_w,
    cell_h/2). No text/glyphs. viewBox/width/height as above.
    """


def render_svg_to_png(svg: str, out_path: str) -> None:
    """cairosvg.svg2png(bytestring=svg.encode(), write_to=out_path).

    Writes directly to out_path on any filesystem -- no shutil.move needed
    (unlike html2image, which could only target CWD).

    If cairosvg is not importable, print "cairosvg is required to save a
    PNG. Run: pip install cairosvg" and return, mirroring the current
    Html2Image-missing handling.
    """
```

### `imgcommon.py` additions (shared grid extraction)

```python
def build_ascii_grid(
    img: Image.Image,
    width: int,
    contrast: float,
    sharpness: float,
    brightness: float,
    min_lum: float,
    saturate: float,
) -> list[list[tuple[int, int, int, str]]]:
    """Enhance (via load_and_enhance) + resize_for(cell_aspect=0.75) + map
    each pixel to (r, g, b, ascii_char) via lift_luminance + the existing
    luminance->glyph formula. This is the per-pixel block currently inline in
    img2ascii.image_to_ascii_html (lines ~40-67), extracted so both --html
    and the new PNG path share it.
    """


def build_halfblock_grid(
    img: Image.Image,
) -> list[list[tuple[tuple[int, int, int], tuple[int, int, int]]]]:
    """resize_for(cell_aspect=1.0) [if not already done by caller] then
    sample (top_pixel, bottom_pixel) per cell -- the getpixel loop currently
    duplicated in img2ansi.image_to_ansi and ansi_image_to_html. .ans
    generation quantizes per-cell from this grid per mode (256/16/truecolor);
    the PNG path feeds it to ansi_grid_to_svg untouched (always truecolor,
    per existing behavior).
    """
```

`build_ascii_grid` calling `load_and_enhance` (rather than img2ascii's inline
`ImageEnhance` calls) is safe: the inline sequence (brightness, contrast,
saturate, sharpness) already matches `load_and_enhance`'s order exactly. This
removes the CLAUDE.md-flagged "two enhancement implementations must be kept
in sync" duplication as a side effect.

### `image2.py` wiring

PNG branches in `_render_ascii` / `_render_ansi` become:

```python
# ascii (else branch, when not args.html)
grid = build_ascii_grid(
    img, width, args.contrast, args.sharpness, args.brightness,
    args.min_lum, args.saturate,
)
svg = ascii_grid_to_svg(grid, font_size, bg, px_w, px_h, args.select)
render_svg_to_png(svg, output_path)

# ansi --png
grid = build_halfblock_grid(img)
svg = ansi_grid_to_svg(grid, char_width_px, font_size, px_w, px_h, "#000000")
render_svg_to_png(svg, png_path)
```

`image_to_ascii_html` (HTML path, unaffected output) calls `build_ascii_grid`
instead of its inline enhance/resize/map block, then proceeds with its
existing HTML run-merge + `<pre>` formatting unchanged.

`_render_ascii`'s px_w/px_h "must exactly match the ascii grid or the
centered `<pre>` gets clipped" recompute (image2.py lines ~261-267) is no
longer needed for the PNG path: `viewBox` is the SVG's natural grid size and
`width`/`height` are the requested output px — cairosvg scales between them,
so `--img-width`/`--img-height` just become output scaling, not grid-fitting.
(`--html` path is untouched and keeps using its own sizing as today.)

### `--no-gpu`

Becomes a no-op (cairosvg has no GPU path). Kept as an accepted-but-ignored
flag, marked deprecated in `--help`, to avoid breaking existing scripts.

### `--select` / auto-highlight

`ascii_grid_to_svg` draws the striped repeating-band overlay (same
`half_row`/`row_height` math as the current CSS `repeating-linear-gradient`)
directly as `<rect>`s when `auto_select` is set. The CSS `::selection`
blue-highlight nuance (a "looks actively selected" effect, meaningful only in
a live browser) is dropped — no SVG equivalent, and it's the minor part of
the visual.

### Dependencies

`pyproject.toml`: `dependencies = ["Pillow", "cairosvg"]` (drop
`html2image`). `Html2Image` import/try-except in `imgcommon.py` removed.

## Error handling / edge cases

- `cairosvg` not installed: `render_svg_to_png` prints install instructions
  and returns (mirrors current `Html2Image is None` handling).
- libcairo native lib missing: `import cairosvg` raises `OSError` from cffi
  with a message naming the missing `.so` — left to surface as-is (chromium
  had an analogous "binary not found" failure mode).
- `merge_runs` on an empty row: returns `[]` (no runs) — `ascii_grid_to_svg`/
  `ansi_grid_to_svg` emit an empty `<text>`/no `<rect>`s for that row.
  argparse widths are always >=1 so empty rows shouldn't occur in practice.
- Font metrics: `cell_w = font_size*0.6` / `cell_h = font_size*0.8` were
  tuned against chromium's `Courier New` fallback. cairosvg's default
  `monospace` (likely DejaVu Sans Mono) may have very slightly different
  glyph advance widths. Flag for visual verification during implementation;
  if rows visibly over/underflow `viewBox`, adjust the constants for the
  ascii-PNG path specifically (the `--html` path's own constants are
  untouched).

## Testing

`tests/test_imgsvg.py` (new):
- `merge_runs`: uniform-color row -> single run covering full row;
  alternating colors -> N runs of length 1; boundary at diff==10 (breaks
  run) vs diff==9 (continues run).
- `ascii_grid_to_svg`: parse output as XML; assert `<text>` count == row
  count, `<tspan>` text content matches expected merged glyph runs for a
  small synthetic grid; `auto_select=True` adds the expected band `<rect>`s.
- `ansi_grid_to_svg`: parse as XML; assert `<rect>` count/positions/fills
  match expected top/bottom runs for a small synthetic grid.
- `render_svg_to_png`: mock `cairosvg.svg2png`, assert
  `write_to=out_path` and `bytestring=svg.encode()`; assert graceful message
  + early return when `cairosvg` import fails.

`tests/test_imgcommon.py` (additions):
- `build_ascii_grid`: solid-color and 2x2 gradient fixture images -> expected
  `(r,g,b,char)` grid values and dimensions.
- `build_halfblock_grid`: fixture image -> expected `(top_rgb, bot_rgb)` per
  cell.

`tests/test_img2ascii.py` (regression):
- `image_to_ascii_html` output is byte-identical before/after the
  `build_ascii_grid` refactor on a fixture image (snapshot comparison).

Remove: `write_png_from_html` tests (Html2Image mocks, `shutil.move` mocks)
in favor of the new `render_svg_to_png` tests above.

## CLAUDE.md updates

- Remove "`write_png_from_html` saves to CWD then `shutil.move`" gotcha
  (gone).
- Remove "img2ascii runs its own enhancement inline, does not call
  load_and_enhance" gotcha (fixed by `build_ascii_grid` refactor).
- Architecture section: flat module list grows to `image2.py`, `img2ansi.py`,
  `img2ascii.py`, `imgcommon.py`, `imgsvg.py`.
- Note `--no-gpu` is accepted-but-ignored/deprecated.
- "ANSI PNG preview always renders truecolor" note stays true; mechanism
  updated from `<span>` text to `<rect>` blocks.
