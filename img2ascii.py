#!/usr/bin/env python3
# flake8: noqa: E501
"""img2ascii.py — colored-ASCII render backend for ascii.

Maps each pixel's brightness to an ASCII glyph and colors it with the pixel's
RGB, emitting HTML. CLI lives in ascii.py (`ascii --style ascii`, the default).
"""

import sys

try:
    from PIL import Image, ImageEnhance
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

from imgcommon import lift_luminance

ascii_chars = (
    "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
)
ascii_chars = ascii_chars[::-1]


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
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturate != 1.0:
        img = ImageEnhance.Color(img).enhance(saturate)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    aspect = img.height / img.width
    height = int(width * aspect * 0.75)
    img = img.resize(  # type: ignore[arg-type]
        (width, height), resample=Image.Resampling.LANCZOS
    ).convert("RGB")

    rows: list[list[tuple[int, int, int, str]]] = []
    for y in range(height):
        row: list[tuple[int, int, int, str]] = []
        for x in range(width):
            pixel = img.getpixel((x, y))
            if isinstance(pixel, tuple):
                r, g, b = int(pixel[0]), int(pixel[1]), int(pixel[2])
            else:
                p = int(pixel) if pixel is not None else 0
                r, g, b = p, p, p
            r, g, b = lift_luminance(r, g, b, min_lum)
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            char_idx = int(lum / 255 * (len(ascii_chars) - 1))
            row.append((r, g, b, ascii_chars[char_idx]))
        rows.append(row)

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

    ascii_html = "<br>".join(lines_html)

    row_height = (font_size * 0.8) * text_scale
    half_row = row_height / 2

    w_css = f"{px_w}px" if px_w else "100vw"
    h_css = f"{px_h}px" if px_h else "100vh"

    selection_css = (
        f"""
    ::selection {{
      background: #0058d6 !important;
      color: #ffffff !important;
    }}
    body::after {{
      content: "";
      position: absolute;
      top: 0; left: 0; width: {w_css}; height: {h_css};
      background: repeating-linear-gradient(
        to bottom,
        transparent,
        transparent {half_row}px,
        rgba(0, 0, 0, 0.2) {half_row}px,
        rgba(0, 0, 0, 0.2) {row_height}px
      );
      pointer-events: none;
      z-index: 10;
    }}
    """
        if auto_select
        else ""
    )

    selection_js = (
        """
    <script>
      var pre = document.querySelector('pre');
      var range = document.createRange();
      range.selectNodeContents(pre);
      var sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
    </script>
    """
        if auto_select
        else ""
    )

    html = f"""<!DOCTYPE html>
<html style="margin:0;padding:0;width:{w_css};height:{h_css};overflow:hidden;">
<head>
<meta charset="UTF-8">
<style>
  body {{
    background: {bg_color};
    margin: 0;
    display: flex;
    justify-content: center;
    align-items: center;
    width: {w_css};
    height: {h_css};
    overflow: hidden;
    position: relative;
  }}
  pre {{
    font-family: 'Courier New', Courier, monospace;
    font-size: {font_size}px;
    line-height: 0.8;
    letter-spacing: 0px;
    white-space: pre;
    margin: 0;
    z-index: 1;
    transform: scale({text_scale});
    transform-origin: center;
  }}
  {selection_css}
</style>
</head>
<body>
<pre>{ascii_html}</pre>
{selection_js}
</body>
</html>"""
    return html
