# ascii Unified CLI Implementation Plan

> NOTE: This plan’s original `pico` naming has been superseded by the shipped `ascii` CLI; treat remaining `pico` references below as historical unless updated.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate `img2ansi.py` / `img2ascii.py` command-line tools with a single `ascii` command that renders either style via `--style ascii|ansi` (default `ascii`).

**Architecture:** `img2ansi.py` and `img2ascii.py` become pure render libraries (no `main()`). A new `ascii.py` owns all CLI concerns — one argparse surface, per-style default resolution, cross-style flag validation, dispatch, and output writing. The duplicated Html2Image PNG routine is extracted once into `imgcommon.write_png_from_html`. The package is installable (`pip install -e .` exposes `ascii`) and the directory is renamed `pico_ansii → pico_ascii`.

---

## Important constraints (read before starting)

- **Do not move these tested symbols.** The suite imports them by module name:
  - `img2ansi`: `image_to_ansi`, `rgb_to_256`, `rgb_to_16`, `ansi_image_to_html` (keep `_cell_escape`, `PALETTE_16`, `UPPER_HALF` too).
  - `img2ascii`: `image_to_ascii_html`, and `lift_luminance` (re-exported from `imgcommon`).
- **Run all tasks from inside the current repo dir** (`.../pico_ansii`, which is the git repo root). The folder rename is the **final** task — done as `mv` from the parent, not `git mv` (you cannot `git mv` the repo root; tracked paths are root-relative so history is unaffected).
- **Baseline:** `./venv/bin/python -m pytest tests/ -q` → `19 passed`. It must stay green after every task.
- Default style is `ascii`. Flags with style-divergent defaults parse as `None` and resolve after `--style` is known.

---

## File structure

| File | Change | Responsibility |
|------|--------|----------------|
| `imgcommon.py` | modify | Image prep (unchanged) **+** new `write_png_from_html` shared PNG writer. |
| `img2ansi.py` | modify | ANSI render backend only — remove `main`, argparse, `_write_png`. |
| `img2ascii.py` | modify | ASCII render backend only — remove `main`, argparse, inline Html2Image. |
| `pico.py` | create | The unified CLI. |
| `pyproject.toml` | modify | Add `[build-system]`, `[project]`, `[project.scripts]`, `[tool.setuptools]`. |
| `requirements.txt` | modify | Add `setuptools` (build/editable-install dep). |
| `README.md` | modify | Rewrite around the single `pico` command. |
| `tests/test_imgcommon.py` | modify | Add `write_png_from_html` missing-dep test. |
| `tests/test_pico.py` | create | Parser defaults, width resolution, cross-style validation, exit codes. |

---

## Task 1: Extract shared `write_png_from_html` into imgcommon

**Files:**
- Modify: `imgcommon.py`
- Test: `tests/test_imgcommon.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_imgcommon.py`:

```python
import os
import sys

import imgcommon


def test_write_png_missing_html2image_returns_without_raising(
    monkeypatch, capsys, tmp_path
):
    # Force `import html2image` to raise ImportError inside the function.
    monkeypatch.setitem(sys.modules, "html2image", None)
    out = str(tmp_path / "out.png")

    imgcommon.write_png_from_html("<html></html>", out, 10, 10, False)

    captured = capsys.readouterr()
    assert "html2image" in captured.out  # prints the install hint
    assert not os.path.exists(out)       # no file written, no exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py::test_write_png_missing_html2image_returns_without_raising -v`
Expected: FAIL — `AttributeError: module 'imgcommon' has no attribute 'write_png_from_html'`

- [ ] **Step 3: Implement `write_png_from_html`**

In `imgcommon.py`, add `os` and `shutil` to imports at the top:

```python
import colorsys
import os
import shutil

from PIL import Image, ImageEnhance
```

Append this function to the end of `imgcommon.py`:

```python
def write_png_from_html(
    html: str,
    out_path: str,
    px_w: int,
    px_h: int,
    no_gpu: bool,
) -> None:
    """Rasterize HTML to a PNG via headless Chrome (html2image).

    A missing html2image install is non-fatal: prints a hint and returns so
    any already-written .ans/.html is preserved. Uses shutil.move so output
    across filesystems works.
    """
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
    hti = Html2Image(custom_flags=flags)
    print(f"Snapping the PNG to {out_path}...")
    hti.screenshot(
        html_str=html,
        save_as=os.path.basename(out_path),
        size=(px_w, px_h),
    )
    if os.path.dirname(out_path):
        shutil.move(os.path.basename(out_path), out_path)
    print("Image generated, stay frosty.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest tests/test_imgcommon.py -v`
Expected: PASS (all imgcommon tests green)

- [ ] **Step 5: Commit**

```bash
git add imgcommon.py tests/test_imgcommon.py
git commit -m "feat: add shared write_png_from_html to imgcommon"
```

---

## Task 2: Reduce img2ansi.py to a render library

**Files:**
- Modify: `img2ansi.py`
- Test: `tests/test_img2ansi.py` (existing, must still pass)

- [ ] **Step 1: Confirm the safety net is green**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: PASS (these tests guard the symbols we must keep)

- [ ] **Step 2: Remove the CLI from img2ansi.py**

Delete these from `img2ansi.py`:
- the `_write_png` function (entire definition),
- the `main` function (entire definition),
- the `if __name__ == "__main__": main()` block,
- now-unused imports `argparse` and `shutil`.

Keep everything else: module docstring (update the `Usage` line — see below), the Pillow import guard, `from imgcommon import load_and_enhance, resize_for, lift_luminance`, `UPPER_HALF`, `PALETTE_16`, `rgb_to_256`, `rgb_to_16`, `_cell_escape`, `image_to_ansi`, `ansi_image_to_html`.

Replace the module docstring's usage block so it documents the library role:

```python
"""img2ansi.py — ANSI half-block render backend for pico.

Each character cell is an upper-half block (▀): the top source pixel becomes
the foreground color, the bottom pixel the background color, doubling vertical
resolution. CLI lives in pico.py (`pico --style ansi`).
"""
```

Leave `import sys` and `import os` only if still referenced. After removing
`main`/`_write_png`, `os` is unused — remove `import os`. `sys` is still used by
the Pillow import guard (`sys.exit(1)`) — keep it.

- [ ] **Step 3: Verify nothing references the removed names**

Run: `grep -nE "argparse|_write_png|def main|__main__|shutil|import os" img2ansi.py`
Expected: no matches.

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/python -m pytest tests/test_img2ansi.py -v`
Expected: PASS (unchanged count)

- [ ] **Step 5: Commit**

```bash
git add img2ansi.py
git commit -m "refactor: make img2ansi a render library (drop CLI)"
```

---

## Task 3: Reduce img2ascii.py to a render library

**Files:**
- Modify: `img2ascii.py`
- Test: `tests/test_img2ascii_regression.py` (existing, must still pass)

- [ ] **Step 1: Confirm the safety net is green**

Run: `./venv/bin/python -m pytest tests/test_img2ascii_regression.py -v`
Expected: PASS

- [ ] **Step 2: Remove the CLI from img2ascii.py**

Delete from `img2ascii.py`:
- the `main` function (entire definition),
- the `if __name__ == "__main__": main()` block,
- the top-level `try: from html2image import Html2Image ... except ImportError: Html2Image = None` block (PNG writing now lives in `imgcommon.write_png_from_html`),
- now-unused imports `argparse`, `shutil`, `sys` (verify `sys` unused after edit — the Pillow guard uses it, so keep `sys` if the `try/except ImportError` guard around `from PIL import ...` remains; it does — **keep `sys`**), and `os` (verify unused — after removing `main`, `os` is unused; remove it).

Keep: module docstring (update — see below), the Pillow import guard, `from imgcommon import lift_luminance` (this re-export is asserted by a test — **must stay**), `ascii_chars`, `image_to_ascii_html` (unchanged signature and body).

Replace the module docstring:

```python
"""img2ascii.py — colored-ASCII render backend for pico.

Maps each pixel's brightness to an ASCII glyph and colors it with the pixel's
RGB, emitting HTML. CLI lives in pico.py (`pico --style ascii`, the default).
"""
```

- [ ] **Step 3: Verify removals**

Run: `grep -nE "argparse|def main|__main__|Html2Image|import shutil|import os" img2ascii.py`
Expected: no matches.

Run: `grep -n "from imgcommon import lift_luminance" img2ascii.py`
Expected: one match (the required re-export).

- [ ] **Step 4: Run the tests**

Run: `./venv/bin/python -m pytest tests/test_img2ascii_regression.py -v`
Expected: PASS (both tests, including `test_lift_luminance_still_exposed`)

- [ ] **Step 5: Commit**

```bash
git add img2ascii.py
git commit -m "refactor: make img2ascii a render library (drop CLI)"
```

---

## Task 4: Create pico.py — the unified CLI

Build `pico.py` in TDD slices: parser/defaults/validation first (pure, testable), then the render dispatch (mirrors the deleted `main()`s exactly).

**Files:**
- Create: `pico.py`
- Test: `tests/test_pico.py`

### Task 4a: Parser, default resolution, cross-style validation

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pico.py`:

```python
import sys

import pytest

import pico


def test_default_style_is_ascii():
    args = pico.build_parser().parse_args(["in.jpg"])
    assert args.style == "ascii"


def test_width_resolves_per_style():
    assert pico.resolve_width("ascii", None) == 350
    assert pico.resolve_width("ansi", None) == 80
    assert pico.resolve_width("ascii", 120) == 120
    assert pico.resolve_width("ansi", 120) == 120


def test_cross_style_ok_when_flags_match_style():
    p = pico.build_parser()
    assert pico.cross_style_error(p.parse_args(["in.jpg"])) is None
    assert pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--mode", "256"])
    ) is None
    assert pico.cross_style_error(
        p.parse_args(["in.jpg", "--html"])
    ) is None


def test_ansi_flag_under_ascii_errors():
    p = pico.build_parser()
    msg = pico.cross_style_error(p.parse_args(["in.jpg", "--mode", "256"]))
    assert msg == "--mode requires --style ansi"
    msg = pico.cross_style_error(p.parse_args(["in.jpg", "--png"]))
    assert msg == "--png requires --style ansi"


def test_ascii_flag_under_ansi_errors():
    p = pico.build_parser()
    msg = pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--html"])
    )
    assert msg == "--html requires --style ascii"
    msg = pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--font-size", "5"])
    )
    assert msg == "--font-size requires --style ascii"


def test_main_wrong_style_exits_2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pico", "in.jpg", "--mode", "256"])
    with pytest.raises(SystemExit) as exc:
        pico.main()
    assert exc.value.code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_pico.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'pico'`

- [ ] **Step 3: Create pico.py with parser + helpers**

Create `pico.py`:

```python
#!/usr/bin/env python3
# flake8: noqa: E501
"""pico — convert an image to colored ASCII or traditional ANSI art.

Usage:
    pico <input_image> [--style ascii|ansi] [options]
    python3 pico.py <input_image> [--style ascii|ansi] [options]

Default style is `ascii`. Style-specific flags used under the wrong style are
rejected (exit 2).

Shared options:
    -o, --output      Output path
    -w, --width       Character columns (default: ascii 350, ansi 80)
    -c, --contrast    Contrast multiplier (default: 1.5)
    -s, --sharpness   Sharpness multiplier (default: 2.5)
    -B, --brightness  Brightness multiplier (default: 1.0)
    --saturate        Saturation multiplier (default: 1.0)
    --min-lum         Minimum HLS luminance 0.0-1.0 (default: 0.0)
    --no-gpu          Disable GPU in html2image (PNG only)
    -h, --help        Show help

ascii-only:
    --html            Save HTML instead of PNG
    --img-width       Force output PNG pixel width
    --img-height      Force output PNG pixel height
    -b, --bg          Background color (default: #000000)
    --font-size       Font size px (default: 4.0 HTML / 6.5 PNG)
    --select          Auto-highlight the text

ansi-only:
    --mode            truecolor (default) | 256 | bbs16
    --png             Also rasterize a PNG
"""

import argparse
import os
import sys

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

import img2ansi
import img2ascii
from imgcommon import (
    load_and_enhance,
    resize_for,
    lift_luminance,
    write_png_from_html,
)

# (attr on args, display name, "was it set?" predicate)
ANSI_FLAGS = [
    ("mode", "--mode", lambda v: v is not None),
    ("png", "--png", bool),
]
ASCII_FLAGS = [
    ("html", "--html", bool),
    ("img_width", "--img-width", lambda v: v is not None),
    ("img_height", "--img-height", lambda v: v is not None),
    ("bg", "--bg", lambda v: v is not None),
    ("font_size", "--font-size", lambda v: v is not None),
    ("select", "--select", bool),
]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("input", nargs="?")
    p.add_argument("--style", choices=["ascii", "ansi"], default="ascii")
    p.add_argument("-o", "--output")
    p.add_argument("-w", "--width", type=int, default=None)
    p.add_argument("-c", "--contrast", type=float, default=1.5)
    p.add_argument("-s", "--sharpness", type=float, default=2.5)
    p.add_argument("-B", "--brightness", type=float, default=1.0)
    p.add_argument("--saturate", type=float, default=1.0)
    p.add_argument("--min-lum", type=float, default=0.0)
    p.add_argument("--no-gpu", action="store_true", default=False)
    # ascii-only (defaults None/False so misuse is detectable)
    p.add_argument("--html", action="store_true", default=False)
    p.add_argument("--img-width", type=int, default=None)
    p.add_argument("--img-height", type=int, default=None)
    p.add_argument("-b", "--bg", default=None)
    p.add_argument("--font-size", type=float, default=None)
    p.add_argument("--select", action="store_true", default=False)
    # ansi-only
    p.add_argument("--mode", choices=["truecolor", "256", "bbs16"], default=None)
    p.add_argument("--png", action="store_true", default=False)
    p.add_argument("-h", "--help", action="help")
    return p


def cross_style_error(args) -> str | None:
    """Return an error message if a style-specific flag is misused, else None."""
    wrong = ANSI_FLAGS if args.style == "ascii" else ASCII_FLAGS
    other = "ansi" if args.style == "ascii" else "ascii"
    for attr, name, is_set in wrong:
        if is_set(getattr(args, attr)):
            return f"{name} requires --style {other}"
    return None


def resolve_width(style: str, width: int | None) -> int:
    if width is not None:
        return width
    return 350 if style == "ascii" else 80


def main():
    parser = build_parser()
    args = parser.parse_args()

    err = cross_style_error(args)
    if err:
        print(f"error: {err}", file=sys.stderr)
        sys.exit(2)

    if not args.input or not os.path.exists(args.input):
        print("Bummer dude, need a valid input image.")
        sys.exit(1)

    width = resolve_width(args.style, args.width)
    if args.style == "ansi":
        _render_ansi(args, width)
    else:
        _render_ascii(args, width)


if __name__ == "__main__":
    main()
```

> Note: `_render_ansi` / `_render_ascii` are added in Task 4b. The validation/exit-2 tests in this slice never reach them (a wrong-style flag exits before dispatch, and `test_main_wrong_style_exits_2` uses `--mode` which fails validation first).

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_pico.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add pico.py tests/test_pico.py
git commit -m "feat: pico CLI parser, default + cross-style validation"
```

### Task 4b: Render dispatch (ansi + ascii)

These mirror the behavior of the deleted `main()`s exactly.

- [ ] **Step 1: Write the failing integration tests**

Append to `tests/test_pico.py`:

```python
import os as _os

from PIL import Image as _Image


def _tiny_image(tmp_path):
    path = tmp_path / "tiny.png"
    img = _Image.new("RGB", (4, 4), (200, 100, 50))
    img.save(path)
    return str(path)


def test_ansi_writes_ans_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.ans")
    monkeypatch.setattr(
        sys, "argv", ["pico", src, "--style", "ansi", "-o", out]
    )
    pico.main()
    assert _os.path.exists(out)
    data = open(out, encoding="utf-8").read()
    assert "\x1b[" in data and "▀" in data


def test_ascii_html_writes_html_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(sys, "argv", ["pico", src, "--html", "-o", out])
    pico.main()
    assert _os.path.exists(out)
    assert "<pre>" in open(out, encoding="utf-8").read()


def test_ascii_default_output_path(tmp_path, monkeypatch):
    # ascii + --html with no -o -> <input>_ascii.html next to source
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pico", src, "--html"])
    pico.main()
    expected = _os.path.splitext(src)[0] + "_ascii.html"
    assert _os.path.exists(expected)


def test_ansi_default_output_path(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["pico", src, "--style", "ansi"])
    pico.main()
    expected = _os.path.splitext(src)[0] + "_ansi.ans"
    assert _os.path.exists(expected)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_pico.py -k "writes or default_output" -v`
Expected: FAIL — `AttributeError: module 'pico' has no attribute '_render_ansi'`

- [ ] **Step 3: Implement the dispatch functions**

In `pico.py`, insert these two functions above `def main():`.

```python
def _render_ansi(args, width: int) -> None:
    mode = args.mode if args.mode is not None else "truecolor"

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
    img = resize_for(img, width, cell_aspect=1.0)

    if args.min_lum > 0:
        img = img.convert("RGB")
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                img.putpixel((x, y), lift_luminance(r, g, b, args.min_lum))

    print("Carving the ANSI wave...")
    ansi = img2ansi.image_to_ansi(img, mode=mode)
    with open(ans_path, "w", encoding="utf-8") as f:
        f.write(ansi + "\n")
    print(f"ANSI locked in at: {ans_path}")

    if args.png:
        png_path = os.path.splitext(ans_path)[0] + ".png"
        font_size = 8.0
        rows = img.height // 2
        html = img2ansi.ansi_image_to_html(
            img, bg_color="#000000", font_size=font_size
        )
        px_w = int(width * font_size * 0.6) + 2
        px_h = int(rows * font_size) + 2
        write_png_from_html(html, png_path, px_w, px_h, args.no_gpu)


def _render_ascii(args, width: int) -> None:
    bg = args.bg if args.bg is not None else "#000000"
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 6.5)
    )

    ext = ".html" if args.html else ".png"
    if args.output:
        base, given_ext = os.path.splitext(args.output)
        output_path = args.output if given_ext else args.output + ext
    else:
        output_path = os.path.splitext(args.input)[0] + "_ascii" + ext

    img = Image.open(args.input)

    aspect = img.height / img.width
    ascii_height = int(width * aspect * 0.48)
    char_width_px = font_size * 0.6
    line_height_px = font_size * 0.8
    auto_w = int((width * char_width_px) + 2)
    auto_h = int((ascii_height * line_height_px) + 2)

    scale = 1.0
    if args.img_width and not args.img_height:
        px_w = args.img_width
        px_h = int(px_w * (auto_h / auto_w))
        scale = px_w / auto_w
    elif args.img_height and not args.img_width:
        px_h = args.img_height
        px_w = int(px_h * (auto_w / auto_h))
        scale = px_h / auto_h
    elif args.img_width and args.img_height:
        px_w = args.img_width
        px_h = args.img_height
        scale = min(px_w / auto_w, px_h / auto_h)
    else:
        px_w = auto_w
        px_h = auto_h

    print("Carving the HTML wave...")
    html = img2ascii.image_to_ascii_html(
        img,
        width,
        args.contrast,
        args.sharpness,
        args.brightness,
        args.min_lum,
        args.saturate,
        bg,
        font_size,
        args.select,
        scale,
    )

    if args.html:
        html_path = os.path.splitext(output_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML locked in at: {html_path}")
    else:
        write_png_from_html(html, output_path, px_w, px_h, args.no_gpu)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_pico.py -v`
Expected: PASS (all pico tests, including the new file-writing ones)

- [ ] **Step 5: Run the full suite**

Run: `./venv/bin/python -m pytest tests/ -q`
Expected: PASS — count is now `19 + new pico/imgcommon tests`, all green.

- [ ] **Step 6: Manual smoke test**

```bash
./venv/bin/python pico.py enterprise.jpg --style ansi -o /tmp/smoke.ans
cat /tmp/smoke.ans | head -3
./venv/bin/python pico.py enterprise.jpg --html -o /tmp/smoke.html
grep -c "<pre>" /tmp/smoke.html
./venv/bin/python pico.py enterprise.jpg --mode 256; echo "exit=$?"   # expect error + exit 2
```
Expected: `.ans` has escape codes; HTML has one `<pre>`; the third prints `error: --mode requires --style ansi` and `exit=2`.

- [ ] **Step 7: Commit**

```bash
git add pico.py tests/test_pico.py
git commit -m "feat: pico render dispatch for ansi and ascii"
```

---

## Task 5: Packaging — installable `pico` command

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Add packaging config to pyproject.toml**

Prepend to `pyproject.toml` (keep the existing `[tool.black]` section below it):

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pico-ascii"
version = "0.1.0"
description = "Convert images to colored ASCII or traditional ANSI art."
requires-python = ">=3.14"
dependencies = ["Pillow"]

[project.scripts]
pico = "pico:main"

[tool.setuptools]
py-modules = ["pico", "img2ansi", "img2ascii", "imgcommon"]

```

- [ ] **Step 2: Add setuptools to requirements.txt**

Add a line to `requirements.txt`:

```
setuptools
```

- [ ] **Step 3: Install setuptools, then editable-install the package**

Run:
```bash
./venv/bin/pip install setuptools
./venv/bin/pip install -e .
```
Expected: `Successfully installed pico-ascii-0.1.0` (or similar). No errors.

- [ ] **Step 4: Verify the `pico` command exists and runs**

Run:
```bash
./venv/bin/pico enterprise.jpg --style ansi -o /tmp/installed.ans && head -1 /tmp/installed.ans
./venv/bin/pico enterprise.jpg --mode 256; echo "exit=$?"
```
Expected: first writes an `.ans`; second prints `error: --mode requires --style ansi` with `exit=2`.

- [ ] **Step 5: Confirm tests still pass**

Run: `./venv/bin/python -m pytest tests/ -q`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "build: package pico as an installable console command"
```

---

## Task 6: Rewrite README around `pico`

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace README.md content**

Rewrite `README.md` so every invocation uses `pico`. Use this content:

````markdown
# pico

Convert any image into terminal/text art with one command. Two render styles,
one shared image-prep core:

| Style | `--style` | Output | Best viewed in |
|-------|-----------|--------|----------------|
| Colored **ASCII** — luminance picks a glyph (`$@B%8&…`), each character keeps its own RGB color | `ascii` (default) | HTML or PNG | Browser / image viewer |
| Traditional **ANSI** — half-block `▀` (top pixel = foreground, bottom = background) | `ansi` | `.ans` + optional PNG | Terminal (`cat`) / image viewer |

---

## Requirements

- Python 3.14+
- [Pillow](https://pypi.org/project/Pillow/) — image loading/processing
- [html2image](https://pypi.org/project/html2image/) — **only** for PNG output (needs Chrome/Chromium)
- pytest — only for the test suite

Install in a venv:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .          # exposes the `pico` command on PATH
```

Without installing, run it directly: `python3 pico.py <image> ...`.

---

## Usage

```bash
pico <input_image> [--style ascii|ansi] [options]
```

`--style` defaults to `ascii`. A style-specific flag used under the wrong style
is rejected with a clear error (exit 2), e.g. `pico in.jpg --mode 256` →
`error: --mode requires --style ansi`.

### Shared options

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | Path to the source image (positional) |
| `--style` | `ascii` | `ascii` \| `ansi` |
| `-o, --output` | per style (below) | Output path. Extension respected if given |
| `-w, --width` | `350` (ascii) / `80` (ansi) | Character columns |
| `-c, --contrast` | `1.5` | Contrast multiplier |
| `-s, --sharpness` | `2.5` | Sharpness multiplier |
| `-B, --brightness` | `1.0` | Brightness multiplier |
| `--saturate` | `1.0` | Saturation multiplier |
| `--min-lum` | `0.0` | Minimum HLS luminance floor (0.0–1.0) |
| `--no-gpu` | off | Disable GPU in html2image (PNG only) |
| `-h, --help` | — | Show help |

### ascii-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--html` | off (PNG) | Save HTML instead of a PNG |
| `--img-width` | auto | Force output PNG pixel width |
| `--img-height` | auto | Force output PNG pixel height |
| `-b, --bg` | `#000000` | Background color |
| `--font-size` | `4.0` (HTML) / `6.5` (PNG) | Font size in px |
| `--select` | off | Auto-highlight the text |

Default output: `<input>_ascii.png` (or `<input>_ascii.html` with `--html`).

### ansi-only options

| Flag | Default | Description |
|------|---------|-------------|
| `--mode` | `truecolor` | `truecolor` \| `256` \| `bbs16` |
| `--png` | off | Also rasterize a PNG |

Default output: `<input>_ansi.ans` (plus `<input>_ansi.png` with `--png`).

Color modes: **truecolor** = 24-bit (needs a truecolor terminal); **256** =
xterm-256 palette; **bbs16** = classic 16-color CP437/VGA (most retro, works
almost everywhere).

---

## Examples

```bash
# Colored ASCII (default style) -> high-detail PNG next to the source
pico enterprise.jpg
#   -> enterprise_ascii.png

# Standalone zoomable HTML
pico planet.jpg --html
#   -> planet_ascii.html

# Force a 1920px-wide PNG on dark-grey
pico planet.jpg --img-width 1920 -b "#101010"

# Traditional ANSI, 80-col truecolor .ans
pico enterprise.jpg --style ansi
cat enterprise_ansi.ans

# Retro 16-color, wider, also a PNG
pico planet.jpg --style ansi -w 100 --mode bbs16 --png

# 256-color, lift the dark areas
pico planet.jpg --style ansi --mode 256 --min-lum 0.15
```

---

## Project layout

```
imgcommon.py   Shared helpers: lift_luminance, load_and_enhance, resize_for, write_png_from_html
img2ascii.py   Colored-ASCII render backend
img2ansi.py    Traditional-ANSI render backend
pico.py        Unified CLI (argument parsing, dispatch, output)
tests/         pytest suite
docs/superpowers/  Design spec + implementation plan
```

---

## PNG output notes

- PNG requires `html2image` (drives headless Chrome/Chromium). If Chrome isn't
  found or crashes, add `--no-gpu`.
- Without `html2image`, the `.ans`/`.html` is still written; the PNG step prints
  a hint and is skipped.
- Output is moved with `shutil.move`, so writing across filesystems works.

---

## Running the tests

```bash
./venv/bin/python -m pytest tests/ -v
```

---

## How it works (short version)

1. `imgcommon.load_and_enhance` opens the image and applies brightness →
   contrast → saturation → sharpness (ANSI path; the ASCII renderer applies the
   same chain internally).
2. The image is resized to the character grid (`cell_aspect` differs per style:
   `0.48` line-spacing for ASCII, `1.0` for ANSI half-blocks which sample 2 rows
   per cell).
3. `imgcommon.lift_luminance` optionally raises dark pixels to a floor
   (`--min-lum`).
4. Each backend renders: ASCII → colored `<span>`s; ANSI → half-block glyphs
   with SGR escape codes (and HTML spans for the PNG preview).
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README around the unified pico command"
```

---

## Task 7: Rename directory `pico_ansii → pico_ascii`

This is the final task — it changes the folder name your shell is sitting in.
The dir is the git repo root, so this is a filesystem `mv` (not `git mv`); git
tracks files by root-relative path, so history is unaffected.

- [ ] **Step 1: Confirm a clean tree**

Run: `git status --porcelain`
Expected: empty (everything committed).

- [ ] **Step 2: Rename from the parent directory**

Run:
```bash
mv /home/brian/Documents/c0de_box/scripts/pico_ansii /home/brian/Documents/c0de_box/scripts/pico_ascii
```

- [ ] **Step 3: Re-enter the renamed directory and reinstall the editable package**

The old path is now stale. Work from the new path:
```bash
cd /home/brian/Documents/c0de_box/scripts/pico_ascii
./venv/bin/pip install -e .       # refresh the editable install's recorded path
```
Expected: reinstalls cleanly.

- [ ] **Step 4: Verify everything still works at the new path**

Run:
```bash
./venv/bin/python -m pytest tests/ -q
./venv/bin/pico enterprise.jpg --style ansi -o /tmp/renamed.ans && head -1 /tmp/renamed.ans
```
Expected: tests green; `.ans` written.

- [ ] **Step 5: Note on git history**

The repo root folder rename is invisible to git (no tracked path changed), so
there is nothing to commit for the rename itself. Confirm:

Run: `git status --porcelain`
Expected: empty.

---

## Self-review checklist (already applied)

- **Spec coverage:** shared `write_png_from_html` (Task 1) · backends stripped to libraries with tested symbols preserved (Tasks 2–3) · unified parser, default ascii, width resolution, cross-style error exit 2 (Task 4a) · per-style dispatch + output naming (Task 4b) · packaging/console script (Task 5) · README rewrite (Task 6) · dir rename (Task 7). All spec sections covered.
- **No placeholders:** every code step shows complete code; every run step states the expected result.
- **Type/name consistency:** `build_parser`, `cross_style_error`, `resolve_width`, `_render_ansi`, `_render_ascii`, `write_png_from_html` used consistently across tasks and tests. Flag attrs (`img_width`, `img_height`, `font_size`, `bg`, `mode`, `png`, `html`, `select`) match argparse dest names.
- **Behavior parity:** `_render_ansi` / `_render_ascii` reproduce the deleted `main()` logic verbatim (defaults, output-path rules, min-lum handling, scale math), so output is unchanged.
```
