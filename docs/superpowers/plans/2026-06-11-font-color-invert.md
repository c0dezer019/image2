# Font color override + color inversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--invert` (color inversion, ascii+ansi) and `--monochrome`/`--font-color` (solid font color override, ascii only) CLI flags.

**Architecture:** `--invert` is applied once to the opened RGB image in `image2.main()` via `PIL.ImageOps.invert`, before enhancement/render dispatch — no backend changes needed. `--monochrome`/`--font-color` are resolved in `_render_ascii` and passed through to `img2ascii.image_to_ascii_html`, which gains a monochrome row-rendering branch that wraps each row's glyphs in a single `<span style="color:{font_color}">` instead of per-pixel-color spans.

**Tech Stack:** Python, Pillow (PIL.ImageOps), argparse, pytest.

---

### Task 1: `img2ascii.image_to_ascii_html` monochrome rendering

**Files:**
- Modify: `img2ascii.py:25-39` (signature), `img2ascii.py:69-93` (row rendering)
- Test: `tests/test_img2ascii_regression.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_img2ascii_regression.py`:

```python
def test_image_to_ascii_html_monochrome_uses_font_color():
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
        monochrome=True,
        font_color="#00ff00",
    )
    assert "color:#00ff00" in html
    assert "rgb(" not in html


def test_image_to_ascii_html_default_not_monochrome():
    img = Image.new("RGB", (4, 4), (255, 0, 0))

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
    assert "rgb(" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_img2ascii_regression.py -v`
Expected: `test_image_to_ascii_html_monochrome_uses_font_color` FAILs with
`TypeError: image_to_ascii_html() got an unexpected keyword argument 'monochrome'`.
`test_image_to_ascii_html_default_not_monochrome` should PASS already (sanity check of current behavior).

- [ ] **Step 3: Update the function signature**

In `img2ascii.py`, change the signature (lines 25-39) from:

```python
def image_to_ascii_html(
    img: Image.Image,
    width: int,
    contrast: float,
    sharpness: float,
    brightness: float,
    min_lum: float,
    saturate: float,
    bg_color: str,
    font_size: float,
    auto_select: bool,
    text_scale: float,
    px_w: int = 0,
    px_h: int = 0,
) -> str:
```

to:

```python
def image_to_ascii_html(
    img: Image.Image,
    width: int,
    contrast: float,
    sharpness: float,
    brightness: float,
    min_lum: float,
    saturate: float,
    bg_color: str,
    font_size: float,
    auto_select: bool,
    text_scale: float,
    px_w: int = 0,
    px_h: int = 0,
    monochrome: bool = False,
    font_color: str = "#ffffff",
) -> str:
```

- [ ] **Step 4: Add the monochrome row-rendering branch**

In `img2ascii.py`, replace the row-rendering loop (lines 69-91):

```python
    lines_html: list[str] = []
    for row in rows:
        spans: list[str] = []
        i = 0
        while i < len(row):
            r, g, b, c = row[i]
            run = c
            j = i + 1
            while j < len(row):
                r2, g2, b2, c2 = row[j]
                if abs(r2 - r) < 10 and abs(g2 - g) < 10 and abs(b2 - b) < 10:
                    run += c2
                    j += 1
                else:
                    break
            safe = (
                run.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            spans.append(f'<span style="color:rgb({r},{g},{b})">{safe}</span>')
            i = j
        lines_html.append("".join(spans))
```

with:

```python
    lines_html: list[str] = []
    for row in rows:
        if monochrome:
            text = "".join(c for _, _, _, c in row)
            safe = (
                text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            lines_html.append(
                f'<span style="color:{font_color}">{safe}</span>'
            )
            continue
        spans: list[str] = []
        i = 0
        while i < len(row):
            r, g, b, c = row[i]
            run = c
            j = i + 1
            while j < len(row):
                r2, g2, b2, c2 = row[j]
                if abs(r2 - r) < 10 and abs(g2 - g) < 10 and abs(b2 - b) < 10:
                    run += c2
                    j += 1
                else:
                    break
            safe = (
                run.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            spans.append(f'<span style="color:rgb({r},{g},{b})">{safe}</span>')
            i = j
        lines_html.append("".join(spans))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_img2ascii_regression.py -v`
Expected: both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add img2ascii.py tests/test_img2ascii_regression.py
git commit -m "feat: add monochrome rendering to image_to_ascii_html"
```

---

### Task 2: `--invert` flag (ascii + ansi)

**Files:**
- Modify: `image2.py:49` (import), `image2.py:65-78` (`_shared_parser`), `image2.py:295-320` (`main`)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image2.py`:

```python
def test_invert_flag_available_for_both_styles():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--invert"])
    assert args.invert is True
    args = p.parse_args(["ansi", "in.jpg", "--invert"])
    assert args.invert is True


def test_invert_flag_defaults_false():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.invert is False


def test_ansi_invert_changes_output(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out_normal = str(tmp_path / "normal.ans")
    out_inverted = str(tmp_path / "inverted.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_normal, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ansi", src, "-o", out_inverted, "--no-auto", "--invert"],
    )
    image2.main()

    normal = open(out_normal, encoding="utf-8").read()
    inverted = open(out_inverted, encoding="utf-8").read()
    assert normal != inverted
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_image2.py -v -k invert`
Expected: all three FAIL — `test_invert_flag_available_for_both_styles` and
`test_invert_flag_defaults_false` with `AttributeError: 'Namespace' object
has no attribute 'invert'`; `test_ansi_invert_changes_output` with the same
`AttributeError` (raised during `parse_args` inside `main()`).

- [ ] **Step 3: Add the `--invert` flag to the shared parser**

In `image2.py`, in `_shared_parser` (lines 65-78), add after the `--no-gpu` line:

```python
    p.add_argument("--no-gpu", action="store_true", default=False)
    p.add_argument("--invert", action="store_true", default=False)
    return p
```

- [ ] **Step 4: Import ImageOps and apply inversion in `main()`**

In `image2.py`, change line 49 from:

```python
    from PIL import Image
```

to:

```python
    from PIL import Image, ImageOps
```

In `main()` (around lines 304-306), change:

```python
    width = resolve_width(args.style, args.width)
    with Image.open(args.input) as opened:
        img = opened.convert("RGB")
```

to:

```python
    width = resolve_width(args.style, args.width)
    with Image.open(args.input) as opened:
        img = opened.convert("RGB")
    if args.invert:
        img = ImageOps.invert(img)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_image2.py -v -k invert`
Expected: all three PASS.

- [ ] **Step 6: Run the full test suite**

Run: `venv/bin/pytest`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add --invert flag for color inversion"
```

---

### Task 3: `--monochrome` / `--font-color` flags (ascii only)

**Files:**
- Modify: `image2.py:93-103` (`ascii_p` subparser), `image2.py:229-292` (`_render_ascii`)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image2.py`:

```python
def test_monochrome_flags_available_for_ascii():
    p = image2.build_parser()
    args = p.parse_args(
        ["ascii", "in.jpg", "--monochrome", "--font-color", "#00ff00"]
    )
    assert args.monochrome is True
    assert args.font_color == "#00ff00"


def test_monochrome_flags_default():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.monochrome is False
    assert args.font_color is None


def test_monochrome_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(["ansi", "in.jpg", "--monochrome"])


def test_font_color_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(
            ["ansi", "in.jpg", "--font-color", "#00ff00"]
        )


def test_ascii_monochrome_default_color(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--html", "-o", out, "--monochrome"]
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "color:#ffffff" in html
    assert "rgb(" not in html


def test_ascii_font_color_implies_monochrome(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ascii", src, "--html", "-o", out, "--font-color", "#00ff00"],
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "color:#00ff00" in html
    assert "rgb(" not in html


def test_ascii_no_monochrome_uses_per_pixel_color(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--html", "-o", out]
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "rgb(" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_image2.py -v -k "monochrome or font_color"`
Expected: parsing tests FAIL with `AttributeError: 'Namespace' object has no
attribute 'monochrome'` (or `font_color`); the two "rejected under ansi"
tests currently PASS already (no such flags exist yet, so `parse_args`
already raises `SystemExit` for unrecognized args) — that's fine, they'll
keep passing. The end-to-end tests FAIL with the same `AttributeError`
during `main()`.

- [ ] **Step 3: Add `--monochrome` / `--font-color` to the ascii subparser**

In `image2.py`, in the `ascii_p` block (lines 98-103), add two lines:

```python
    ascii_p.add_argument("--html", action="store_true", default=False)
    ascii_p.add_argument("--img-width", type=int, default=None)
    ascii_p.add_argument("--img-height", type=int, default=None)
    ascii_p.add_argument("-b", "--bg", default=None)
    ascii_p.add_argument("--font-size", type=float, default=None)
    ascii_p.add_argument("--select", action="store_true", default=False)
    ascii_p.add_argument("--monochrome", action="store_true", default=False)
    ascii_p.add_argument("--font-color", default=None)
```

- [ ] **Step 4: Resolve monochrome/font_color and pass to `image_to_ascii_html`**

In `_render_ascii` (`image2.py:229-292`), add resolution logic right after
the existing `bg`/`font_size` setup (after line 235):

```python
    bg = args.bg if args.bg is not None else "#000000"
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )
    monochrome = args.monochrome or args.font_color is not None
    font_color = args.font_color or "#ffffff"
```

Then update the `image_to_ascii_html` call (lines 270-284) from:

```python
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
        1.0,
        px_w,
        px_h,
    )
```

to:

```python
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
        1.0,
        px_w,
        px_h,
        monochrome,
        font_color,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_image2.py -v -k "monochrome or font_color"`
Expected: all PASS.

- [ ] **Step 6: Run the full test suite**

Run: `venv/bin/pytest`
Expected: all tests PASS.

- [ ] **Step 7: Lint**

Run: `venv/bin/flake8`
Expected: no output (clean).

- [ ] **Step 8: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add --monochrome and --font-color flags for ascii style"
```
