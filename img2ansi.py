#!/usr/bin/env python3
# flake8: noqa: E501
"""img2ansi.py — Convert an image to traditional ANSI art (half-block glyphs).

Each character cell is an upper-half block (▀): the top source pixel becomes
the foreground color, the bottom pixel the background color, doubling vertical
resolution.

Usage:
    python3 img2ansi.py <input_image> [options]

Options:
    -o, --output      Output path (default: <input>_ansi.ans)
    -w, --width       Character columns (default: 80, BBS-authentic)
    --mode            truecolor (default) | 256 | bbs16
    --png             Also rasterize a PNG via html2image
    -c, --contrast    Contrast multiplier (default: 1.5)
    -s, --sharpness   Sharpness multiplier (default: 2.5)
    -B, --brightness  Brightness multiplier (default: 1.0)
    --saturate        Saturation multiplier (default: 1.0)
    --min-lum         Minimum HLS luminance 0.0-1.0 (default: 0.0)
    --no-gpu          Disable GPU for html2image (PNG only)
    -h, --help        Show this help

View output:  cat <file>.ans
"""

import sys
import os
import argparse
import shutil

try:
    from PIL import Image  # noqa: F401
except ImportError:
    print("Error: Pillow is required. Install it with: pip install Pillow")
    sys.exit(1)

from imgcommon import load_and_enhance, resize_for, lift_luminance

UPPER_HALF = "▀"  # ▀

# Classic 16-color CP437/VGA palette: (r, g, b, fg_sgr, bg_sgr)
PALETTE_16 = [
    (0, 0, 0, 30, 40),
    (170, 0, 0, 31, 41),
    (0, 170, 0, 32, 42),
    (170, 85, 0, 33, 43),
    (0, 0, 170, 34, 44),
    (170, 0, 170, 35, 45),
    (0, 170, 170, 36, 46),
    (170, 170, 170, 37, 47),
    (85, 85, 85, 90, 100),
    (255, 85, 85, 91, 101),
    (85, 255, 85, 92, 102),
    (255, 255, 85, 93, 103),
    (85, 85, 255, 94, 104),
    (255, 85, 255, 95, 105),
    (85, 255, 255, 96, 106),
    (255, 255, 255, 97, 107),
]


def rgb_to_256(r: int, g: int, b: int) -> int:
    """Map an RGB triple to the nearest xterm-256 index (16..255)."""
    # grayscale ramp check
    if abs(r - g) < 8 and abs(g - b) < 8:
        if r < 8:
            return 16
        if r > 247:
            return 231
        return 232 + (r - 8) // 10
    r6 = round(r / 255 * 5)
    g6 = round(g / 255 * 5)
    b6 = round(b / 255 * 5)
    return 16 + 36 * r6 + 6 * g6 + b6


def rgb_to_16(r: int, g: int, b: int) -> tuple[int, int]:
    """Map an RGB triple to nearest 16-color palette (fg_sgr, bg_sgr)."""
    best = PALETTE_16[0]
    best_d = None
    for pr, pg, pb, fg, bg in PALETTE_16:
        d = (pr - r) ** 2 + (pg - g) ** 2 + (pb - b) ** 2
        if best_d is None or d < best_d:
            best_d = d
            best = (pr, pg, pb, fg, bg)
    return best[3], best[4]


def _cell_escape(
    top: tuple[int, int, int],
    bot: tuple[int, int, int],
    mode: str,
) -> str:
    tr, tg, tb = top
    br, bg_, bb = bot
    if mode == "truecolor":
        return (
            f"\x1b[38;2;{tr};{tg};{tb}m"
            f"\x1b[48;2;{br};{bg_};{bb}m{UPPER_HALF}"
        )
    if mode == "256":
        return (
            f"\x1b[38;5;{rgb_to_256(tr, tg, tb)}m"
            f"\x1b[48;5;{rgb_to_256(br, bg_, bb)}m{UPPER_HALF}"
        )
    if mode == "bbs16":
        fg, _ = rgb_to_16(tr, tg, tb)
        _, bg_code = rgb_to_16(br, bg_, bb)
        return f"\x1b[{fg}m\x1b[{bg_code}m{UPPER_HALF}"
    raise ValueError(f"unknown mode: {mode}")


def image_to_ansi(img: Image.Image, mode: str = "truecolor") -> str:
    """Render an RGB image to ANSI half-block art. Samples 2 rows per cell."""
    img = img.convert("RGB")
    w, h = img.size
    rows = h // 2
    lines: list[str] = []
    for cy in range(rows):
        y = cy * 2
        cells: list[str] = []
        for x in range(w):
            top = img.getpixel((x, y))
            bot = img.getpixel((x, y + 1))
            cells.append(_cell_escape(top, bot, mode))
        lines.append("".join(cells) + "\x1b[0m")
    return "\n".join(lines)


def ansi_image_to_html(
    img: Image.Image,
    bg_color: str,
    font_size: float,
) -> str:
    """Render the half-block art to HTML for html2image rasterization.

    Always truecolor in the PNG preview; the .ans file carries the
    quantized version for the chosen mode.
    """
    img = img.convert("RGB")
    w, h = img.size
    rows = h // 2
    lines_html: list[str] = []
    for cy in range(rows):
        y = cy * 2
        spans: list[str] = []
        for x in range(w):
            tr, tg, tb = img.getpixel((x, y))
            br, bg_, bb = img.getpixel((x, y + 1))
            spans.append(
                f'<span style="color:rgb({tr},{tg},{tb});'
                f'background:rgb({br},{bg_},{bb})">{UPPER_HALF}</span>'
            )
        lines_html.append("".join(spans))
    body = "<br>".join(lines_html)
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>
  body {{ background:{bg_color}; margin:0; }}
  pre {{
    font-family:'Courier New',Courier,monospace;
    font-size:{font_size}px;
    line-height:{font_size}px;
    letter-spacing:0;
    white-space:pre;
    margin:0;
  }}
</style></head>
<body><pre>{body}</pre></body>
</html>"""


def _write_png(
    html: str,
    out_path: str,
    width: int,
    rows: int,
    font_size: float,
    no_gpu: bool,
) -> None:
    try:
        from html2image import Html2Image  # type: ignore[import-untyped]
    except ImportError:
        print(
            "Gnarly wipeout, comrad! You need html2image to save a PNG. "
            "Run: pip install html2image"
        )
        return
    flags = ["--hide-scrollbars", "--no-sandbox", "--disable-setuid-sandbox"]
    if no_gpu:
        flags += [
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
        ]
    # Canvas sized to the art: each cell ~ font_size*0.6 wide, font_size tall.
    # +2 safety pixels to avoid sub-pixel cutoff.
    px_w = int(width * font_size * 0.6) + 2
    px_h = int(rows * font_size) + 2
    hti = Html2Image(custom_flags=flags)
    print(f"Snapping the PNG to {out_path}...")
    hti.screenshot(
        html_str=html,
        save_as=os.path.basename(out_path),
        size=(px_w, px_h),
    )
    if os.path.dirname(out_path):
        shutil.move(os.path.basename(out_path), out_path)
    print("Image generated, stay frosty.")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("input", nargs="?")
    parser.add_argument("-o", "--output")
    parser.add_argument("-w", "--width", type=int, default=80)
    parser.add_argument(
        "--mode",
        choices=["truecolor", "256", "bbs16"],
        default="truecolor",
    )
    parser.add_argument("--png", action="store_true", default=False)
    parser.add_argument("-c", "--contrast", type=float, default=1.5)
    parser.add_argument("-s", "--sharpness", type=float, default=2.5)
    parser.add_argument("-B", "--brightness", type=float, default=1.0)
    parser.add_argument("--saturate", type=float, default=1.0)
    parser.add_argument("--min-lum", type=float, default=0.0)
    parser.add_argument("--no-gpu", action="store_true", default=False)
    parser.add_argument("-h", "--help", action="help")
    args = parser.parse_args()

    if not args.input or not os.path.exists(args.input):
        print("Bummer dude, need a valid input image.")
        sys.exit(1)

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
    # half-block: cell_aspect 1.0, then sample 2 rows per cell ->
    # need an even pixel height of ~ 2x the cell rows.
    img = resize_for(img, args.width, cell_aspect=1.0)

    if args.min_lum > 0:
        img = img.convert("RGB")
        for y in range(img.height):
            for x in range(img.width):
                r, g, b = img.getpixel((x, y))
                img.putpixel((x, y), lift_luminance(r, g, b, args.min_lum))

    print("Carving the ANSI wave...")
    ansi = image_to_ansi(img, mode=args.mode)
    with open(ans_path, "w", encoding="utf-8") as f:
        f.write(ansi + "\n")
    print(f"ANSI locked in at: {ans_path}")

    if args.png:
        png_path = os.path.splitext(ans_path)[0] + ".png"
        font_size = 8.0
        rows = img.height // 2
        html = ansi_image_to_html(
            img, bg_color="#000000", font_size=font_size
        )
        _write_png(
            html, png_path, args.width, rows, font_size, args.no_gpu
        )


if __name__ == "__main__":
    main()
