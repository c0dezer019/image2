# ascii — Unified CLI Design

**Date:** 2026-06-07
**Status:** Approved (design); pending spec review

## Problem

The project ships two separate command-line tools — `img2ansi.py` and
`img2ascii.py` — that share most of their flags and all of their image-prep
pipeline but must be invoked as different modules. A user who wants to switch
render styles has to remember and call a different script. We want one command.

## Goal

A single `ascii` command that renders an image in either style, with one
unified flag surface, while preserving the existing render behavior and test
coverage.

## Decisions (locked)

- **Command:** `ascii`.
- **Style selection:** `--style ascii|ansi`, defaulting to `ascii` when the
  flag is omitted.
- **Invocation:** both `python3 ascii.py <input> ...` (dev, no install) and an
  installed `ascii` console command (`pip install -e .`).
- **Directory rename:** `git mv pico_ansii pico_ascii` (corrects the
  misspelling) as part of this work.
- **Old entrypoints:** hard replace. `img2ansi.py` and `img2ascii.py` lose
  their `main()`/argparse and become pure render libraries. `ascii` is the only
  CLI. `python3 img2ansi.py foo.jpg` no longer runs.
- **Wrong-style flags:** error out (exit 2) with a clear message when a
  style-specific flag is passed under the other style.

> **Rename note:** initial design drafts used `pico`, but implementation ships
> `ascii` to avoid conflicts with the classic nano-predecessor editor binary
> named `pico` on many systems.

## Architecture

After the directory rename, the package is `pico_ascii/` with a flat layout:

| File | Role |
|------|------|
| `imgcommon.py` | Unchanged image-prep helpers (`lift_luminance`, `load_and_enhance`, `resize_for`) **plus** a new shared `write_png_from_html(html, out_path, px_w, px_h, no_gpu)`. |
| `img2ansi.py` | ANSI render backend (library only, no `main()`). |
| `img2ascii.py` | ASCII render backend (library only, no `main()`). |
| `ascii.py` | **New** unified CLI: argument parsing, style/default resolution, prep, dispatch, output writing. |
| `tests/` | Existing pytest suite, unchanged. |

### Component: `imgcommon.write_png_from_html`

Both renderers currently duplicate the same Html2Image sequence (build flags,
`--no-gpu` variants, `screenshot`, `shutil.move` for cross-filesystem output).
Extract it once:

```
write_png_from_html(html: str, out_path: str,
                    px_w: int, px_h: int, no_gpu: bool) -> None
```

- Builds the base Chrome flags (`--hide-scrollbars --no-sandbox
  --disable-setuid-sandbox`), appends the GPU-disable flags when `no_gpu`.
- Handles the missing-`html2image` case (prints the existing hint, returns
  without raising) so a missing optional dep never aborts the `.ans`/`.html`
  that was already written.
- Moves the screenshot to `out_path` with `shutil.move` (cross-filesystem
  safe), as today.

Each caller computes its own `px_w`/`px_h` (the sizing math differs per style)
and passes the result in.

### Component: `img2ansi.py` (backend)

Render functions only. **These tested public symbols stay in this module under
these exact names** (the test suite imports them directly):

- `image_to_ansi(img, mode)`
- `rgb_to_256(r, g, b)`
- `rgb_to_16(r, g, b)`
- `ansi_image_to_html(img, bg_color, font_size)`

Also retained: `_cell_escape`, `PALETTE_16`, `UPPER_HALF`. The module-level
`main()`, argparse, and `_write_png` are removed; PNG writing moves to the
shared helper, called from `ascii.py`.

### Component: `img2ascii.py` (backend)

Render functions only. **These tested public symbols stay in this module:**

- `image_to_ascii_html(...)` — same signature as today.
- `lift_luminance` — must remain importable from this module (re-exported from
  `imgcommon`); a regression test asserts `img2ascii.lift_luminance` exists.

The module-level `main()`, argparse, and inline Html2Image block are removed.
`ascii_chars` stays.

### Component: `ascii.py` (the CLI)

One `argparse` parser with all flags. Flow:

1. Parse args.
2. Resolve `--style` (default `ascii`).
3. **Validate cross-style flags** — if an ansi-only flag is set while style is
   ascii (or vice versa), print `error: <flag> requires --style <other>` and
   exit 2.
4. Resolve style-divergent defaults (see table below).
5. Run `imgcommon.load_and_enhance` + `imgcommon.resize_for`
   (`cell_aspect` `1.0` for ansi, `0.48`-equivalent handling for ascii) +
   optional `lift_luminance`, matching each renderer's current pipeline.
6. Dispatch to the chosen backend, then write outputs.

Note: the ascii path currently performs its enhancement and resize *inside*
`image_to_ascii_html`. To keep that tested function's behavior identical, the
ascii dispatch calls it as-is (passing the raw `Image.open` result and params),
rather than pre-running the shared prep. The ansi path uses the shared
`load_and_enhance` + `resize_for` as `img2ansi.main` does today. `ascii.py`
absorbs the per-style orchestration that the deleted `main()`s used to do.

## Flag surface

### Shared (both styles)

`input` (positional) · `-o/--output` · `-w/--width` · `-c/--contrast` ·
`-s/--sharpness` · `-B/--brightness` · `--saturate` · `--min-lum` ·
`--no-gpu` · `-h/--help` · `--style {ascii,ansi}`

### ansi-only

`--mode {truecolor,256,bbs16}` · `--png`

### ascii-only

`--html` · `--img-width` · `--img-height` · `-b/--bg` · `--font-size` ·
`--select`

### Style-divergent defaults

| Concern | ascii | ansi |
|---------|-------|------|
| `--width` default | 350 | 80 |
| default output | `<input>_ascii.png` (or `.html` with `--html`) | `<input>_ansi.ans` (+ `<input>_ansi.png` with `--png`) |
| `--font-size` default | 4.0 (HTML) / 6.5 (PNG) | n/a (fixed 8.0 internally) |

`--width` parses as `None` and resolves to the style default after `--style`
is known.

## Cross-style flag validation

Given default style is `ascii`, the common mistake is passing an ansi flag
without `--style ansi`:

```
$ ascii in.jpg --mode 256
error: --mode requires --style ansi
[exit 2]
```

Implementation: after resolving style, check the set of flags that belong to
the *other* style against their parsed values (non-default / explicitly set).
If any was provided, emit `error: <flag> requires --style <other-style>` and
`sys.exit(2)`. `--no-gpu` is shared (applies to both PNG paths) and is exempt.

## Packaging

`pyproject.toml` gains, alongside the existing `[tool.black]`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "pico-ascii"
version = "0.1.0"
requires-python = ">=3.14"
dependencies = ["Pillow"]
# html2image is optional (PNG only) — kept in requirements.txt, not a hard dep.

[project.scripts]
ascii = "ascii:main"

[tool.setuptools]
py-modules = ["ascii", "img2ansi", "img2ascii", "imgcommon"]
```

Flat layout (no `src/` restructure). `pip install -e .` exposes `ascii` on
PATH; `python3 ascii.py` works without installing.

## Documentation

`README.md` currently documents `python3 img2ansi.py ...` and
`python3 img2ascii.py ...` throughout (title, layout table, usage, examples).
Rewrite it to document the single `ascii` command, `--style`, the unified flag
table, and the new install/invocation. This is in scope for this change, not a
follow-up — the old invocations stop working.

## Testing

- The existing 19-test suite must pass unchanged. Tests import `img2ansi` and
  `img2ascii` by module name and call public functions directly; keeping those
  symbols in place (per the constraints above) preserves coverage.
- New tests for `ascii.py`:
  - `--style` default resolves to `ascii`.
  - `--width` resolves to 350 (ascii) / 80 (ansi) when omitted.
  - Cross-style flag misuse exits 2 with the expected message
    (`--mode` under ascii; an ascii-only flag under ansi).
  - Output path/extension resolution per style.
- New test for `imgcommon.write_png_from_html`: missing-`html2image` path
  returns without raising (mock the import).

## Out of scope

- No change to render algorithms, palettes, or output appearance.
- No new render styles.
- No `src/` layout migration beyond what packaging requires.
