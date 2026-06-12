# Gaussian Blur Preprocessing — Design

## Goal

Add an opt-in gaussian blur preprocessing step to reduce noise in source
images before they're rendered to ASCII or ANSI art.

## CLI

Add `--blur RADIUS` (float, default `0.0`) to `_shared_parser()` in
`image2.py`. Applies to both the `ascii` and `ansi` subcommands.

`RADIUS <= 0` (including the default) is a true no-op — the filter is not
applied at all.

Add a `--blur` line to the shared options section of the module docstring
in `image2.py`.

## Pipeline placement

Applied in `main()`, immediately after the existing `--invert` step and
before `resolve_enhance_params` (auto-detection of contrast/brightness/
saturate/min_lum) and before resize/enhance.

Rationale: blurring should smooth sensor noise on the full-resolution
source image before stats-based auto-params are computed (so auto-detect
sees the "cleaned" image) and before `--sharpness` runs (sharpness would
re-amplify noise if blur ran after it).

Order in `main()`:

1. Open image, convert to RGB
2. `--invert` (existing)
3. `--blur` (new)
4. `resolve_enhance_params` (existing, auto-detect or fixed defaults)
5. Render (ascii/ansi) (existing)

## Implementation

One-liner using Pillow's built-in filter, added directly in `main()` —
no new helper/module needed:

```python
if args.blur > 0:
    img = img.filter(ImageFilter.GaussianBlur(radius=args.blur))
```

Requires adding `ImageFilter` to the existing `from PIL import Image,
ImageOps` import in `image2.py`.

## Testing

Add case(s) to `tests/test_image2.py`:

- `--blur 0` (or omitted) produces output identical to current behavior
  (no-op).
- `--blur 2.0` on a noisy test image measurably changes pixel data (e.g.
  reduces stddev/variance of the resulting grid/output) compared to
  unblurred.

## Out of scope

- Auto-detection of noise level / auto blur radius.
- Per-subcommand-only blur (ascii-only or ansi-only) — always shared.
- Other denoise algorithms (median filter, bilateral, etc.).
