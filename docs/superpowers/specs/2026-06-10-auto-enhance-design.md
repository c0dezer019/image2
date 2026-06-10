# Auto-detected enhancement defaults

## Problem

Users frequently must pass `-B`/`--brightness` (and friends) by hand because
the current fixed defaults (`contrast=1.5`, `sharpness=2.5`, `brightness=1.0`,
`saturate=1.0`, `min-lum=0.0`) don't account for the source image's own
luminance/contrast/saturation. Dark or flat source images render dark/flat
output unless the user manually compensates.

## Goal

When the user does not pass `-c/--contrast`, `-B/--brightness`,
`--saturate`, or `--min-lum`, derive each from the source image's own RGB/HSV
statistics so the rendered output's tonal range tracks the source. Sharpness
is unaffected (stays a fixed default; not part of this feature).

## Design

### `imgcommon.compute_auto_params(img: Image.Image) -> dict[str, float]`

New pure function. Input: the source image, RGB, **before** resize and
before any `ImageEnhance` operations. Output: a dict with keys
`brightness`, `contrast`, `saturate`, `min_lum`.

Analysis:
- `gray = img.convert("L")` — perceptual luminance band (matches the
  `0.299*r + 0.587*g + 0.114*b` formula already used in `img2ascii.py` for
  glyph selection, for consistency).
  - `mean_lum, std_lum = ImageStat.Stat(gray).mean[0], .stddev[0]`
  - `low_lum = percentile(gray.histogram(), 5)` — 5th-percentile luminance
    (0-255), used as a proxy for "how crushed are the shadows".
- `hsv = img.convert("HSV")` — `mean_sat = ImageStat.Stat(hsv).mean[1]`
  (S band, 0-255).

Calibration constants (module-level, named, documented as tunable):

```python
_TARGET_MEAN_LUM = 0.50   # target mean luminance, 0-1
_TARGET_STD_LUM  = 0.22   # target luminance spread (contrast proxy), 0-1
_TARGET_MEAN_SAT = 0.45   # target mean HSV saturation, 0-1
_MIN_LUM_FLOOR   = 0.12   # target shadow floor, 0-1
_MIN_LUM_PCT     = 5      # percentile used to measure current shadow level
_AUTO_CLAMP      = (0.5, 2.5)  # bounds for brightness/contrast/saturate
_MAX_AUTO_MIN_LUM = 0.30  # upper bound for derived min_lum
```

Formulas:

```python
brightness = clamp(_TARGET_MEAN_LUM * 255 / max(mean_lum, eps), *_AUTO_CLAMP)
contrast   = clamp(_TARGET_STD_LUM  * 255 / max(std_lum,  eps), *_AUTO_CLAMP)
saturate   = clamp(_TARGET_MEAN_SAT * 255 / max(mean_sat, eps), *_AUTO_CLAMP)
min_lum    = clamp(max(0.0, _MIN_LUM_FLOOR - low_lum / 255), 0.0, _MAX_AUTO_MIN_LUM)
```

`eps = 1e-6` guards divide-by-zero on degenerate (solid black) images; the
clamp then catches the resulting huge ratio and pins it to `2.5`.

### CLI wiring (`image2.py`)

- `_shared_parser()`: change defaults of `-c/--contrast`, `-B/--brightness`,
  `--saturate`, `--min-lum` from their current fixed values to `None`.
  `-s/--sharpness` is untouched (stays `default=2.5`).
- Add `--no-auto` (`action="store_true"`, default `False`) to
  `_shared_parser()`.
- In `main()`, after the input-path validation and before dispatch:
  - If `args.no_auto` is `False` and any of the four params is `None`, open
    the source image once (`Image.open(args.input).convert("RGB")`) and call
    `compute_auto_params`.
  - Fill each `None` param:
    - `--no-auto` set → use today's old hardcoded defaults
      (`contrast=1.5, brightness=1.0, saturate=1.0, min_lum=0.0`).
    - otherwise → use the corresponding value from `compute_auto_params`.
  - Explicit user-supplied flags pass through unchanged (per-flag override —
    no auto computation needed for params the user specified, but for
    simplicity `compute_auto_params` is called once and only its results for
    `None` params are used).

No changes needed in `img2ascii.py`, `img2ansi.py`, or
`imgcommon.load_and_enhance` — they continue to receive fully-resolved
numeric values exactly as today, sidestepping the dual-enhancement-path
gotcha noted in CLAUDE.md.

### Help text

Update `image2.py` module docstring to document the new auto-detect default
behavior and `--no-auto`.

## Error handling / edge cases

- Solid black/white image: `mean_lum`/`std_lum`/`mean_sat` near 0 → ratios
  blow up → clamped to `2.5`.
- Pure grayscale image: `mean_sat == 0` → `saturate` clamps to `2.5`, but
  `ImageEnhance.Color` on a fully desaturated image is a no-op regardless, so
  this is harmless.
- Already "well-balanced" image (mean_lum ~127, std_lum ~56, mean_sat ~115):
  all three multipliers come out close to `1.0` and `min_lum` close to `0`,
  i.e. auto behaves like the old `contrast=1.0, brightness=1.0, saturate=1.0,
  min-lum=0.0`. Note this differs from the *old* default of
  `contrast=1.5, sharpness=2.5` — `--no-auto` is the way to get the exact old
  behavior back.

## Testing

`tests/test_imgcommon.py`:
- Solid mid-gray image → all four auto values ≈ identity (brightness/
  contrast/saturate ≈ 1.0, min_lum ≈ 0.0).
- Solid near-black image → brightness and min_lum both push toward
  brightening (brightness clamps to 2.5, min_lum > 0).
- Solid near-white image → brightness clamps low (0.5), min_lum == 0.
- Flat low-contrast gradient → contrast > 1.0.
- Pure grayscale (S=0) image → saturate clamps to 2.5 but is harmless
  (document via comment, no separate enhancement-path test needed here).
- Percentile helper: synthetic histogram with known distribution → exact
  expected percentile value.

`tests/test_image2.py`:
- No flags passed → resolved args come from `compute_auto_params` (mock it,
  assert values flow through).
- Explicit `-B 1.2` passed → `1.2` used verbatim, `compute_auto_params`
  result for brightness ignored (others still auto).
- `--no-auto` passed, no other flags → resolved args equal old hardcoded
  defaults (1.5/2.5/1.0/1.0/0.0).
- `--no-auto` + explicit `-c 2.0` → contrast `2.0`, others fall back to old
  hardcoded defaults.
