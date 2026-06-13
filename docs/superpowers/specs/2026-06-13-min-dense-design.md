# --min / dense ascii rendering design

## Problem

`ascii` style defaults to a large width (350 cols) and font-size (13px
PNG / 4.0px HTML), producing dense, high-detail output. Users sometimes
want a quick, low-detail render: smaller width and font-size, faster
generation.

## Design

Add `--min` flag, ascii-only, `action="store_true"`, default `False`.

"Dense" is the existing default behavior — no new flag, no code change
for it.

### Behavior when `--min` is set

After width and font-size are resolved through existing logic
(explicit `-w`/`--font-size`, or defaults, or `--img-width`/
`--img-height`-derived auto width), clamp:

- `width = min(width, 100)`
- `font_size = min(font_size, 8)` for PNG output
- `font_size = min(font_size, 2.0)` for HTML output

Clamping happens last, after all existing resolution logic (including
the `args.width is None` auto-compute branch in `_render_ascii`). `--min`
only ever lowers values — if the resolved width/font-size is already
≤ the cap, `--min` has no effect.

### Scope

`--min` is added only to `ascii_p` (the `ascii` subparser). Passing
`--min` with `ansi` is a normal argparse error ("unrecognized
arguments"), same as any other ascii-only flag.

### Docstring

Add `--min` to the `ascii-only:` section of the module docstring in
`image2.py`:

```
    --min             Cap width to 100 and font-size to 8 (PNG) /
                      2.0 (HTML) for a quick, low-detail render
                      (default: off, "dense" mode)
```

## Implementation notes

- `_render_ascii` already computes final `width` (possibly via the
  `args.width is None` auto branch) and `font_size` before building the
  grid/SVG. Clamp both immediately after those computations, gated on
  `args.min`.
- No changes to `imgcommon.py`, `img2ascii.py`, `imgsvg.py`, or `ansi`
  path.

## Testing

- `tests/`: add a test asserting that with `--min` and no explicit
  `-w`/`--font-size`, resolved width ≤ 100 and font_size ≤ 8 (PNG) / 2.0
  (HTML).
- Add a test asserting `--min` with explicit `-w 50` keeps width 50
  (cap only lowers, doesn't raise).
- Add a test asserting `--min` with explicit `-w 200` clamps to 100.
