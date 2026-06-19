#!/usr/bin/env python3
# flake8: noqa: E501
"""image2 — convert an image to colored ASCII or traditional ANSI art.

Usage:
    img2 ascii <input_image> [options]
    img2 ansi  <input_image> [options]

Shared options:
    -o, --output      Output path
    -w, --width       Character columns (default: ascii 350, ansi 80)
    -c, --contrast    Contrast multiplier (default: auto-detected)
    -s, --sharpness   Sharpness multiplier (default: 2.5)
    -B, --brightness  Brightness multiplier (default: auto-detected)
    --saturate        Saturation multiplier (default: auto-detected)
    -ml, --min-lum    Minimum HLS luminance 0.0-1.0 (default: auto-detected)
    --no-auto         Disable auto-detection; use fixed defaults
                      (contrast 1.5, brightness 1.0, saturate 1.0,
                      min-lum 0.0) for any of the above not given.
                      Sharpness is never auto-detected and is
                      unaffected by this flag.
    --invert          Invert source image colors before rendering
    --blur            Gaussian blur radius applied before processing
                      (default: 0.0, disabled)
    -h, --help        Show help

ascii-only:
    --html            Save HTML instead of PNG
    --img-width, -W   Force output PNG pixel width
    --img-height, -H  Force output PNG pixel height
    --aspect-ratio,
    -ar               Aspect ratio for PNG output ("16:9" or "1.778");
                      derives the unset dimension from -W or -H (or from
                      the source width if neither given). Conflicts with
                      passing both -W and -H.
    -b, --bg          Background color (default: auto-detected from
                      source image tone, #ffffff or #000000; #000000
                      under --no-auto)
    --font-size, -f   Font size px (default: 4.0 HTML / 13 PNG)
    --select, -s      Auto-highlight the text
    --monochrome, -m  Render all glyphs in a single solid color
    --font-color, -F  Solid font color (implies --monochrome,
                      default #ffffff)
    --min             Cap width to 100 and font-size to 8 (PNG) /
                      2.0 (HTML) for a quick, low-detail render
                      (default: off, "dense" mode)

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
    from PIL import Image, ImageFilter, ImageOps
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

import img2ansi
import img2ascii
from imgcommon import (
    build_ascii_grid,
    build_halfblock_grid,
    compute_auto_bg,
    compute_auto_params,
    load_and_enhance,
    resize_for,
    lift_luminance,
)
from imgsvg import ascii_grid_to_svg, ansi_grid_to_svg, render_svg_to_png
import img2ui


def parse_aspect_ratio(value: str) -> float:
    """Parse "W:H" or a plain float into a width/height ratio."""
    if ":" in value:
        w, _, h = value.partition(":")
        try:
            w, h = float(w), float(h)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"invalid aspect ratio: {value!r}"
            )
        if h == 0:
            raise argparse.ArgumentTypeError(
                f"invalid aspect ratio: {value!r}"
            )
        return w / h
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"invalid aspect ratio: {value!r}"
        )


def _shared_parser() -> argparse.ArgumentParser:
    """Parent parser carrying args common to both subcommands."""
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("input", nargs="?")
    p.add_argument("-o", "--output")
    p.add_argument("-w", "--width", type=int, default=None)
    p.add_argument("-c", "--contrast", type=float, default=None)
    p.add_argument("-s", "--sharpness", type=float, default=2.5)
    p.add_argument("-B", "--brightness", type=float, default=None)
    p.add_argument("-S", "--saturate", type=float, default=None)
    p.add_argument("-ml", "--min-lum", type=float, default=None)
    p.add_argument("--no-auto", action="store_true", default=False)
    p.add_argument("--invert", action="store_true", default=False)
    p.add_argument("--blur", type=float, default=0.0)
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
    ascii_p.add_argument("-W", "--img-width", type=int, default=None)
    ascii_p.add_argument("-H", "--img-height", type=int, default=None)
    ascii_p.add_argument(
        "-ar", "--aspect-ratio", type=parse_aspect_ratio, default=None
    )
    ascii_p.add_argument("-b", "--bg", default=None)
    ascii_p.add_argument("-f", "--font-size", type=float, default=None)
    ascii_p.add_argument("--select", action="store_true", default=False)
    ascii_p.add_argument("-m", "--monochrome", action="store_true", default=False)
    ascii_p.add_argument("-F", "--font-color", default=None)
    ascii_p.add_argument("--min", action="store_true", default=False)
    ascii_p.add_argument(
        "--ui",
        action="store_true",
        default=False,
        help="Open Image2-Web UI pre-seeded with this image and params",
    )

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
    ansi_p.add_argument(
        "--ui",
        action="store_true",
        default=False,
        help="Open Image2-Web UI pre-seeded with this image and params",
    )

    ui_p = sub.add_parser(
        "ui",
        help="Launch Image2-Web UI locally via Docker Compose",
    )
    ui_p.add_argument(
        "--stop",
        action="store_true",
        default=False,
        help="Stop the running Docker Compose stack",
    )

    return p


def resolve_width(style: str, width: int | None) -> int:
    if width is not None:
        return width
    return 350 if style == "ascii" else 80


def apply_min_cap(value, cap, enabled):
    """Clamp value to cap (only lowers, never raises) when enabled."""
    return min(value, cap) if enabled else value


# Old fixed defaults, used when --no-auto is passed.
_OLD_ENHANCE_DEFAULTS = {
    "contrast": 1.5,
    "brightness": 1.0,
    "saturate": 1.0,
    "min_lum": 0.0,
}


def resolve_enhance_params(
    img: Image.Image,
    contrast: float | None,
    brightness: float | None,
    saturate: float | None,
    min_lum: float | None,
    no_auto: bool,
) -> tuple[float, float, float, float]:
    """Fill in unset enhancement params from auto-detection or old defaults.

    Any of contrast/brightness/saturate/min_lum left as None is filled from
    imgcommon.compute_auto_params(img), unless no_auto is True, in which
    case unset params fall back to the historical fixed defaults.

    Args:
        img: Already-opened source image (used for auto-detection only;
            not modified).

    Returns:
        (contrast, brightness, saturate, min_lum) fully resolved.
    """
    requested = {
        "contrast": contrast,
        "brightness": brightness,
        "saturate": saturate,
        "min_lum": min_lum,
    }
    if all(v is not None for v in requested.values()):
        return contrast, brightness, saturate, min_lum

    auto = _OLD_ENHANCE_DEFAULTS if no_auto else compute_auto_params(img)

    resolved = {
        key: (value if value is not None else auto[key])
        for key, value in requested.items()
    }
    return (
        resolved["contrast"],
        resolved["brightness"],
        resolved["saturate"],
        resolved["min_lum"],
    )


def _render_ansi(args, width: int, img: Image.Image) -> None:
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
        img,
        args.contrast,
        args.sharpness,
        args.brightness,
        args.saturate,
    )
    img = resize_for(img, width, cell_aspect=1.0)

    if args.min_lum > 0:
        img = img.convert("RGB")
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                img.putpixel((x, y), lift_luminance(r, g, b, args.min_lum))

    print("Generating the ANSI...")
    ansi = img2ansi.image_to_ansi(img, mode=mode)
    with open(ans_path, "w", encoding="utf-8") as f:
        f.write(ansi + "\n")
    print(f"ANSI locked in at: {ans_path}")

    if args.png:
        png_path = os.path.splitext(ans_path)[0] + ".png"
        font_size = 8.0
        char_width_px = font_size * 0.6
        cols = img.width
        rows = img.height // 2
        grid = build_halfblock_grid(img)
        px_w = round(cols * char_width_px)
        px_h = round(rows * font_size)
        svg = ansi_grid_to_svg(
            grid, char_width_px, font_size, px_w, px_h, "#000000"
        )
        render_svg_to_png(svg, png_path)


def _render_ascii(args, width: int, img: Image.Image) -> None:
    if args.bg is not None:
        bg = args.bg
    elif args.no_auto:
        bg = "#000000"
    else:
        bg = compute_auto_bg(img)
    font_size = (
        args.font_size
        if args.font_size is not None
        else (4.0 if args.html else 13)
    )
    monochrome = args.monochrome or args.font_color is not None
    font_color = args.font_color or (
        "#000000" if bg == "#ffffff" else "#ffffff"
    )

    ext = ".html" if args.html else ".png"
    if args.output:
        base, given_ext = os.path.splitext(args.output)
        output_path = args.output if given_ext else args.output + ext
    else:
        output_path = os.path.splitext(args.input)[0] + "_ascii" + ext

    char_width_px = font_size * 0.6

    if args.aspect_ratio:
        if args.img_width:
            px_w = args.img_width
            px_h = round(px_w / args.aspect_ratio)
        elif args.img_height:
            px_h = args.img_height
            px_w = round(px_h * args.aspect_ratio)
        else:
            px_w = img.width
            px_h = round(px_w / args.aspect_ratio)
    elif args.img_width and args.img_height:
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

    if args.width is None:
        width = max(1, int((px_w - 2) / char_width_px))
    width = apply_min_cap(width, 100, args.min)

    font_size = apply_min_cap(
        font_size, 2.0 if args.html else 8, args.min
    )
    char_width_px = font_size * 0.6

    if args.html:
        # Canvas must fit the rendered ascii grid exactly (mirrors the
        # row/col math in img2ascii.image_to_ascii_html), else the centered
        # <pre> gets clipped top/bottom by overflow:hidden.
        aspect = img.height / img.width
        ascii_rows = max(1, int(width * aspect * 0.75))
        px_w = round(width * char_width_px)
        px_h = round(ascii_rows * (font_size * 0.8))

        print("Generating HTML...")
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
        html_path = os.path.splitext(output_path)[0] + ".html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"HTML locked in at: {html_path}")
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
        svg = ascii_grid_to_svg(
            grid, font_size, bg, px_w, px_h, args.select,
            monochrome, font_color,
        )
        render_svg_to_png(svg, output_path)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.style == "ui":
        img2ui.cmd_ui(args)
        return

    if not args.input or not os.path.exists(args.input):
        print("Error: a valid input image path is required.")
        sys.exit(1)

    if (
        getattr(args, "aspect_ratio", None)
        and args.img_width
        and args.img_height
    ):
        parser.error(
            "argument -ar/--aspect-ratio: not allowed with both "
            "-W/--img-width and -H/--img-height"
        )

    width = resolve_width(args.style, args.width)
    with Image.open(args.input) as opened:
        img = opened.convert("RGB")

    if args.invert:
        img = ImageOps.invert(img)

    if args.blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=args.blur))

    args.contrast, args.brightness, args.saturate, args.min_lum = (
        resolve_enhance_params(
            img,
            args.contrast,
            args.brightness,
            args.saturate,
            args.min_lum,
            args.no_auto,
        )
    )
    if getattr(args, "ui", False):
        ui_params = {
            "contrast": str(args.contrast),
            "brightness": str(args.brightness),
            "sharpness": str(args.sharpness),
            "saturate": str(args.saturate),
            "min_lum": str(args.min_lum),
            "width": str(width),
        }
        img2ui.cmd_ui_with_file(args.input, args.style, ui_params)
        return

    if args.style == "ansi":
        _render_ansi(args, width, img)
    else:
        _render_ascii(args, width, img)


if __name__ == "__main__":
    main()
