# Re-port: `--invert` and `--monochrome`/`--font-color` onto SVG architecture

## Context

`docs/superpowers/specs/2026-06-11-font-color-invert-design.md` and
`docs/superpowers/plans/2026-06-11-font-color-invert.md` describe the
original implementation (branch `13-feature-change-font-color`, commits
`f3c2510`..`3644151`), built against the pre-refactor architecture where
both `--html` and PNG ascii output routed through
`img2ascii.image_to_ascii_html` + `write_png_from_html` (html2image).

Meanwhile `origin/main` gained PR #15 ("feat: get rid of headless
browser"): html2image/Chromium replaced with cairosvg-based SVG rendering
(`imgsvg.py`). `image_to_ascii_html` now delegates grid-building to
`imgcommon.build_ascii_grid` and lost the `monochrome`/`font_color` params
our branch added. Default (non-`--html`) ascii output now bypasses
`image_to_ascii_html` entirely, going `build_ascii_grid` →
`imgsvg.ascii_grid_to_svg` → `render_svg_to_png`.

This spec covers re-implementing both features against main's structure.
The original design's feature semantics (flag names, defaults, invert
behavior, "monochrome means single solid glyph color") are unchanged —
only the integration points move.

## Feature 1: `--invert`

No architectural impact — ports essentially unchanged:

- `image2.py` imports: `from PIL import Image, ImageOps`
- `_shared_parser()`: add `p.add_argument("--invert", action="store_true", default=False)`
- `main()`: after `img = opened.convert("RGB")`, before
  `resolve_enhance_params`:
  ```python
  if args.invert:
      img = ImageOps.invert(img)
  ```
- Docstring: add `--invert  Invert source image colors before rendering`
  to the shared options block.

## Feature 2: `--monochrome` / `--font-color`

### Scope change from original spec

Original spec scoped this to `image_to_ascii_html` only, because at the
time *all* ascii output (HTML and PNG) went through that function. On
main, PNG (the default) no longer does — it goes through
`ascii_grid_to_svg`. To preserve the original intent ("ascii output in a
single solid color, regardless of output format"), monochrome must now be
supported in **both**:

- `img2ascii.image_to_ascii_html` (the `--html` path)
- `imgsvg.ascii_grid_to_svg` (the default PNG path)

### CLI (`image2.py`)

- `ascii_p`: re-add
  ```python
  ascii_p.add_argument("--monochrome", action="store_true", default=False)
  ascii_p.add_argument("--font-color", default=None)
  ```
- `_render_ascii`: compute, as before:
  ```python
  monochrome = args.monochrome or args.font_color is not None
  font_color = args.font_color or "#ffffff"
  ```
- Pass `monochrome, font_color` to **both** call sites:
  - `image_to_ascii_html(..., px_w, px_h, monochrome, font_color)` (HTML branch)
  - `ascii_grid_to_svg(grid, font_size, bg, px_w, px_h, args.select, monochrome, font_color)` (PNG branch)
- Docstring: re-add `--monochrome`/`--font-color` lines to the
  `ascii-only:` section (as in commit `3644151`).

### `img2ascii.image_to_ascii_html`

Re-add trailing params `monochrome: bool = False, font_color: str =
"#ffffff"`. `rows` (from `build_ascii_grid`) has the same
`(r, g, b, char)` shape the original monochrome branch consumed, so
Task 1's logic ports with no structural change: when `monochrome` is
True, for each row concatenate all glyphs into one string, HTML-escape
(`&`, `<`, `>`), and wrap in a single `<span style="color:{font_color}">`
instead of per-run `<span style="color:rgb(...)">`.

### `imgsvg.ascii_grid_to_svg`

Add trailing params `monochrome: bool = False, font_color: str =
"#ffffff"`. In the per-row loop, when `monochrome` is True, skip
`merge_runs`/per-run `<tspan fill="rgb(...)">` and instead emit one
`<text>` element with a single `fill` attribute and the row's full
(escaped) glyph string:

```python
if monochrome:
    text = "".join(ch for _, _, _, ch in row)
    text_els.append(
        f'<text x="0" y="{y}" xml:space="preserve" fill="{font_color}">'
        f'{sx.escape(text)}</text>'
    )
else:
    # existing merge_runs/tspan logic
```

`auto_select` overlay and viewBox fitting are unaffected — monochrome
only changes per-row glyph coloring.

## Out of scope (unchanged from original)

- No interaction between `--invert` and `--monochrome`/`--font-color`
  beyond both being independently applicable — invert affects the source
  image; monochrome affects only how ascii glyphs are colored.
- `--monochrome`/`--font-color` remain ascii-only (rejected under `ansi`
  subcommand, enforced by argparse subparsers as before).

## Git mechanics

1. Merge `origin/main` into `13-feature-change-font-color` (not a literal
   rebase — branch is already pushed with open PR #16; merge keeps PR
   #16's diff = `main...branch` and avoids force-push).
2. Resolve `image2.py` conflict by taking main's structure, then
   reapplying Feature 1 + Feature 2 CLI wiring on top.
3. For `img2ascii.py`, take main's version wholesale
   (`git checkout origin/main -- img2ascii.py`) rather than trusting the
   auto-merge, then reapply the monochrome branch deliberately.
4. `imgcommon.py`, `imgsvg.py`, `img2ansi.py`: take main's versions as-is
   (no conflict expected — our branch never touched these post-refactor
   files).

## Testing

- `tests/test_image2.py`: existing `--invert` tests (parser flags,
  `test_ansi_invert_changes_output`) and existing `--monochrome`/
  `--font-color` parser + HTML-output tests port unchanged.
- `tests/test_img2ascii_regression.py`: existing
  `test_image_to_ascii_html_monochrome_uses_font_color` /
  `test_image_to_ascii_html_default_not_monochrome` port unchanged (same
  `(r,g,b,char)` row shape).
- `tests/test_imgsvg.py` (new on main): add
  `test_ascii_grid_to_svg_monochrome_uses_font_color` — build a small grid
  with varying pixel colors, call `ascii_grid_to_svg(..., monochrome=True,
  font_color="#00ff00")`, assert output contains `fill="#00ff00"` and does
  NOT contain `fill="rgb(`. Add a default (non-monochrome) counterpart
  asserting `fill="rgb(` IS present, mirroring the existing
  `img2ascii_regression` pair.
