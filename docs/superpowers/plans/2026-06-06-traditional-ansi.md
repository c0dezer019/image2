# Traditional ANSI Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add traditional ANSI art generation (half-block `▀` glyphs + ANSI escape codes) to the pico_ansii toolkit via a new `img2ansi.py` CLI, sharing image-prep code with the existing `img2ascii.py` through a new `imgcommon.py` module.

**Architecture:** Extract image-prep helpers (`lift_luminance`, enhance chain, aspect-aware resize) into `imgcommon.py`. Refactor `img2ascii.py` to import them with zero behavior change. Build `img2ansi.py` that samples 2 vertical pixels per cell (top=fg, bottom=bg), renders `▀` in one of three color modes (`truecolor`, `256`, `bbs16`), writes a `.ans` file, and optionally rasterizes a PNG by reusing the existing HTML → `html2image` path.

**Tech Stack:** Python 3.14, Pillow, html2image, pytest. Code style: black, line-length 79.

---

## File Structure

- Create: `imgcommon.py` — shared image-prep helpers.
- Modify: `img2ascii.py` — import helpers from `imgcommon`, drop local copies.
- Create: `img2ansi.py` — ANSI render pipeline + CLI.
- Create: `tests/test_imgcommon.py`
- Create: `tests/test_img2ansi.py`
- Create: `tests/test_img2ascii_regression.py`
- Modify: `requirements.txt` — add `pytest`.

All commands assume the project venv: prefix python/pytest with `./venv/bin/`.

---

## Task 0: Environment setup

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Init git (commits in later tasks need it)**

Run: `git init && git add -A && git commit -m "chore: snapshot before ANSI feature"`
Expected: repo created, initial commit made.

- [ ] **Step 2: Install pytest into the venv**

Run: `./venv/bin/pip install pytest`
Expected: pytest installs successfully.

- [ ] **Step 3: Add pytest to requirements.txt**

Add this line to `requirements.txt` (keep alphabetical-ish; append is fine):

```
pytest==8.3.4
```

- [ ] **Step 4: Create the tests package dir**

Run: `mkdir -p tests && touch tests/__init__.py`
Expected: `tests/__init__.py` exists.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt tests/__init__.py
git commit -m "chore: add pytest and tests dir"
```

---

## Task 1: `imgcommon.lift_luminance`

Move `lift_luminance` out of `img2ascii.py` into the shared module, test-first.

**Files:**
- Create: `imgcommon.py`
- Test: `tests/test_imgcommon.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_imgcommon.py`:

```python
import imgcommon


def test_lift_luminance_passthrough_when_min_zero():
    assert imgcommon.lift_luminance(10, 20, 30, 0.0) == (10, 20, 30)


def test_lift_luminance_raises_dark_pixel():
    # near-black pixel lifted to a higher luminance floor
    r, g, b = imgcommon.lift_luminance(0, 0, 0, 0.5)
    # all channels equal for a gray result, and clearly brighter than 0
    assert r == g == b
    assert r > 100


def test_lift_luminance_leaves_bright_pixel():
    # already-bright pixel above the floor is unchanged-ish
    r, g, b = imgcommon.lift_luminance(255, 255, 255, 0.5)
    assert (r, g, b) == (255, 255, 255)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'imgcommon'`.

- [ ] **Step 3: Write minimal implementation**

Create `imgcommon.py`:

```python
#!/usr/bin/env python3
# flake8: noqa: E501
"""imgcommon.py — shared image-prep helpers for img2ascii / img2ansi."""

import colorsys

from PIL import Image, ImageEnhance


def lift_luminance(
    r: int, g: int, b: int, min_l: float
) -> tuple[int, int, int]:
    if min_l <= 0:
        return r, g, b
    h, luminance, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    if luminance < min_l:
        luminance = min_l
    nr, ng, nb = colorsys.hls_to_rgb(h, luminance, s)
    return int(nr * 255), int(ng * 255), int(nb * 255)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add imgcommon.py tests/test_imgcommon.py
git commit -m "feat: add imgcommon.lift_luminance"
```

---

## Task 2: `imgcommon.load_and_enhance` and `resize_for`

**Files:**
- Modify: `imgcommon.py`
- Test: `tests/test_imgcommon.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_imgcommon.py`:

```python
from PIL import Image


def _solid(w, h, color=(120, 60, 200)):
    return Image.new("RGB", (w, h), color)


def test_resize_for_ascii_aspect():
    img = _solid(100, 100)
    out = imgcommon.resize_for(img, width=50, cell_aspect=0.48)
    # height = round(50 * (100/100) * 0.48) = 24
    assert out.size == (50, 24)
    assert out.mode == "RGB"


def test_resize_for_block_aspect():
    img = _solid(80, 40)
    out = imgcommon.resize_for(img, width=20, cell_aspect=1.0)
    # height = round(20 * (40/80) * 1.0) = 10
    assert out.size == (20, 10)


def test_load_and_enhance_returns_image(tmp_path):
    p = tmp_path / "src.png"
    _solid(8, 8).save(p)
    out = imgcommon.load_and_enhance(
        str(p), contrast=1.5, sharpness=2.5, brightness=1.0, saturate=1.0
    )
    assert isinstance(out, Image.Image)
    assert out.size == (8, 8)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py -v`
Expected: FAIL — `AttributeError: module 'imgcommon' has no attribute 'resize_for'`.

- [ ] **Step 3: Write minimal implementation**

Append to `imgcommon.py`:

```python
def load_and_enhance(
    path: str,
    contrast: float,
    sharpness: float,
    brightness: float,
    saturate: float,
) -> Image.Image:
    img = Image.open(path)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturate != 1.0:
        img = ImageEnhance.Color(img).enhance(saturate)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img


def resize_for(
    img: Image.Image, width: int, cell_aspect: float
) -> Image.Image:
    aspect = img.height / img.width
    height = round(width * aspect * cell_aspect)
    height = max(1, height)
    return img.resize(
        (width, height), resample=Image.Resampling.LANCZOS
    ).convert("RGB")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add imgcommon.py tests/test_imgcommon.py
git commit -m "feat: add load_and_enhance and resize_for to imgcommon"
```

---

## Task 3: Refactor `img2ascii.py` onto `imgcommon` (no behavior change)

The current `img2ascii.py` uses `int(width * aspect * 0.48)` (truncation) in two
places. `resize_for` uses `round`. To guarantee identical output, this task
keeps the existing height math in `img2ascii.py` and only delegates
`lift_luminance` and the enhance chain — NOT the resize. This avoids any
off-by-one pixel drift in the existing pipeline.

**Files:**
- Modify: `img2ascii.py`
- Test: `tests/test_img2ascii_regression.py`

- [ ] **Step 1: Write the regression test**

Create `tests/test_img2ascii_regression.py`:

```python
import img2ascii
from PIL import Image


def test_image_to_ascii_html_stable_output(tmp_path):
    # deterministic 4-color image, fixed params -> stable HTML
    img = Image.new("RGB", (4, 4))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((2, 0), (0, 0, 255))
    img.putpixel((3, 0), (255, 255, 255))

    html = img2ascii.image_to_ascii_html(
        img,
        width=4,
        contrast=1.5,
        sharpness=2.5,
        brightness=1.0,
        min_lum=0.0,
        saturate=1.0,
        bg_color="#000000",
        font_size=4.0,
        auto_select=False,
        text_scale=1.0,
    )
    assert "<pre>" in html
    assert "rgb(" in html
    assert "font-size: 4.0px" in html


def test_lift_luminance_still_exposed():
    # img2ascii must still expose lift_luminance (re-exported from imgcommon)
    assert img2ascii.lift_luminance(10, 20, 30, 0.0) == (10, 20, 30)
```

- [ ] **Step 2: Run test to verify current behavior passes (baseline)**

Run: `./venv/bin/python -m pytest tests/test_img2ascii_regression.py -v`
Expected: PASS (both pass against the un-refactored file).

- [ ] **Step 3: Refactor img2ascii.py to import from imgcommon**

In `img2ascii.py`, replace the local `colorsys` import and the
`lift_luminance` definition (lines ~33 and ~52-61) with an import.

Replace:

```python
import colorsys

try:
    from PIL import Image, ImageEnhance
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)
```

with:

```python
try:
    from PIL import Image, ImageEnhance
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

from imgcommon import lift_luminance
```

Then delete the entire local `def lift_luminance(...)` block (the function body
that uses `colorsys`). The `ImageEnhance` import stays — `image_to_ascii_html`
still uses it directly. `lift_luminance` is now the imported one.

- [ ] **Step 4: Run regression test to verify output unchanged**

Run: `./venv/bin/python -m pytest tests/test_img2ascii_regression.py -v`
Expected: PASS (both still pass — output identical).

- [ ] **Step 5: Smoke-test the real CLI end to end**

Run: `./venv/bin/python img2ascii.py enterprise.jpg --html -o /tmp/regress`
Expected: prints "HTML locked in at: /tmp/regress.html", file exists, no traceback.

- [ ] **Step 6: Commit**

```bash
git add img2ascii.py tests/test_img2ascii_regression.py
git commit -m "refactor: img2ascii uses imgcommon.lift_luminance"
```

---

## Task 4: ANSI color quantizers (`rgb_to_256`, `rgb_to_16`)

**Files:**
- Create: `img2ansi.py`
- Test: `tests/test_img2ansi.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_img2ansi.py`:

```python
import img2ansi


def test_rgb_to_256_black_and_white():
    assert img2ansi.rgb_to_256(0, 0, 0) == 16
    assert img2ansi.rgb_to_256(255, 255, 255) == 231


def test_rgb_to_256_pure_red_in_cube():
    # pure red maps into the 16..231 color cube
    idx = img2ansi.rgb_to_256(255, 0, 0)
    assert 16 <= idx <= 231


def test_rgb_to_16_red():
    fg, bg = img2ansi.rgb_to_16(255, 0, 0)
    # bright or normal red foreground, matching background offset
    assert fg in (31, 91)
    assert bg in (41, 101)


def test_rgb_to_16_black_white():
    fg_k, _ = img2ansi.rgb_to_16(0, 0, 0)
    fg_w, _ = img2ansi.rgb_to_16(255, 255, 255)
    assert fg_k == 30          # black
    assert fg_w in (37, 97)    # white / bright white
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'img2ansi'`.

- [ ] **Step 3: Write minimal implementation**

Create `img2ansi.py`:

```python
#!/usr/bin/env python3
# flake8: noqa: E501
"""img2ansi.py — Convert an image to traditional ANSI art (half-block glyphs).

Usage:
    python3 img2ansi.py <input_image> [options]
"""

import sys
import os
import argparse

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

from imgcommon import load_and_enhance, resize_for, lift_luminance

UPPER_HALF = "▀"  # ▀

# Classic 16-color CP437/VGA palette: (r, g, b, fg_sgr, bg_sgr)
PALETTE_16 = [
    (0, 0, 0, 30, 40),
    (170, 0, 0, 31, 41),
    (0, 170, 0, 32, 42),
    (170, 85, 0, 33, 43),
    (0, 0, 170, 34, 44),
    (170, 0, 170, 35, 45),
    (0, 170, 170, 36, 46),
    (170, 170, 170, 37, 47),
    (85, 85, 85, 90, 100),
    (255, 85, 85, 91, 101),
    (85, 255, 85, 92, 102),
    (255, 255, 85, 93, 103),
    (85, 85, 255, 94, 104),
    (255, 85, 255, 95, 105),
    (85, 255, 255, 96, 106),
    (255, 255, 255, 97, 107),
]


def rgb_to_256(r: int, g: int, b: int) -> int:
    """Map an RGB triple to the nearest xterm-256 index (16..255)."""
    # grayscale ramp check
    if abs(r - g) < 8 and abs(g - b) < 8:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + (r - 8) // 10
    r6 = round(r / 255 * 5)
    g6 = round(g / 255 * 5)
    b6 = round(b / 255 * 5)
    return 16 + 36 * r6 + 6 * g6 + b6


def rgb_to_16(r: int, g: int, b: int) -> tuple[int, int]:
    """Map an RGB triple to nearest 16-color palette (fg_sgr, bg_sgr)."""
    best = PALETTE_16[0]
    best_d = None
    for pr, pg, pb, fg, bg in PALETTE_16:
        d = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best = (pr, pg, pb, fg, bg)
    return best[3], best[4]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add img2ansi.py tests/test_img2ansi.py
git commit -m "feat: add ANSI color quantizers to img2ansi"
```

---

## Task 5: Half-block ANSI renderer (`image_to_ansi`)

**Files:**
- Modify: `img2ansi.py`
- Test: `tests/test_img2ansi.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_img2ansi.py`:

```python
from PIL import Image


def _two_row(top, bot, width=1):
    img = Image.new("RGB", (width, 2))
    for x in range(width):
        img.putpixel((x, 0), top)
        img.putpixel((x, 1), bot)
    return img


def test_truecolor_single_cell():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    line = out.splitlines()[0]
    assert "\x1b[38;2;255;0;0m" in line   # fg = top
    assert "\x1b[48;2;0;0;255m" in line   # bg = bottom
    assert "▀" in line               # ▀
    assert line.rstrip().endswith("\x1b[0m")


def test_cell_count_matches_width():
    img = _two_row((10, 20, 30), (40, 50, 60), width=5)
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    assert out.splitlines()[0].count("▀") == 5


def test_256_mode_uses_5_prefix():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="256")
    assert "\x1b[38;5;" in out
    assert "\x1b[48;5;" in out


def test_bbs16_mode_uses_sgr_codes():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="bbs16")
    # red fg (31 or 91), blue bg (44 or 104)
    assert ("\x1b[31m" in out) or ("\x1b[91m" in out)
    assert ("\x1b[44m" in out) or ("\x1b[104m" in out)


def test_odd_height_drops_trailing_row():
    img = Image.new("RGB", (1, 3), (0, 0, 0))
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    # 3 rows -> 1 cell row (floor(3/2))
    assert len([ln for ln in out.splitlines() if ln]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: FAIL — `AttributeError: module 'img2ansi' has no attribute 'image_to_ansi'`.

- [ ] **Step 3: Write minimal implementation**

Append to `img2ansi.py`:

```python
def _cell_escape(
    top: tuple[int, int, int],
    bot: tuple[int, int, int],
    mode: str,
) -> str:
    tr, tg, tb = top
    br, bg_, bb = bot
    if mode == "truecolor":
        return (
            f"\x1b[38;2;{tr};{tg};{tb}m"
            f"\x1b[48;2;{br};{bg_};{bb}m{UPPER_HALF}"
        )
    if mode == "256":
        return (
            f"\x1b[38;5;{rgb_to_256(tr, tg, tb)}m"
            f"\x1b[48;5;{rgb_to_256(br, bg_, bb)}m{UPPER_HALF}"
        )
    if mode == "bbs16":
        fg, _ = rgb_to_16(tr, tg, tb)
        _, bg_code = rgb_to_16(br, bg_, bb)
        return f"\x1b[{fg}m\x1b[{bg_code}m{UPPER_HALF}"
    raise ValueError(f"unknown mode: {mode}")


def image_to_ansi(img: Image.Image, mode: str = "truecolor") -> str:
    """Render an RGB image to ANSI half-block art. Samples 2 rows per cell."""
    img = img.convert("RGB")
    w, h = img.size
    rows = h // 2
    lines: list[str] = []
    for cy in range(rows):
        y = cy * 2
        cells: list[str] = []
        for x in range(w):
            top = img.getpixel((x, y))
            bot = img.getpixel((x, y + 1))
            cells.append(_cell_escape(top, bot, mode))
        lines.append("".join(cells) + "\x1b[0m")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add img2ansi.py tests/test_img2ansi.py
git commit -m "feat: add half-block ANSI renderer"
```

---

## Task 6: PNG rendering via HTML (`ansi_image_to_html`)

Build the HTML preview from the same per-cell color data. Reuse the
`min_lum` luminance lift so the preview matches the `.ans` source pixels.

**Files:**
- Modify: `img2ansi.py`
- Test: `tests/test_img2ansi.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_img2ansi.py`:

```python
def test_ansi_html_contains_cells():
    img = _two_row((255, 0, 0), (0, 0, 255), width=2)
    html = img2ansi.ansi_image_to_html(img, bg_color="#000000", font_size=8.0)
    assert "<pre>" in html
    assert "background:#000000" in html.replace(" ", "") or "#000000" in html
    assert "color:rgb(255,0,0)" in html.replace(" ", "")
    assert "background:rgb(0,0,255)" in html.replace(" ", "")
    assert "▀" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py::test_ansi_html_contains_cells -v`
Expected: FAIL — `AttributeError: ... 'ansi_image_to_html'`.

- [ ] **Step 3: Write minimal implementation**

Append to `img2ansi.py`:

```python
def ansi_image_to_html(
    img: Image.Image,
    bg_color: str,
    font_size: float,
) -> str:
    """Render the half-block art to HTML for html2image rasterization.

    Always truecolor in the PNG preview; the .ans file carries the
    quantized version for the chosen mode.
    """
    img = img.convert("RGB")
    w, h = img.size
    rows = h // 2
    lines_html: list[str] = []
    for cy in range(rows):
        y = cy * 2
        spans: list[str] = []
        for x in range(w):
            tr, tg, tb = img.getpixel((x, y))
            br, bg_, bb = img.getpixel((x, y + 1))
            spans.append(
                f'<span style="color:rgb({tr},{tg},{tb});'
                f'background:rgb({br},{bg_},{bb})">{UPPER_HALF}</span>'
            )
        lines_html.append("".join(spans))
    body = "<br>".join(lines_html)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>
  body {{ background:{bg_color}; margin:0; }}
  pre {{
    font-family:'Courier New',Courier,monospace;
    font-size:{font_size}px;
    line-height:{font_size}px;
    letter-spacing:0;
    white-space:pre;
    margin:0;
  }}
</style></head>
<body><pre>{body}</pre></body>
</html>"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```bash
git add img2ansi.py tests/test_img2ansi.py
git commit -m "feat: add ANSI HTML preview for PNG rendering"
```

---

## Task 7: CLI wiring (`main`)

**Files:**
- Modify: `img2ansi.py`

- [ ] **Step 1: Write the implementation**

Append to `img2ansi.py`:

```python
def _write_png(html: str, out_path: str, width: int, no_gpu: bool) -> None:
    try:
        from html2image import Html2Image  # type: ignore[import-untyped]
    except ImportError:
        print(
            "Gnarly wipeout, comrad! You need html2image to save a PNG. "
            "Run: pip install html2image"
        )
        return
    flags = ["--hide-scrollbars", "--no-sandbox", "--disable-setuid-sandbox"]
    if no_gpu:
        flags += [
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
        ]
    # px width: each cell ~ font_size*0.6 wide; height tracked by html2image
    px_w = int(width * 8.0 * 0.6) + 2
    hti = Html2Image(custom_flags=flags)
    print(f"Snapping the PNG to {out_path}...")
    hti.screenshot(
        html_str=html,
        save_as=os.path.basename(out_path),
        size=(px_w, px_w),  # square canvas; overflow trimmed by content
    )
    if os.path.dirname(out_path):
        os.rename(os.path.basename(out_path), out_path)
    print("Image generated, stay frosty.")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("-w", "--width", type=int, default=80)
    parser.add_argument(
        "--mode",
        choices=["truecolor", "256", "bbs16"],
        default="truecolor",
    )
    parser.add_argument("--png", action="store_true", default=False)
    parser.add_argument("-c", "--contrast", type=float, default=1.5)
    parser.add_argument("-s", "--sharpness", type=float, default=2.5)
    parser.add_argument("-B", "--brightness", type=float, default=1.0)
    parser.add_argument("--saturate", type=float, default=1.0)
    parser.add_argument("--min-lum", type=float, default=0.0)
    parser.add_argument("--no-gpu", action="store_true", default=False)
    parser.add_argument("-h", "--help", action="help")
    args = parser.parse_args()

    if not args.input or not os.path.exists(args.input):
        print("Bummer dude, need a valid input image.")
        sys.exit(1)

    base = (
        os.path.splitext(args.output)[0]
        if args.output
        else os.path.splitext(args.input)[0] + "_ansi"
    )
    ans_path = (
        args.output
        if (args.output and os.path.splitext(args.output)[1])
        else base + ".ans"
    )

    img = load_and_enhance(
        args.input,
        args.contrast,
        args.sharpness,
        args.brightness,
        args.saturate,
    )
    # half-block: cell_aspect 1.0, then sample 2 rows per cell ->
    # need an even pixel height of ~ 2x the cell rows.
    img = resize_for(img, args.width, cell_aspect=1.0)

    if args.min_lum > 0:
        img = img.convert("RGB")
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                img.putpixel((x, y), lift_luminance(r, g, b, args.min_lum))

    print("Carving the ANSI wave...")
    ansi = image_to_ansi(img, mode=args.mode)
    with open(ans_path, "w", encoding="utf-8") as f:
        f.write(ansi + "\n")
    print(f"ANSI locked in at: {ans_path}")

    if args.png:
        png_path = os.path.splitext(ans_path)[0] + ".png"
        html = ansi_image_to_html(img, bg_color="#000000", font_size=8.0)
        _write_png(html, png_path, args.width, args.no_gpu)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test: write a .ans and view it**

Run: `./venv/bin/python img2ansi.py enterprise.jpg -w 80 --mode truecolor -o /tmp/ent.ans && cat /tmp/ent.ans | head -5`
Expected: prints "ANSI locked in at: /tmp/ent.ans" then renders colored half-block art in the terminal.

- [ ] **Step 3: Smoke-test each mode runs without error**

Run: `for m in truecolor 256 bbs16; do ./venv/bin/python img2ansi.py enterprise.jpg -w 40 --mode $m -o /tmp/ent_$m.ans; done`
Expected: three "ANSI locked in" lines, no traceback.

- [ ] **Step 4: Smoke-test PNG path**

Run: `./venv/bin/python img2ansi.py enterprise.jpg -w 80 --png -o /tmp/ent.ans && ls -l /tmp/ent.png`
Expected: PNG created, non-zero size (skip/ignore if html2image/chrome unavailable — `.ans` still written).

- [ ] **Step 5: Run the full test suite**

Run: `./venv/bin/python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add img2ansi.py
git commit -m "feat: wire img2ansi CLI (modes, .ans output, optional PNG)"
```

---

## Task 8: Help text + README note

**Files:**
- Modify: `img2ansi.py` (docstring)

- [ ] **Step 1: Expand the module docstring with options**

Replace the short docstring at the top of `img2ansi.py` with:

```python
"""img2ansi.py — Convert an image to traditional ANSI art (half-block glyphs).

Each character cell is an upper-half block (▀): the top source pixel becomes
the foreground color, the bottom pixel the background color, doubling vertical
resolution.

Usage:
    python3 img2ansi.py <input_image> [options]

Options:
    -o, --output      Output path (default: <input>_ansi.ans)
    -w, --width       Character columns (default: 80, BBS-authentic)
    --mode            truecolor (default) | 256 | bbs16
    --png             Also rasterize a PNG via html2image
    -c, --contrast    Contrast multiplier (default: 1.5)
    -s, --sharpness   Sharpness multiplier (default: 2.5)
    -B, --brightness  Brightness multiplier (default: 1.0)
    --saturate        Saturation multiplier (default: 1.0)
    --min-lum         Minimum HLS luminance 0.0-1.0 (default: 0.0)
    --no-gpu          Disable GPU for html2image (PNG only)
    -h, --help        Show this help

View output:  cat <file>.ans
"""
```

- [ ] **Step 2: Verify help renders**

Run: `./venv/bin/python img2ansi.py --help`
Expected: argparse usage prints, no traceback.

- [ ] **Step 3: Final full suite + commit**

```bash
./venv/bin/python -m pytest tests/ -v
git add img2ansi.py
git commit -m "docs: img2ansi help text and options"
```

---

## Self-Review Notes

- **Spec coverage:** shared module (T1–T2), img2ascii refactor (T3), half-block render (T5), three modes (T4–T5), .ans + PNG outputs (T5–T7), CLI flags (T7), help text (T8), testing per task. All spec sections mapped.
- **Type consistency:** `image_to_ansi(img, mode)`, `ansi_image_to_html(img, bg_color, font_size)`, `rgb_to_256 -> int`, `rgb_to_16 -> (fg, bg)`, `resize_for(img, width, cell_aspect)`, `load_and_enhance(path, contrast, sharpness, brightness, saturate)` — used consistently across tasks.
- **Known deviation from spec:** spec §Architecture suggested the ASCII path call `resize_for(..., 0.48)`. T3 deliberately does NOT swap the resize (keeps `int()` truncation) to guarantee byte-identical existing output; only `lift_luminance` is shared from the ASCII side. Documented in T3 preamble.
