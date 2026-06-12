# Re-port invert/monochrome onto SVG architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `origin/main` (PR #15's html2image→cairosvg/SVG rewrite) into `13-feature-change-font-color`, then re-implement `--invert` and `--monochrome`/`--font-color` against the new `build_ascii_grid`/`imgsvg` architecture, covering both the `--html` output path (`img2ascii.image_to_ascii_html`) and the default PNG path (`imgsvg.ascii_grid_to_svg`).

**Architecture:** Merge first (only `image2.py` and `img2ascii.py` conflict — confirmed via `git diff` against the merge-base, every other file is single-sided). Resolve both conflicted files by taking `origin/main`'s version wholesale, restoring a clean green baseline on the new architecture. Then re-apply `--invert` (image-level, unchanged), monochrome support in `image_to_ascii_html` (HTML path, same row shape as before), and new monochrome support in `imgsvg.ascii_grid_to_svg` (PNG path, the part that didn't exist before).

**Tech Stack:** Python 3.14, Pillow, cairosvg (new dependency from main), pytest, argparse.

---

## Reference: design spec

See `docs/superpowers/specs/2026-06-11-font-color-invert-report-design.md` for full rationale. Key facts this plan relies on:

- `imgcommon.build_ascii_grid(img, width, contrast, sharpness, brightness, min_lum, saturate) -> list[list[tuple[int,int,int,str]]]` — rows of `(r, g, b, ascii_char)`.
- `img2ascii.image_to_ascii_html(img, width, contrast, sharpness, brightness, min_lum, saturate, bg_color, font_size, auto_select, text_scale, px_w=0, px_h=0)` — now delegates grid-building to `build_ascii_grid`.
- `imgsvg.ascii_grid_to_svg(grid, font_size, bg_color, px_w, px_h, auto_select=False) -> str` — one `<text>` per row, one `<tspan fill="rgb(...)">` per color-run via `imgsvg.merge_runs`.
- `image2._render_ascii`: `--html` → `image_to_ascii_html`; default (PNG) → `build_ascii_grid` + `ascii_grid_to_svg` + `render_svg_to_png`.

---

### Task 1: Merge `origin/main` and restore a green baseline

**Files:**
- Merge: entire repo (conflicts expected only in `image2.py`, `img2ascii.py`)

- [ ] **Step 1: Fetch and start the merge**

```bash
git fetch origin
git merge origin/main
```

Expected: merge stops with conflicts in exactly two files:
```
CONFLICT (content): Merge conflict in image2.py
CONFLICT (content): Merge conflict in img2ascii.py
Automatic merge failed; fix conflicts and then commit the result.
```
All other files (`imgcommon.py`, `imgsvg.py`, `img2ansi.py`, `tests/test_imgcommon.py`, `tests/test_img2ansi.py`, `tests/test_imgsvg.py`, `tests/test_image2.py`, `tests/test_img2ascii_regression.py`, `pyproject.toml`, `requirements*.txt`, `pylock.toml`, `.flake8`, `CLAUDE.md`, `README.md`, `.gitignore`) auto-merge cleanly — leave them as merged.

- [ ] **Step 2: Resolve `image2.py` and `img2ascii.py` by taking main's version**

These two files were independently rewritten by both sides (our monochrome/invert additions vs. main's SVG rewrite). Take main's version wholesale here — Tasks 2-5 re-apply our additions on top of it deliberately, avoiding a Frankenstein auto-merge.

```bash
git checkout --theirs image2.py img2ascii.py
git add image2.py img2ascii.py
```

- [ ] **Step 3: Commit the merge**

```bash
git commit -m "$(cat <<'EOF'
Merge origin/main into 13-feature-change-font-color

Resolves image2.py and img2ascii.py conflicts by taking main's
SVG-based rewrite (PR #15) wholesale. --invert and
--monochrome/--font-color are re-applied on top in subsequent commits,
covering both the --html and PNG (imgsvg) output paths.
EOF
)"
```

- [ ] **Step 4: Install updated dependencies**

Main added `cairosvg` as a dependency and dropped `html2image`. Reinstall the package so the venv matches `pyproject.toml`:

```bash
.venv/bin/pip install -e .
```

- [ ] **Step 5: Run the full test suite to confirm the merged baseline is green (minus the not-yet-reimplemented features)**

```bash
.venv/bin/pytest -q
```

Expected: most tests pass. The following will FAIL — this is expected, they're re-implemented in Tasks 2-5:
- `tests/test_image2.py::test_invert_flag_available_for_both_styles`
- `tests/test_image2.py::test_invert_flag_defaults_false`
- `tests/test_image2.py::test_ansi_invert_changes_output`
- `tests/test_image2.py::test_monochrome_flags_available_for_ascii`
- `tests/test_image2.py::test_monochrome_flags_default`
- `tests/test_image2.py::test_monochrome_flag_rejected_under_ansi`
- `tests/test_image2.py::test_font_color_flag_rejected_under_ansi`
- `tests/test_image2.py::test_ascii_monochrome_default_color`
- `tests/test_image2.py::test_ascii_font_color_implies_monochrome`
- `tests/test_image2.py::test_ascii_no_monochrome_uses_per_pixel_color`
- `tests/test_img2ascii_regression.py::test_image_to_ascii_html_monochrome_uses_font_color`
- `tests/test_img2ascii_regression.py::test_image_to_ascii_html_default_not_monochrome`

(`test_ascii_no_monochrome_uses_per_pixel_color` and
`test_image_to_ascii_html_default_not_monochrome` may currently pass by
coincidence since `rgb(` is already present without monochrome — verify
either way, they must pass after Task 3/4 regardless.)

Do not proceed to Task 2 until the failure set matches the above (no
unrelated failures from the merge).

---

### Task 2: Re-port `--invert`

**Files:**
- Modify: `image2.py`
- Test: `tests/test_image2.py` (tests already present from the merge)

- [ ] **Step 1: Run the invert tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_image2.py -k invert -v
```

Expected: 3 FAILs —
- `test_invert_flag_available_for_both_styles` — `AttributeError: 'Namespace' object has no attribute 'invert'`
- `test_invert_flag_defaults_false` — same
- `test_ansi_invert_changes_output` — same (raised inside `image2.main()`)

- [ ] **Step 2: Add `ImageOps` import**

In `image2.py`, change:

```python
try:
    from PIL import Image
except ImportError:
```

to:

```python
try:
    from PIL import Image, ImageOps
except ImportError:
```

- [ ] **Step 3: Add `--invert` to `_shared_parser`**

In `_shared_parser()`, after `p.add_argument("--no-gpu", action="store_true", default=False)`, add:

```python
    p.add_argument("--invert", action="store_true", default=False)
```

- [ ] **Step 4: Apply invert in `main()`**

In `main()`, after:

```python
    with Image.open(args.input) as opened:
        img = opened.convert("RGB")
```

add:

```python
    if args.invert:
        img = ImageOps.invert(img)
```

(this must be *before* `resolve_enhance_params`, so auto-detected enhancement params are computed on the inverted image — matches the original implementation).

- [ ] **Step 5: Add `--invert` to the module docstring**

In the module docstring's `Shared options:` block, after the `--no-gpu` line:

```
    --no-gpu          Deprecated, ignored (no-op; PNG output no longer
                      uses a GPU-backed renderer)
```

add:

```
    --invert          Invert source image colors before rendering
```

- [ ] **Step 6: Run the invert tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_image2.py -k invert -v
```

Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add image2.py
git commit -m "feat: re-add --invert flag onto SVG-based architecture"
```

---

### Task 3: Re-port monochrome rendering in `img2ascii.image_to_ascii_html` (--html path)

**Files:**
- Modify: `img2ascii.py`
- Test: `tests/test_img2ascii_regression.py` (tests already present from the merge)

- [ ] **Step 1: Run the monochrome regression tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_img2ascii_regression.py -v
```

Expected: `test_image_to_ascii_html_monochrome_uses_font_color` FAILs with
`TypeError: image_to_ascii_html() got an unexpected keyword argument 'monochrome'`.
`test_image_to_ascii_html_default_not_monochrome` and
`test_image_to_ascii_html_stable_output` should already PASS (no
monochrome kwargs passed) — confirm this.

- [ ] **Step 2: Add `monochrome`/`font_color` params to `image_to_ascii_html`**

In `img2ascii.py`, the signature currently ends:

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

Add two trailing params:

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

- [ ] **Step 3: Add the monochrome row-rendering branch**

In `image_to_ascii_html`, the row loop currently starts:

```python
    lines_html: list[str] = []
    for row in rows:
        spans: list[str] = []
        i = 0
        while i < len(row):
```

Add a monochrome branch before the per-run logic:

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
```

- [ ] **Step 4: Run the regression tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_img2ascii_regression.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add img2ascii.py
git commit -m "feat: re-add monochrome rendering to image_to_ascii_html"
```

---

### Task 4: Wire `--monochrome`/`--font-color` CLI flags through the --html path

**Files:**
- Modify: `image2.py`
- Test: `tests/test_image2.py` (tests already present from the merge)

- [ ] **Step 1: Run the monochrome CLI tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_image2.py -k "monochrome or font_color" -v
```

Expected: all FAIL —
- `test_monochrome_flags_available_for_ascii`, `test_monochrome_flags_default` — `argparse.ArgumentError`/`AttributeError` (no `--monochrome`/`--font-color`)
- `test_monochrome_flag_rejected_under_ansi`, `test_font_color_flag_rejected_under_ansi` — these expect `SystemExit` from argparse rejecting an unknown flag under `ansi`; argparse already raises `SystemExit` for unrecognized arguments, so these may already PASS. Verify and note actual result.
- `test_ascii_monochrome_default_color`, `test_ascii_font_color_implies_monochrome` — `AttributeError: 'Namespace' object has no attribute 'monochrome'` raised inside `image2.main()`
- `test_ascii_no_monochrome_uses_per_pixel_color` — should already PASS (no flags involved); confirm.

- [ ] **Step 2: Add `--monochrome`/`--font-color` to `ascii_p`**

In `build_parser()`, after:

```python
    ascii_p.add_argument("--select", action="store_true", default=False)
```

add:

```python
    ascii_p.add_argument("--monochrome", action="store_true", default=False)
    ascii_p.add_argument("--font-color", default=None)
```

- [ ] **Step 3: Compute `monochrome`/`font_color` in `_render_ascii`**

In `_render_ascii`, after:

```python
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )
```

add:

```python
    monochrome = args.monochrome or args.font_color is not None
    font_color = args.font_color or "#ffffff"
```

- [ ] **Step 4: Pass `monochrome`/`font_color` to `image_to_ascii_html` (the `--html` branch)**

In `_render_ascii`'s `if args.html:` branch, the call to `image_to_ascii_html` currently ends:

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

Add the two new trailing args:

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

- [ ] **Step 5: Add `--monochrome`/`--font-color` to the module docstring**

In the module docstring's `ascii-only:` block, after the `--select` line:

```
    --select          Auto-highlight the text
```

add:

```
    --monochrome      Render all glyphs in a single solid color
    --font-color      Solid font color (implies --monochrome,
                      default #ffffff)
```

- [ ] **Step 6: Run the monochrome CLI tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_image2.py -k "monochrome or font_color" -v
```

Expected: all PASS.

- [ ] **Step 7: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: only the PNG-path monochrome support (Task 5, not yet implemented) is missing — no test currently exercises `ascii_grid_to_svg` monochrome, so the full suite should be all-PASS at this point.

- [ ] **Step 8: Commit**

```bash
git add image2.py
git commit -m "feat: wire --monochrome/--font-color through the --html path"
```

---

### Task 5: Add monochrome support to `imgsvg.ascii_grid_to_svg` (default PNG path)

**Files:**
- Modify: `imgsvg.py`
- Modify: `image2.py`
- Test: `tests/test_imgsvg.py`

This is the load-bearing path: `img2 ascii foo.jpg --monochrome` (no `--html`) goes through `ascii_grid_to_svg`, not `image_to_ascii_html`. Without this task, `--monochrome` silently does nothing for the default output.

- [ ] **Step 1: Write the failing test**

In `tests/test_imgsvg.py`, the file already has an `_ascii_grid()` helper:

```python
def _ascii_grid():
    # row: (0,0,0)/'a' and (5,5,5)/'b' merge (diff 5 < 10), (100,100,100)/'c'
    # breaks the run.
    return [
        [(0, 0, 0, "a"), (5, 5, 5, "b"), (100, 100, 100, "c")],
    ]
```

Add new tests after `test_ascii_grid_to_svg_text_and_tspan_runs` (in the `# ascii_grid_to_svg` section):

```python
def test_ascii_grid_to_svg_monochrome_uses_single_fill():
    svg = imgsvg.ascii_grid_to_svg(
        _ascii_grid(),
        font_size=10,
        bg_color="#000000",
        px_w=18,
        px_h=8,
        monochrome=True,
        font_color="#00ff00",
    )
    root = ET.fromstring(svg)

    texts = root.findall(f"{SVG_NS}text")
    assert len(texts) == 1
    assert texts[0].get("fill") == "#00ff00"
    assert texts[0].text == "abc"

    tspans = texts[0].findall(f"{SVG_NS}tspan")
    assert tspans == []
    assert "rgb(" not in svg


def test_ascii_grid_to_svg_default_uses_per_run_tspans():
    svg = imgsvg.ascii_grid_to_svg(
        _ascii_grid(), font_size=10, bg_color="#000000", px_w=18, px_h=8
    )
    root = ET.fromstring(svg)

    texts = root.findall(f"{SVG_NS}text")
    assert texts[0].get("fill") is None
    assert "rgb(" in svg
```

- [ ] **Step 2: Run the new tests to confirm they fail**

```bash
.venv/bin/pytest tests/test_imgsvg.py -k monochrome -v
```

Expected: `test_ascii_grid_to_svg_monochrome_uses_single_fill` FAILs with
`TypeError: ascii_grid_to_svg() got an unexpected keyword argument 'monochrome'`.
`test_ascii_grid_to_svg_default_uses_per_run_tspans` should already PASS
(it doesn't use the new kwargs) — confirm.

- [ ] **Step 3: Add `monochrome`/`font_color` params and branch to `ascii_grid_to_svg`**

In `imgsvg.py`, the signature currently is:

```python
def ascii_grid_to_svg(
    grid: list[list[tuple[int, int, int, str]]],
    font_size: float,
    bg_color: str,
    px_w: int,
    px_h: int,
    auto_select: bool = False,
) -> str:
```

Change to:

```python
def ascii_grid_to_svg(
    grid: list[list[tuple[int, int, int, str]]],
    font_size: float,
    bg_color: str,
    px_w: int,
    px_h: int,
    auto_select: bool = False,
    monochrome: bool = False,
    font_color: str = "#ffffff",
) -> str:
```

Update the docstring `Args:` section by adding, after `auto_select`:

```
        monochrome: If True, render every glyph in ``font_color`` as a
            single ``<text fill="...">`` per row instead of per-run
            ``<tspan fill="rgb(...)">`` elements.
        font_color: CSS color used for glyphs when ``monochrome`` is True.
```

The row-rendering loop currently is:

```python
    text_els: list[str] = []
    for row_idx, row in enumerate(grid):
        colors = [(r, g, b) for r, g, b, _ in row]
        runs = merge_runs(colors)
        y = (row_idx + 1) * cell_h - baseline_offset
        tspans: list[str] = []
        for r, g, b, start, length in runs:
            text = "".join(ch for _, _, _, ch in row[start:start + length])
            tspans.append(
                f'<tspan fill="rgb({r},{g},{b})">{sx.escape(text)}</tspan>'
            )
        text_els.append(
            f'<text x="0" y="{y}" xml:space="preserve">{"".join(tspans)}</text>'
        )
```

Change to:

```python
    text_els: list[str] = []
    for row_idx, row in enumerate(grid):
        y = (row_idx + 1) * cell_h - baseline_offset
        if monochrome:
            text = "".join(ch for _, _, _, ch in row)
            text_els.append(
                f'<text x="0" y="{y}" xml:space="preserve" '
                f'fill="{font_color}">{sx.escape(text)}</text>'
            )
            continue
        colors = [(r, g, b) for r, g, b, _ in row]
        runs = merge_runs(colors)
        tspans: list[str] = []
        for r, g, b, start, length in runs:
            text = "".join(ch for _, _, _, ch in row[start:start + length])
            tspans.append(
                f'<tspan fill="rgb({r},{g},{b})">{sx.escape(text)}</tspan>'
            )
        text_els.append(
            f'<text x="0" y="{y}" xml:space="preserve">{"".join(tspans)}</text>'
        )
```

- [ ] **Step 4: Run the new tests to confirm they pass**

```bash
.venv/bin/pytest tests/test_imgsvg.py -k monochrome -v
```

Expected: both PASS.

- [ ] **Step 5: Wire `monochrome`/`font_color` into the PNG branch of `_render_ascii`**

In `image2.py`'s `_render_ascii`, the PNG (`else:`) branch currently is:

```python
    else:
        print("Generating the ASCII grid...")
        grid = build_ascii_grid(
            img,
            width,
            args.contrast,
            args.sharpness,
            args.brightness,
            args.min_lum,
            args.saturate,
        )
        svg = ascii_grid_to_svg(grid, font_size, bg, px_w, px_h, args.select)
        render_svg_to_png(svg, output_path)
```

Change the `ascii_grid_to_svg` call to:

```python
        svg = ascii_grid_to_svg(
            grid, font_size, bg, px_w, px_h, args.select,
            monochrome, font_color,
        )
```

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/pytest -q
```

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add imgsvg.py image2.py tests/test_imgsvg.py
git commit -m "feat: add monochrome rendering to ascii_grid_to_svg (PNG path)"
```

---

### Task 6: Lint, push, verify PR mergeability

**Files:**
- None (verification only)

- [ ] **Step 1: Run flake8**

```bash
.venv/bin/flake8 image2.py img2ascii.py imgsvg.py
```

Expected: no output (clean). Fix any line-length (79 char) or style issues introduced by the edits above before proceeding.

- [ ] **Step 2: Run the full test suite one more time**

```bash
.venv/bin/pytest -q
```

Expected: all PASS.

- [ ] **Step 3: Push the branch**

```bash
git push origin 13-feature-change-font-color
```

- [ ] **Step 4: Verify PR #16 is mergeable**

```bash
gh pr view 16 --json mergeable,mergeStateStatus
```

Expected: `"mergeable": "MERGEABLE"`, `"mergeStateStatus": "CLEAN"` (or `"UNSTABLE"`/`"BLOCKED"` if CI is still running — re-check after CI completes).

---

## Self-review notes

- **Spec coverage:** Feature 1 (`--invert`) → Task 2. Feature 2 CLI/`image_to_ascii_html` → Tasks 3-4. Feature 2 `ascii_grid_to_svg` → Task 5. Git mechanics → Task 1. Testing → Tasks 2-5 (existing tests reactivated, one new pair added in Task 5).
- **Type consistency:** `monochrome: bool = False, font_color: str = "#ffffff"` trailing-param convention is identical across `image_to_ascii_html` (Task 3) and `ascii_grid_to_svg` (Task 5); `_render_ascii` computes them once (Task 4 Step 3) and passes the same two local variables to both call sites (Task 4 Step 4, Task 5 Step 5).
- **No placeholders:** every code step shows exact before/after text from the current `origin/main` file contents (verified via `git show origin/main:<file>` during design).
