# --min/dense ascii rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an ascii-only `--min` flag that caps render width to 100 and
font-size to 8 (PNG) / 2.0 (HTML), for a quick low-detail render. "Dense"
is the existing default — no flag, no behavior change when `--min` is
absent.

**Architecture:** A pure helper `apply_min_cap(value, cap, enabled)` in
`image2.py` does the clamping (`min(value, cap)` if enabled, else
passthrough). `_render_ascii` calls it once for `font_size` (right after
font_size is resolved) and once for `width` (right after the
`args.width is None` auto-compute block). `--min` is added only to the
`ascii` subparser, so `img2 ansi ... --min` is a normal argparse error.

**Tech Stack:** Python 3, argparse, pytest.

---

### Task 1: Add `--min` argparse flag and docstring entry

**Files:**
- Modify: `image2.py:34` (docstring, ascii-only section)
- Modify: `image2.py:116` (ascii_p argument registration)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image2.py` near `test_ascii_only_flags_available_under_ascii`:

```python
def test_min_flag_available_under_ascii():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--min"])
    assert args.min is True


def test_min_flag_defaults_false():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.min is False


def test_min_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(["ansi", "in.jpg", "--min"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_image2.py -k min_flag -v`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'min'`
(first two tests); third test fails because `--min` is not yet
ansi-rejected (it doesn't exist at all, so `SystemExit` IS raised —
this one passes by accident). Confirm the first two fail.

- [ ] **Step 3: Add the flag and docstring entry**

In `image2.py`, in the `ascii-only:` docstring block (around line 34,
after the `--font-color` line), add:

```
    --min             Cap width to 100 and font-size to 8 (PNG) /
                      2.0 (HTML) for a quick, low-detail render
                      (default: off, "dense" mode)
```

In `image2.py`, after the `ascii_p.add_argument("--font-color", ...)`
line (around line 116), add:

```python
    ascii_p.add_argument("--min", action="store_true", default=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_image2.py -k min_flag -v`
Expected: PASS (all 3)

- [ ] **Step 5: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add --min flag for ascii style"
```

---

### Task 2: Add `apply_min_cap` helper with unit tests

**Files:**
- Modify: `image2.py` (near `resolve_width`, around line 137)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image2.py`:

```python
def test_apply_min_cap_disabled_passes_through():
    assert image2.apply_min_cap(350, 100, False) == 350
    assert image2.apply_min_cap(13, 8, False) == 13


def test_apply_min_cap_clamps_when_enabled():
    assert image2.apply_min_cap(350, 100, True) == 100
    assert image2.apply_min_cap(13, 8, True) == 8


def test_apply_min_cap_does_not_raise_below_cap():
    assert image2.apply_min_cap(50, 100, True) == 50
    assert image2.apply_min_cap(2.0, 8, True) == 2.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_image2.py -k apply_min_cap -v`
Expected: FAIL with `AttributeError: module 'image2' has no attribute
'apply_min_cap'`

- [ ] **Step 3: Implement the helper**

In `image2.py`, after `resolve_width` (around line 137), add:

```python
def apply_min_cap(value, cap, enabled):
    """Clamp value to cap (only lowers, never raises) when enabled."""
    return min(value, cap) if enabled else value
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_image2.py -k apply_min_cap -v`
Expected: PASS (all 3)

- [ ] **Step 5: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add apply_min_cap helper for --min clamping"
```

---

### Task 3: Wire `--min` into `_render_ascii`

**Files:**
- Modify: `image2.py:245-249` (font_size resolution)
- Modify: `image2.py:274-275` (width resolution)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing integration test**

Add to `tests/test_image2.py` (uses `_tiny_image` and
`_tiny_pil_image`/monkeypatch helpers already present in the file):

```python
def test_min_flag_caps_width_and_font_size_html(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")

    captured = {}

    def fake_image_to_ascii_html(img, width, *args, **kwargs):
        captured["width"] = width
        captured["font_size"] = args[6]
        return "<pre></pre>"

    monkeypatch.setattr(
        image2.img2ascii, "image_to_ascii_html", fake_image_to_ascii_html
    )
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--html", "--min", "-o", out]
    )
    image2.main()

    assert captured["width"] <= 100
    assert captured["font_size"] == 2.0


def test_min_flag_caps_width_png(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.png")

    captured = {}

    def fake_build_ascii_grid(img, width, *args, **kwargs):
        captured["width"] = width
        return [["#" for _ in range(1)]]

    def fake_ascii_grid_to_svg(grid, font_size, *args, **kwargs):
        captured["font_size"] = font_size
        return "<svg></svg>"

    monkeypatch.setattr(image2, "build_ascii_grid", fake_build_ascii_grid)
    monkeypatch.setattr(image2, "ascii_grid_to_svg", fake_ascii_grid_to_svg)
    monkeypatch.setattr(image2, "render_svg_to_png", lambda svg, path: None)
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--min", "-o", out]
    )
    image2.main()

    assert captured["width"] <= 100
    assert captured["font_size"] <= 8


def test_min_flag_does_not_raise_explicit_small_width(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.png")

    captured = {}

    def fake_build_ascii_grid(img, width, *args, **kwargs):
        captured["width"] = width
        return [["#" for _ in range(1)]]

    monkeypatch.setattr(image2, "build_ascii_grid", fake_build_ascii_grid)
    monkeypatch.setattr(
        image2, "ascii_grid_to_svg", lambda *a, **k: "<svg></svg>"
    )
    monkeypatch.setattr(image2, "render_svg_to_png", lambda svg, path: None)
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--min", "-w", "50", "-o", out]
    )
    image2.main()

    assert captured["width"] == 50
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_image2.py -k min_flag_caps -v` and
`.venv/bin/pytest tests/test_image2.py -k does_not_raise -v`
Expected: FAIL — `captured["width"]` will be 350 (or whatever the
unclamped default/auto value is) and `captured["font_size"]` will be
4.0/13, since `--min` isn't wired up yet.

- [ ] **Step 3: Wire the clamps into `_render_ascii`**

In `image2.py`, the existing font_size resolution block reads:

```python
    bg = args.bg if args.bg is not None else "#000000"
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )
```

Change to:

```python
    bg = args.bg if args.bg is not None else "#000000"
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )
    font_size = apply_min_cap(
        font_size, 2.0 if args.html else 8, args.min
    )
```

The existing width resolution block reads:

```python
    if args.width is None:
        width = max(1, int((px_w - 2) / char_width_px))
```

Change to:

```python
    if args.width is None:
        width = max(1, int((px_w - 2) / char_width_px))
    width = apply_min_cap(width, 100, args.min)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_image2.py -v`
Expected: PASS (full file, no regressions)

- [ ] **Step 5: Lint**

Run: `.venv/bin/flake8 image2.py tests/test_image2.py`
Expected: no output

- [ ] **Step 6: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: wire --min into ascii width/font-size resolution"
```

---

## Manual smoke test (optional, after Task 3)

```bash
.venv/bin/python -m image2 ascii tests/fixtures/<some image> --min -o /tmp/min.png
.venv/bin/python -m image2 ascii tests/fixtures/<some image> --min --html -o /tmp/min.html
grep 'font-size: 2.0px' /tmp/min.html
```
(Skip if no fixture image is available — the automated tests cover this.)
