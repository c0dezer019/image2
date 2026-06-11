# Font color override + color inversion

## Goal

Add two CLI features:
1. `--invert` — invert source image colors before rendering. Applies to
   both `ascii` and `ansi` styles.
2. `--monochrome` / `--font-color` — render ascii output with a single
   solid font color instead of per-pixel RGB. Ascii style only.

## Feature 1: `--invert`

- New flag added to `_shared_parser()` in `image2.py`: `--invert`
  (`store_true`, default `False`).
- In `main()`, immediately after `img = opened.convert("RGB")`:
  ```python
  if args.invert:
      img = ImageOps.invert(img)
  ```
  Requires `from PIL import ImageOps`.
- This happens before `resolve_enhance_params` and before dispatch to
  `_render_ascii` / `_render_ansi`, so:
  - Auto-detected contrast/brightness/saturate/min_lum are computed on the
    already-inverted image (correct — that's what gets rendered).
  - Neither `img2ascii.py` nor `img2ansi.py` need any changes for this
    feature.

## Feature 2: `--monochrome` / `--font-color`

- New flags on the `ascii` subparser only:
  - `--monochrome` (`store_true`, default `False`)
  - `--font-color <str>` (default `None`) — any CSS color string
    (`#rrggbb`, named color, `rgb(...)`), passed through unvalidated.
- Resolution in `_render_ascii`:
  ```python
  monochrome = args.monochrome or args.font_color is not None
  font_color = args.font_color or "#ffffff"
  ```
- `img2ascii.image_to_ascii_html` gains two new parameters:
  `monochrome: bool = False, font_color: str = "#ffffff"`.
- Glyph selection (luminance → `ascii_chars` index) is unchanged.
- Row rendering changes when `monochrome` is `True`:
  - Skip the per-pixel-color run-length grouping (lines computing `run`,
    color-distance grouping, per-run `<span style="color:rgb(...)">`).
  - Instead, build the row's full glyph string, HTML-escape it, and wrap
    it in a single `<span style="color:{font_color}">...</span>`.
- `--monochrome` and `--font-color` are ascii-only; not accepted by the
  `ansi` subparser (block-art mode — fg/bg color *is* the picture, "font
  color" doesn't apply).

## Out of scope

- No interaction between `--invert` and `--monochrome`/`--font-color`
  beyond normal flag composition (invert affects the source image;
  monochrome affects only how ascii glyphs are colored — both can be
  combined freely).
- No new tests beyond updating existing ones for new parameters /
  exercising new flags at a basic level (covered in implementation plan).
