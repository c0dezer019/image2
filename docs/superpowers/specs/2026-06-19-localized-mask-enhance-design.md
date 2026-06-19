# Localized (masked) brightness/contrast/saturate edits

## Problem

`compute_auto_params` (see `2026-06-10-auto-enhance-design.md`, since
amended) derives a single global brightness/contrast/saturate/min-lum
set from whole-image statistics. Any single global correction is wrong
for images that mix regions with very different tonal needs — e.g. a
mostly-white line-art subject against a dark background, or a portrait
with a blown-out window in frame. There's no way today to say "brighten
just this region" without cropping/recompositing outside the tool.

## Goal

Let the user supply a grayscale mask image alongside the source image.
Mask intensity at each pixel scales how strongly that pixel receives
the (auto-detected or explicit) brightness/contrast/saturate/min-lum
adjustment: white = full strength, black = untouched, gray = partial.
This composes with everything that already exists — auto-detection
still derives the *parameters*; the mask only changes *where* they're
applied and by how much.

Out of scope for this spec: any interactive/visual mask-drawing UI.
Mask creation is the user's problem (e.g. paint one in any image editor,
or generate one with a separate tool) — `image2` only consumes a mask
file. The Image2-Web frontend could add a paint UI on top of this later
without requiring any CLI changes.

## Design

### CLI surface (`image2.py`)

New flag on `_shared_parser()` (applies to both `ascii` and `ansi`,
since it operates on the source image before grid-building):

```
--mask <path>     Grayscale mask image; scales enhancement strength
                  per-pixel (white = full strength, black = none).
                  Resized to match the source image. Default: none
                  (uniform full-strength enhancement, today's
                  behavior).
```

No new flag is needed to control *what* gets masked — brightness,
contrast, saturate, and min-lum are all scaled together by the same
mask, since they're already resolved as a single set of scalars per
run (`resolve_enhance_params`). A future spec could add per-parameter
mask toggles if that turns out to be wanted; not designed here.

### `imgcommon.py`: `apply_masked_enhance`

```python
def apply_masked_enhance(
    img: Image.Image,
    mask: Image.Image,
    contrast: float,
    sharpness: float,
    brightness: float,
    saturate: float,
) -> Image.Image:
    """Blend full-strength and identity enhancement per-pixel via mask.

    Args:
        img: Source image, RGB.
        mask: Grayscale (or any mode, converted to "L"), resized to
            img.size if it doesn't already match. 255 = full strength,
            0 = untouched.
        contrast, sharpness, brightness, saturate: same as
            load_and_enhance.

    Returns:
        A new image: Image.composite(enhanced, img, mask), where
        ``enhanced = load_and_enhance(img, ...)``.
    """
    if mask.size != img.size:
        mask = mask.resize(img.size, resample=Image.Resampling.LANCZOS)
    mask = mask.convert("L")
    enhanced = load_and_enhance(img, contrast, sharpness, brightness, saturate)
    return Image.composite(enhanced, img, mask)
```

`Image.composite(a, b, mask)` already does exactly the per-pixel linear
blend we want (`mask/255 * a + (1 - mask/255) * b`), so no manual pixel
loop is needed — this stays O(1) Pillow calls, not O(pixels) Python.

`min_lum` (HLS luminance floor) doesn't fit `ImageEnhance`/`composite`
as cleanly since `lift_luminance` is a floor, not a blend — applying it
through the same mask requires building two lifted variants and
compositing those too:

```python
floored = img_pixelwise_lift(img, min_lum)  # existing per-pixel loop
result = Image.composite(floored, result, mask)
```

This reuses the existing per-pixel `lift_luminance` loop already in
`_render_ansi`/build paths — just gated by the mask via a second
composite, applied after the `ImageEnhance` composite above.

### Wiring into `image2.py::main()`

After the existing block:

```python
args.contrast, args.brightness, args.saturate, args.min_lum = (
    resolve_enhance_params(...)
)
```

add:

```python
if args.mask:
    with Image.open(args.mask) as opened_mask:
        mask = opened_mask.convert("L")
    img = apply_masked_enhance(
        img, mask, args.contrast, args.sharpness,
        args.brightness, args.saturate,
    )
    if args.min_lum > 0:
        img = apply_masked_min_lum(img, mask, args.min_lum)  # new helper, mirrors above
else:
    img = load_and_enhance(
        img, args.contrast, args.sharpness, args.brightness, args.saturate
    )
    if args.min_lum > 0:
        img = ... # existing per-pixel lift, unchanged
```

This is the one structural wrinkle: today, `load_and_enhance` /
`lift_luminance` application happens *inside* `_render_ansi` and inside
`build_ascii_grid` (called from `_render_ascii`), not in `main()`. To
support masking without duplicating the enhance step in three places,
this spec proposes moving the enhance-and-lift step up into `main()`
(applied once, uniformly, to `img` before dispatch) for *both* the
masked and unmasked paths, and having `_render_ansi`/`build_ascii_grid`
receive an already-enhanced image and stop calling
`load_and_enhance`/`lift_luminance` themselves.

This is a real refactor (touches `_render_ansi`, `build_ascii_grid`,
and their tests, which currently pass raw `contrast`/`brightness`/etc.
straight through) and needs its own careful pass to confirm no
byte-for-byte output changes for the unmasked path — flagged here as
the main implementation risk, not resolved by this design.

### Error handling / edge cases

- `--mask` path doesn't exist / fails to open → same error pattern as
  invalid `--input` (clear message, exit 1), checked in `main()`
  alongside the existing input-path validation.
- Mask size differs from source → resize (documented above), no error.
- Mask provided but fully black (no-op) or fully white (identical to
  no mask) → both fall out naturally from `Image.composite`, no special
  case needed.
- `--mask` combined with `--no-auto` → mask still applies; it scales
  *whichever* params were resolved (auto or fixed-default), no
  interaction needed.
- `--mask` combined with `--invert`/`--blur` → mask is applied after
  those (both operate on `img` before `resolve_enhance_params` already,
  per current `main()` ordering) — no change needed, just confirm order
  in implementation.

## Testing

`tests/test_imgcommon.py`:
- `apply_masked_enhance` with an all-white mask == `load_and_enhance`
  output exactly.
- `apply_masked_enhance` with an all-black mask == input image
  unchanged.
- `apply_masked_enhance` with a half-white/half-black mask: assert the
  white half matches enhanced, black half matches original, at a few
  sample pixels.
- Mask resized when size doesn't match source (assert no exception,
  output size matches source).

`tests/test_image2.py`:
- `--mask <path>` end-to-end on a synthetic split image (e.g. left half
  needs brightening, right half doesn't) → assert only the masked half
  changed relative to a no-mask render.
- `--mask` + `--no-auto` → fixed defaults still scoped by mask.
- Missing mask file → clear error, exit 1.

## Open questions for a future session

- Should mask strength be invertible (`--mask-invert`) for convenience,
  or is "paint a black mask and don't bother" good enough? Leaning
  toward not adding this until someone actually asks.
- Does this want a per-parameter mask (separate masks for brightness
  vs. contrast vs. saturate)? Not designed here — start with one mask
  scaling everything together, since that's the common case ("fix this
  region's overall exposure").
- The `main()` refactor (moving enhance application up) is the load-
  bearing risk in this design and should get its own focused
  implementation pass with regression-test coverage on the unmasked
  path before the masked path is added on top.
