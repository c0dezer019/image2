# Gaussian Blur Preprocessing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `--blur RADIUS` flag (shared by `ascii` and `ansi`) that applies a Gaussian blur to the source image before auto-param detection and rendering, to reduce noise.

**Architecture:** Single new CLI flag on the shared argparse parent parser in `image2.py`. Default `0.0` (no-op). When `> 0`, `main()` applies `img.filter(ImageFilter.GaussianBlur(radius=args.blur))` right after the existing `--invert` step and before `resolve_enhance_params` / resize / enhance.

**Tech Stack:** Python, argparse, Pillow (`PIL.ImageFilter.GaussianBlur`), pytest.

---

### Task 1: Add `--blur` CLI flag

**Files:**
- Modify: `image2.py:72-86` (`_shared_parser`)
- Modify: `image2.py:1-41` (module docstring, shared options section)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image2.py` (near the other `--invert` flag tests around line 169):

```python
def test_blur_flag_defaults_zero():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.blur == 0.0


def test_blur_flag_available_for_both_styles():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--blur", "1.5"])
    assert args.blur == 1.5
    args = p.parse_args(["ansi", "in.jpg", "--blur", "1.5"])
    assert args.blur == 1.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_image2.py -k blur_flag -v`
Expected: FAIL with `AttributeError: 'Namespace' object has no attribute 'blur'`

- [ ] **Step 3: Implement the flag**

In `image2.py`, inside `_shared_parser()` (around line 85, after the `--invert` argument), add:

```python
    p.add_argument("--invert", action="store_true", default=False)
    p.add_argument("--blur", type=float, default=0.0)
    return p
```

Also update the module docstring's "Shared options" section (around line 24-25, after the `--invert` line) to document the new flag:

```
    --invert          Invert source image colors before rendering
    --blur            Gaussian blur radius applied before processing
                      (default: 0.0, disabled)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_image2.py -k blur_flag -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: add --blur CLI flag"
```

---

### Task 2: Apply Gaussian blur in the processing pipeline

**Files:**
- Modify: `image2.py:53` (PIL imports)
- Modify: `image2.py:323-351` (`main()`)
- Test: `tests/test_image2.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_image2.py`. This needs a noisy source image (a flat-color image is unchanged by Gaussian blur, so it wouldn't exercise the filter). Add a new helper near `_tiny_image` (around line 56-60):

```python
def _noisy_image(tmp_path):
    import random

    path = tmp_path / "noisy.png"
    img = Image.new("RGB", (8, 8))
    rng = random.Random(0)
    for y in range(8):
        for x in range(8):
            img.putpixel(
                (x, y),
                (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)),
            )
    img.save(path)
    return str(path)
```

Then add the behavior test near `test_ansi_invert_changes_output` (around line 195):

```python
def test_ansi_blur_changes_output(tmp_path, monkeypatch):
    src = _noisy_image(tmp_path)
    out_normal = str(tmp_path / "normal.ans")
    out_blurred = str(tmp_path / "blurred.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_normal, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ansi", src, "-o", out_blurred, "--no-auto", "--blur", "2.0"],
    )
    image2.main()

    normal = open(out_normal, encoding="utf-8").read()
    blurred = open(out_blurred, encoding="utf-8").read()
    assert normal != blurred


def test_ansi_blur_zero_is_noop(tmp_path, monkeypatch):
    src = _noisy_image(tmp_path)
    out_default = str(tmp_path / "default.ans")
    out_explicit_zero = str(tmp_path / "explicit_zero.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_default, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ansi", src, "-o", out_explicit_zero, "--no-auto", "--blur", "0"],
    )
    image2.main()

    default = open(out_default, encoding="utf-8").read()
    explicit_zero = open(out_explicit_zero, encoding="utf-8").read()
    assert default == explicit_zero
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv/bin/pytest tests/test_image2.py -k blur -v`
Expected: `test_ansi_blur_changes_output` FAILS (`normal == blurred`, blur not applied yet). `test_ansi_blur_zero_is_noop` and the Task 1 flag tests PASS already.

- [ ] **Step 3: Implement the blur step**

In `image2.py`, update the PIL import (line 53):

```python
from PIL import Image, ImageFilter, ImageOps
```

In `main()` (around line 335-337), add the blur step immediately after the `--invert` block:

```python
    if args.invert:
        img = ImageOps.invert(img)

    if args.blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=args.blur))

    args.contrast, args.brightness, args.saturate, args.min_lum = (
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_image2.py -k blur -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Run full test suite**

Run: `.venv/bin/pytest`
Expected: all tests pass

- [ ] **Step 6: Lint**

Run: `.venv/bin/flake8 image2.py tests/test_image2.py`
Expected: no output (clean)

- [ ] **Step 7: Commit**

```bash
git add image2.py tests/test_image2.py
git commit -m "feat: apply gaussian blur preprocessing via --blur"
```
