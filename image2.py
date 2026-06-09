#!/usr/bin/env python3
# flake8: noqa: E501
"""image2 — convert an image to colored ASCII or traditional ANSI art.

Usage:
    img2 ascii <input_image> [options]
    img2 ansi  <input_image> [options]

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
import importlib.metadata
import os
import sys

try:
    __version__ = importlib.metadata.version("image2")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"

try:
    from PIL import Image
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


def _shared_parser() -> argparse.ArgumentParser:
    """Parent parser carrying args common to both subcommands."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("input", nargs="?")
    p.add_argument("-o", "--output")
    p.add_argument("-w", "--width", type=int, default=None)
    p.add_argument("-c", "--contrast", type=float, default=1.5)
    p.add_argument("-s", "--sharpness", type=float, default=2.5)
    p.add_argument("-B", "--brightness", type=float, default=1.0)
    p.add_argument("--saturate", type=float, default=1.0)
    p.add_argument("--min-lum", type=float, default=0.0)
    p.add_argument("--no-gpu", action="store_true", default=False)
    return p


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="img2",
        description="Convert images to colored ASCII or ANSI art.",
    )
    p.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = p.add_subparsers(dest="style", required=True)

    ascii_p = sub.add_parser(
        "ascii",
        parents=[_shared_parser()],
        help="Colored ASCII art (PNG or HTML output)",
    )
    ascii_p.add_argument("--html", action="store_true", default=False)
    ascii_p.add_argument("--img-width", type=int, default=None)
    ascii_p.add_argument("--img-height", type=int, default=None)
    ascii_p.add_argument("-b", "--bg", default=None)
    ascii_p.add_argument("--font-size", type=float, default=None)
    ascii_p.add_argument("--select", action="store_true", default=False)

    ansi_p = sub.add_parser(
        "ansi",
        parents=[_shared_parser()],
        help="Traditional ANSI art (.ans output)",
    )
    ansi_p.add_argument(
        "--mode",
        choices=["truecolor", "256", "bbs16"],
        default=None,
    )
    ansi_p.add_argument("--png", action="store_true", default=False)

    return p


def resolve_width(style: str, width: int | None) -> int:
    if width is not None:
        return width
    return 350 if style == "ascii" else 80


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
    orig_w, orig_h = img.width, img.height
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
        px_w = orig_w
        px_h = orig_h
        write_png_from_html(html, png_path, px_w, px_h, args.no_gpu)


def _render_ascii(args, width: int) -> None:
    bg = args.bg if args.bg is not None else "#000000"
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )

    ext = ".html" if args.html else ".png"
    if args.output:
        base, given_ext = os.path.splitext(args.output)
        output_path = args.output if given_ext else args.output + ext
    else:
        output_path = os.path.splitext(args.input)[0] + "_ascii" + ext

    with Image.open(args.input) as im:
        img = im.copy()

    char_width_px = font_size * 0.6

    if args.img_width and args.img_height:
        px_w, px_h = args.img_width, args.img_height
    elif args.img_width:
        px_w = args.img_width
        px_h = img.height * px_w // img.width
    elif args.img_height:
        px_h = args.img_height
        px_w = img.width * px_h // img.height
    else:
        px_w = img.width
        px_h = img.height

    width = max(1, int((px_w - 2) / char_width_px))

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
        1.0,
        px_w,
        px_h,
    )

    if args.html:
        html_path = os.path.splitext(output_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML locked in at: {html_path}")
    else:
        write_png_from_html(html, output_path, px_w, px_h, args.no_gpu)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.input or not os.path.exists(args.input):
        print("Error: a valid input image path is required.")
        sys.exit(1)

    width = resolve_width(args.style, args.width)
    if args.style == "ansi":
        _render_ansi(args, width)
    else:
        _render_ascii(args, width)


if __name__ == "__main__":
    main()
