# Auto-Detected Enhancement Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `-c/--contrast`, `-B/--brightness`, `--saturate`, or `--min-lum` are not passed on the CLI, derive their values from the source image's own luminance/saturation statistics instead of using fixed constants, with `--no-auto` to restore the old fixed defaults.

**Architecture:** New pure function `imgcommon.compute_auto_params(img)` analyzes a source `Image` (grayscale mean/stddev/percentile + HSV saturation mean) and returns a dict of derived `brightness`/`contrast`/`saturate`/`min_lum` values, clamped to sane bounds. `image2.py` changes the four CLI flag defaults to `None`, adds `--no-auto`, and a new `resolve_enhance_params()` helper fills in any `None` values from either `compute_auto_params` or the old hardcoded constants before dispatching to `_render_ascii`/`_render_ansi`. No changes to `img2ascii.py`, `img2ansi.py`, or `load_and_enhance`.

**Tech Stack:** Python 3, Pillow (`PIL.Image`, `PIL.ImageStat`), pytest.

Spec: `docs/superpowers/specs/2026-06-10-auto-enhance-design.md`

---

### Task 1: `compute_auto_params` in `imgcommon.py`

**Files:**
- Modify: `imgcommon.py`
- Test: `tests/test_imgcommon.py`

- [ ] **Step 1: Write failing tests for `_percentile_from_histogram`**

Add to `tests/test_imgcommon.py`:

```python
def test_percentile_from_histogram_basic():
    hist = [0] * 256
    hist[20] = 10
    hist[80] = 90
    # total=100, 5th percentile threshold=5, cumulative hits 10 at index 20
    assert imgcommon._percentile_from_histogram(hist, 5) == 20


def test_percentile_from_histogram_empty():
    hist = [0] * 256
    assert imgcommon._percentile_from_histogram(hist, 5) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_imgcommon.py -k percentile -v`
Expected: FAIL with `AttributeError: module 'imgcommon' has no attribute '_percentile_from_histogram'`

- [ ] **Step 3: Write failing tests for `compute_auto_params`**

Add to `tests/test_imgcommon.py`:

```python
def test_compute_auto_params_solid_mid_gray():
    img = _solid(8, 8, (127, 127, 127))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == pytest.approx(1.0039, abs=1e-3)
    assert out["contrast"] == 2.5  # std==0 -> ratio blows up -> clamps high
    assert out["saturate"] == 2.5  # mean_sat==0 -> ratio blows up -> clamps high
    assert out["min_lum"] == 0.0


def test_compute_auto_params_solid_near_black():
    img = _solid(8, 8, (10, 10, 10))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == 2.5  # mean_lum=10 -> ratio clamps high
    assert out["min_lum"] == pytest.approx(0.0808, abs=1e-3)


def test_compute_auto_params_solid_white():
    img = _solid(8, 8, (255, 255, 255))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == 0.5  # mean_lum=255 -> ratio clamps low
    assert out["min_lum"] == 0.0


def test_compute_auto_params_low_variance_gradient_boosts_contrast():
    # 51px-wide gradient from gray 100 to 150: low std -> contrast pushed up
    img = Image.new("RGB", (51, 4))
    for x in range(51):
        v = 100 + x
        for y in range(4):
            img.putpixel((x, y), (v, v, v))
    out = imgcommon.compute_auto_params(img)
    assert out["contrast"] > 1.0


def test_compute_auto_params_clamped_to_bounds():
    for color in [(0, 0, 0), (255, 255, 255), (1, 1, 1)]:
        out = imgcommon.compute_auto_params(_solid(4, 4, color))
        for key in ("brightness", "contrast", "saturate"):
            assert 0.5 <= out[key] <= 2.5
        assert 0.0 <= out["min_lum"] <= 0.3
```

`_solid` and `Image`/`pytest` are already imported/defined at the top of
`tests/test_imgcommon.py`.

- [ ] **Step 4: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_imgcommon.py -k compute_auto_params -v`
Expected: FAIL with `AttributeError: module 'imgcommon' has no attribute 'compute_auto_params'`

- [ ] **Step 5: Implement `_percentile_from_histogram` and `compute_auto_params`**

In `imgcommon.py`, add `from PIL import ImageStat` to the existing
`from PIL import Image, ImageEnhance` import line (becomes
`from PIL import Image, ImageEnhance, ImageStat`), then add at the end of
the file:

```python
# Calibration constants for compute_auto_params. Tunable — these target a
# "typical photo" look (mid-gray mean, moderate spread, moderate
# saturation, lifted shadows).
_TARGET_MEAN_LUM = 0.50
_TARGET_STD_LUM = 0.22
_TARGET_MEAN_SAT = 0.45
_MIN_LUM_FLOOR = 0.12
_MIN_LUM_PCT = 5
_AUTO_CLAMP = (0.5, 2.5)
_MAX_AUTO_MIN_LUM = 0.30
_AUTO_EPS = 1e-6


def _percentile_from_histogram(hist: list[int], pct: float) -> int:
    """Return the 0-255 value at the given percentile of a 256-bin histogram."""
    total = sum(hist)
    if total == 0:
        return 0
    threshold = total * pct / 100
    cumulative = 0
    for value, count in enumerate(hist):
        cumulative += count
        if cumulative >= threshold:
            return value
    return 255


def compute_auto_params(img: Image.Image) -> dict[str, float]:
    """Derive contrast/brightness/saturate/min_lum from source image stats.

    Targets a fixed reference look (mid-gray mean luminance, moderate
    contrast spread, moderate saturation, lifted shadows) so dark, flat, or
    desaturated source images render closer to "as shot".

    Args:
        img: Source image, any mode, pre-resize and pre-enhancement.

    Returns:
        Dict with keys "brightness", "contrast", "saturate", "min_lum".
    """
    rgb = img.convert("RGB")
    gray = rgb.convert("L")
    stat = ImageStat.Stat(gray)
    mean_lum = stat.mean[0]
    std_lum = stat.stddev[0]
    low_lum = _percentile_from_histogram(gray.histogram(), _MIN_LUM_PCT)

    mean_sat = ImageStat.Stat(rgb.convert("HSV")).mean[1]

    lo, hi = _AUTO_CLAMP

    def _clamp_ratio(target: float, current: float) -> float:
        ratio = (target * 255) / max(current, _AUTO_EPS)
        return min(max(ratio, lo), hi)

    min_lum = max(0.0, _MIN_LUM_FLOOR - low_lum / 255)
    min_lum = min(min_lum, _MAX_AUTO_MIN_LUM)

    return {
        "brightness": _clamp_ratio(_TARGET_MEAN_LUM, mean_lum),
        "contrast": _clamp_ratio(_TARGET_STD_LUM, std_lum),
        "saturate": _clamp_ratio(_TARGET_MEAN_SAT, mean_sat),
        "min_lum": min_lum,
    }
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_imgcommon.py -v`
Expected: all PASS

- [ ] **Step 7: Lint**

Run: `venv/bin/flake8 imgcommon.py tests/test_imgcommon.py`
Expected: no output

- [ ] **Step 8: Commit**

```bash
git add imgcommon.py tests/test_imgcommon.py
git commit -m "feat: add compute_auto_params for image-derived enhancement defaults"
```

---

### Task 2: Wire auto-detection into the CLI

**Files:**
- Modify: `image2.py`
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write failing tests for `resolve_enhance_params`**

Add to `tests/test_image2.py`:

```python
import imgcommon


def test_resolve_enhance_params_all_explicit_skips_image(tmp_path):
    # nonexistent path proves the image is never opened when nothing is None
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(missing, 2.0, 1.1, 0.9, 0.05, False)
    assert result == (2.0, 1.1, 0.9, 0.05)


def test_resolve_enhance_params_auto_fills_unset(tmp_path):
    src = _tiny_image(tmp_path)
    with Image.open(src) as img:
        expected = imgcommon.compute_auto_params(img.convert("RGB"))
    result = image2.resolve_enhance_params(src, None, None, None, None, False)
    assert result == (
        expected["contrast"],
        expected["brightness"],
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_no_auto_uses_old_defaults(tmp_path):
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(missing, None, None, None, None, True)
    assert result == (1.5, 1.0, 1.0, 0.0)


def test_resolve_enhance_params_partial_override_with_auto(tmp_path):
    src = _tiny_image(tmp_path)
    with Image.open(src) as img:
        expected = imgcommon.compute_auto_params(img.convert("RGB"))
    result = image2.resolve_enhance_params(src, None, 1.2, None, None, False)
    assert result == (
        expected["contrast"],
        1.2,
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_partial_override_no_auto(tmp_path):
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(missing, 2.0, None, None, None, True)
    assert result == (2.0, 1.0, 1.0, 0.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_image2.py -k resolve_enhance_params -v`
Expected: FAIL with `AttributeError: module 'image2' has no attribute 'resolve_enhance_params'`

- [ ] **Step 3: Change CLI flag defaults and add `--no-auto`**

In `image2.py`, in `_shared_parser()`, change:

```python
    p.add_argument("-c", "--contrast", type=float, default=1.5)
    p.add_argument("-s", "--sharpness", type=float, default=2.5)
    p.add_argument("-B", "--brightness", type=float, default=1.0)
    p.add_argument("--saturate", type=float, default=1.0)
    p.add_argument("--min-lum", type=float, default=0.0)
    p.add_argument("--no-gpu", action="store_true", default=False)
```

to:

```python
    p.add_argument("-c", "--contrast", type=float, default=None)
    p.add_argument("-s", "--sharpness", type=float, default=2.5)
    p.add_argument("-B", "--brightness", type=float, default=None)
    p.add_argument("--saturate", type=float, default=None)
    p.add_argument("--min-lum", type=float, default=None)
    p.add_argument("--no-auto", action="store_true", default=False)
    p.add_argument("--no-gpu", action="store_true", default=False)
```

- [ ] **Step 4: Add `resolve_enhance_params`**

In `image2.py`, add `import imgcommon` to the existing imports (alongside
`from imgcommon import (...)` — keep both since `compute_auto_params` is
called via the module to keep the import line short):

```python
import imgcommon
import img2ansi
import img2ascii
from imgcommon import (
    load_and_enhance,
    resize_for,
    lift_luminance,
    write_png_from_html,
)
```

Then add this function near `resolve_width`:

```python
# Old fixed defaults, used when --no-auto is passed.
_OLD_ENHANCE_DEFAULTS = {
    "contrast": 1.5,
    "brightness": 1.0,
    "saturate": 1.0,
    "min_lum": 0.0,
}


def resolve_enhance_params(
    input_path: str,
    contrast: float | None,
    brightness: float | None,
    saturate: float | None,
    min_lum: float | None,
    no_auto: bool,
) -> tuple[float, float, float, float]:
    """Fill in unset enhancement params from auto-detection or old defaults.

    Any of contrast/brightness/saturate/min_lum left as None is filled from
    imgcommon.compute_auto_params(source image), unless no_auto is True, in
    which case unset params fall back to the historical fixed defaults.

    Returns:
        (contrast, brightness, saturate, min_lum) fully resolved.
    """
    requested = {
        "contrast": contrast,
        "brightness": brightness,
        "saturate": saturate,
        "min_lum": min_lum,
    }
    if all(v is not None for v in requested.values()):
        return contrast, brightness, saturate, min_lum

    if no_auto:
        auto = _OLD_ENHANCE_DEFAULTS
    else:
        with Image.open(input_path) as img:
            auto = imgcommon.compute_auto_params(img.convert("RGB"))

    resolved = {
        key: (value if value is not None else auto[key])
        for key, value in requested.items()
    }
    return (
        resolved["contrast"],
        resolved["brightness"],
        resolved["saturate"],
        resolved["min_lum"],
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_image2.py -v`
Expected: all PASS

- [ ] **Step 6: Call `resolve_enhance_params` from `main()`**

In `image2.py`, in `main()`, change:

```python
    width = resolve_width(args.style, args.width)
    if args.style == "ansi":
        _render_ansi(args, width)
    else:
        _render_ascii(args, width)
```

to:

```python
    width = resolve_width(args.style, args.width)
    args.contrast, args.brightness, args.saturate, args.min_lum = (
        resolve_enhance_params(
            args.input,
            args.contrast,
            args.brightness,
            args.saturate,
            args.min_lum,
            args.no_auto,
        )
    )
    if args.style == "ansi":
        _render_ansi(args, width)
    else:
        _render_ascii(args, width)
```

- [ ] **Step 7: Update module docstring**

In `image2.py`, update the docstring's "Shared options" section:

```python
Shared options:
    -o, --output      Output path
    -w, --width       Character columns (default: ascii 350, ansi 80)
    -c, --contrast    Contrast multiplier (default: auto-detected)
    -s, --sharpness   Sharpness multiplier (default: 2.5)
    -B, --brightness  Brightness multiplier (default: auto-detected)
    --saturate        Saturation multiplier (default: auto-detected)
    --min-lum         Minimum HLS luminance 0.0-1.0 (default: auto-detected)
    --no-auto         Disable auto-detection; use fixed defaults
                      (contrast 1.5, brightness 1.0, saturate 1.0,
                      min-lum 0.0) for any of the above not given
    --no-gpu          Disable GPU in html2image (PNG only)
    -h, --help        Show help
```

- [ ] **Step 8: Run full test suite**

Run: `venv/bin/pytest -v`
Expected: all PASS

- [ ] **Step 9: Lint**

Run: `venv/bin/flake8 image2.py tests/test_image2.py`
Expected: no output

- [ ] **Step 10: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: auto-detect contrast/brightness/saturate/min-lum from source image"
```

---

## Self-Review Notes

- Spec coverage: `compute_auto_params` (Task 1) covers all four derived
  params + clamping + percentile helper. CLI defaults, `--no-auto`,
  `resolve_enhance_params`, `main()` wiring, and docstring updates are all
  in Task 2. No changes to `img2ascii.py`/`img2ansi.py`/`load_and_enhance`
  per spec (resolved values flow in unchanged).
- Both tasks add tests before implementation and run the full suite + flake8
  before committing.
