#!/usr/bin/env python3
# flake8: noqa: E501
"""
img2ascii.py — Convert any image to pure colored ASCII art HTML and optionally export as an image.

Usage:
    python3 img2ascii.py <input_image> [options]

Options:
    -o, --output        Output file path (default: <input_name>_ascii.png or .html)
    --html              Save an HTML file instead of a PNG image
                        (optionally specify file path)
    --img-width         Force the pixel width of the output PNG (auto-scales height and text)
    --img-height        Force the pixel height of the output PNG (auto-scales width and text)
    -w, --width         Character width of output (default: 350).
                        If the source image is narrower than --width chars,
                        it is upsampled first so detail isn't invented from nothing.
    -c, --contrast      Contrast enhancement multiplier (default: 1.5)
    -s, --sharpness     Sharpness enhancement multiplier (default: 2.5)
    -B, --brightness    Brightness enhancement multiplier (default: 1.0)
    --min-lum           Minimum HLS luminance 0.0-1.0 (default: 0.0)
    --saturate          Color saturation multiplier (default: 1.0)
    -b, --bg            HTML background color (default: #000000)
    --font-size         Font size in px (default: 4.0)
    --select            Auto-select the text to replicate OS highlight effects
    --no-gpu            Disables GPU usage for compatibility issues.
    -h, --help          Show this help message
"""

import sys
import os
import argparse
import shutil

try:
    from PIL import Image, ImageEnhance
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

from imgcommon import lift_luminance

try:
    from html2image import Html2Image  # type: ignore[import-untyped]
except ImportError:
    Html2Image = None

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
) -> str:
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturate != 1.0:
        img = ImageEnhance.Color(img).enhance(saturate)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)

    aspect = img.height / img.width
    height = int(width * aspect * 0.48)
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

    selection_css = (
        f"""
    ::selection {{
      background: #0058d6 !important;
      color: #ffffff !important;
    }}
    body::after {{
      content: "";
      position: absolute;
      top: 0; left: 0; width: 100vw; height: 100vh;
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
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{
    background: {bg_color};
    margin: 0;
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    width: 100vw;
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


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("--html", action="store_true", default=False)
    parser.add_argument(
        "--img-width",
        type=int,
        help="Force the pixel width of the output PNG",
    )
    parser.add_argument(
        "--img-height",
        type=int,
        help="Force the pixel height of the output PNG",
    )
    parser.add_argument("-w", "--width", type=int, default=350)
    parser.add_argument("-c", "--contrast", type=float, default=1.5)
    parser.add_argument("-s", "--sharpness", type=float, default=2.5)
    parser.add_argument("-B", "--brightness", type=float, default=1.0)
    parser.add_argument("--min-lum", type=float, default=0.0)
    parser.add_argument("--saturate", type=float, default=1.0)
    parser.add_argument("-b", "--bg", default="#000000")
    parser.add_argument("--font-size", type=float, default=4.0)
    parser.add_argument("--select", action="store_true")
    parser.add_argument("--no-gpu", action="store_true", default=False)
    parser.add_argument("-h", "--help", action="help")

    args = parser.parse_args()

    if not args.html:
        args.font_size = 6.5

    if not args.input or not os.path.exists(args.input):
        print("Bummer dude, need a valid input image.")
        sys.exit(1)

    img = Image.open(args.input)
    ext = ".html" if args.html else ".png"
    if args.output:
        base, given_ext = os.path.splitext(args.output)
        output_path = args.output if given_ext else args.output + ext
    else:
        output_path = os.path.splitext(args.input)[0] + "_ascii" + ext

    aspect = img.height / img.width
    ascii_height = int(args.width * aspect * 0.48)

    # Stripped the +120 padding and locked the font ratio to
    # eliminate the black borders
    char_width_px = args.font_size * 0.6
    line_height_px = args.font_size * 0.8
    # +2 safety pixels to prevent sub-pixel cutoff
    auto_w = int((args.width * char_width_px) + 2)
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
    html = image_to_ascii_html(
        img,
        args.width,
        args.contrast,
        args.sharpness,
        args.brightness,
        args.min_lum,
        args.saturate,
        args.bg,
        args.font_size,
        args.select,
        scale,
    )
    if args.html:
        html_path = os.path.splitext(output_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML locked in at: {html_path}")

    if not args.html:
        if Html2Image is None:
            print(
                "Gnarly wipeout, comrad! You need html2image to save a PNG. "
                "Run: pip install html2image"
            )
        else:
            img_out = output_path

            print(f"Snapping the PNG photo to {img_out} at {px_w}x{px_h}...")

            if not args.no_gpu:
                hti = Html2Image(
                    custom_flags=[
                        "--hide-scrollbars",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                    ]
                )
            else:
                hti = Html2Image(
                    custom_flags=[
                        "--hide-scrollbars",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-dev-shm-usage",
                    ]
                )
            hti.screenshot(  # type: ignore[misc]
                html_str=html,
                save_as=os.path.basename(img_out),
                size=(px_w, px_h),
            )

            if os.path.dirname(img_out):
                shutil.move(os.path.basename(img_out), img_out)

            print("Image generated, stay frosty.")


if __name__ == "__main__":
    main()
