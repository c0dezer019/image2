#!/usr/bin/env python3
# flake8: noqa: E501
"""imgsvg.py — build SVG art from pixel grids and rasterize to PNG.

Replaces the old html2image (headless Chromium) PNG path. Two grid shapes
are supported:

- ascii: ``list[list[(r, g, b, char)]]`` -> one ``<text>`` per row, one
  ``<tspan>`` per color-run.
- ansi half-block: ``list[list[((tr,tg,tb), (br,bg,bb))]]`` -> two ``<rect>``
  per color-run (top half / bottom half), no glyphs.

``merge_runs`` is the shared color-run segmentation used by both.
"""

import math
import xml.sax.saxutils as sx

try:
    import cairosvg  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    cairosvg = None  # type: ignore[assignment]


def _fit_viewbox(
    content_w: float, content_h: float, px_w: int, px_h: int
) -> tuple[float, float, float, float]:
    """Pad a content viewBox to match the canvas aspect ratio.

    The SVG ``width``/``height`` attributes are set to ``px_w``/``px_h``
    while ``viewBox`` describes the content's own coordinate space. With
    the default ``preserveAspectRatio="xMidYMid meet"``, cairosvg scales
    the viewBox to fit *inside* the canvas and leaves transparent
    letterbox bars on the other axis when the aspect ratios differ — even
    though the CLI advertises ``px_w``x``px_h`` as the output size.

    To avoid that, pad the viewBox (on width or height, whichever is
    short) so its aspect ratio exactly matches ``px_w``/``px_h``. A
    same-aspect viewBox scales to fill the canvas with no gap, and a
    background rect drawn at "100% 100%" of the (padded) viewBox then
    covers the full canvas. The returned offsets center the original
    content within the padded viewBox.

    Args:
        content_w: Natural content width (e.g. ``cols * cell_w``).
        content_h: Natural content height (e.g. ``rows * cell_h``).
        px_w: Requested canvas width in px.
        px_h: Requested canvas height in px.

    Returns:
        ``(view_w, view_h, x_offset, y_offset)`` — the (possibly padded)
        viewBox dimensions and the translation needed to center the
        original content within it.
    """
    if not content_w or not content_h or not px_w or not px_h:
        return content_w, content_h, 0.0, 0.0

    canvas_aspect = px_w / px_h
    content_aspect = content_w / content_h

    if math.isclose(canvas_aspect, content_aspect, rel_tol=1e-6):
        return content_w, content_h, 0.0, 0.0

    if canvas_aspect > content_aspect:
        view_w = content_h * canvas_aspect
        return view_w, content_h, (view_w - content_w) / 2, 0.0

    view_h = content_w / canvas_aspect
    return content_w, view_h, 0.0, (view_h - content_h) / 2


def merge_runs(
    colors: list[tuple[int, int, int]], threshold: int = 10
) -> list[tuple[int, int, int, int, int]]:
    """Segment a row of RGB colors into runs of similar color.

    The anchor color for a run is its first pixel; subsequent pixels join
    the run while ``abs(channel diff) < threshold`` for all of r, g, b
    versus that anchor (matches the merge semantics historically used by
    img2ascii's HTML run-merging).

    Args:
        colors: Row of (r, g, b) tuples.
        threshold: Per-channel difference must be strictly less than this
            to continue a run.

    Returns:
        ``[(r, g, b, start_idx, length), ...]`` covering the full row in
        order. Empty input returns ``[]``.
    """
    runs: list[tuple[int, int, int, int, int]] = []
    i = 0
    n = len(colors)
    while i < n:
        r, g, b = colors[i]
        j = i + 1
        while j < n:
            r2, g2, b2 = colors[j]
            if abs(r2 - r) < threshold and abs(g2 - g) < threshold and abs(b2 - b) < threshold:
                j += 1
            else:
                break
        runs.append((r, g, b, i, j - i))
        i = j
    return runs


def ascii_grid_to_svg(
    grid: list[list[tuple[int, int, int, str]]],
    font_size: float,
    bg_color: str,
    px_w: int,
    px_h: int,
    auto_select: bool = False,
) -> str:
    """Render a per-pixel ascii grid to an SVG document.

    One ``<text>`` element per row, one ``<tspan fill="rgb(...)">`` per
    color-run (run text = the run's glyphs). Cell metrics match the
    historically-tuned chromium constants: ``cell_w = font_size * 0.6``,
    ``cell_h = font_size * 0.8``.

    Args:
        grid: Rows of (r, g, b, char).
        font_size: Font size in px (PNG default: 13).
        bg_color: CSS color for the full-canvas background rect.
        px_w: Output width in px (SVG ``width`` attribute).
        px_h: Output height in px (SVG ``height`` attribute).
        auto_select: If True, overlay the striped selection bands (same
            visual as the old ``--select`` CSS repeating-linear-gradient).

    Returns:
        A complete SVG document as a string.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    cell_w = font_size * 0.6
    cell_h = font_size * 0.8
    view_w = cols * cell_w
    view_h = rows * cell_h
    baseline_offset = font_size * 0.15

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

    overlay = ""
    if auto_select:
        row_height = cell_h
        half_row = row_height / 2
        bands: list[str] = []
        y = 0.0
        band_on = False
        while y < view_h:
            h = min(half_row, view_h - y)
            if band_on:
                bands.append(
                    f'<rect x="0" y="{y}" width="{view_w}" height="{h}" '
                    f'fill="rgba(0,0,0,0.2)"/>'
                )
            band_on = not band_on
            y += half_row
        overlay = "".join(bands)

    canvas_w, canvas_h, x_off, y_off = _fit_viewbox(
        view_w, view_h, px_w, px_h
    )
    content = f'{"".join(text_els)}{overlay}'
    if x_off or y_off:
        content = f'<g transform="translate({x_off},{y_off})">{content}</g>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{px_w}" height="{px_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">'
        f'<rect width="100%" height="100%" fill="{bg_color}"/>'
        f'<style>text {{ font-family: monospace; font-size: {font_size}px; }}</style>'
        f'{content}'
        f'</svg>'
    )


def ansi_grid_to_svg(
    grid: list[list[tuple[tuple[int, int, int], tuple[int, int, int]]]],
    cell_w: float,
    cell_h: float,
    px_w: int,
    px_h: int,
    bg_color: str,
) -> str:
    """Render a half-block (top/bottom color) grid to an SVG document.

    Each cell is two stacked solid-color rects (top half = fg/top pixel,
    bottom half = bg/bottom pixel) — the visual equivalent of the ``▀``
    glyph, without any text/glyph rasterization. Color-runs along each
    half are merged independently via ``merge_runs``.

    Args:
        grid: Rows of (top_rgb, bot_rgb) per cell.
        cell_w: Cell width in px.
        cell_h: Cell height in px (split evenly between top/bottom rects).
        px_w: Output width in px (SVG ``width`` attribute).
        px_h: Output height in px (SVG ``height`` attribute).
        bg_color: CSS color for the full-canvas background rect.

    Returns:
        A complete SVG document as a string.
    """
    rows = len(grid)
    cols = len(grid[0]) if rows else 0
    view_w = cols * cell_w
    view_h = rows * cell_h
    half_h = cell_h / 2

    rects: list[str] = []
    for row_idx, row in enumerate(grid):
        top_colors = [top for top, _ in row]
        bot_colors = [bot for _, bot in row]
        y_top = row_idx * cell_h
        y_bot = y_top + half_h
        for r, g, b, start, length in merge_runs(top_colors):
            x = start * cell_w
            w = length * cell_w
            rects.append(
                f'<rect x="{x}" y="{y_top}" width="{w}" height="{half_h}" '
                f'fill="rgb({r},{g},{b})"/>'
            )
        for r, g, b, start, length in merge_runs(bot_colors):
            x = start * cell_w
            w = length * cell_w
            rects.append(
                f'<rect x="{x}" y="{y_bot}" width="{w}" height="{half_h}" '
                f'fill="rgb({r},{g},{b})"/>'
            )

    canvas_w, canvas_h, x_off, y_off = _fit_viewbox(
        view_w, view_h, px_w, px_h
    )
    content = "".join(rects)
    if x_off or y_off:
        content = f'<g transform="translate({x_off},{y_off})">{content}</g>'

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{px_w}" height="{px_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}">'
        f'<rect width="100%" height="100%" fill="{bg_color}"/>'
        f'{content}'
        f'</svg>'
    )


def render_svg_to_png(svg: str, out_path: str) -> None:
    """Rasterize an SVG document to a PNG file.

    Writes directly to ``out_path`` (any filesystem) — unlike the old
    html2image-based path, no CWD/``shutil.move`` workaround is needed.

    Args:
        svg: A complete SVG document.
        out_path: Destination PNG path.
    """
    if cairosvg is None:
        print(
            "cairosvg is required to save a PNG. Run: pip install cairosvg"
        )
        return
    print(f"Snapping the PNG to {out_path}...")
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out_path)
    print("Image generated, stay frosty.")
