#!/usr/bin/env python3
# flake8: noqa: E501
"""imgcommon.py — shared image-prep helpers for img2ascii / img2ansi."""

import colorsys

from PIL import Image, ImageEnhance, ImageStat

# Reversed so index 0 = darkest. Brightness maps to lum/255 * (len-1).
ascii_chars = (
    "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "
)
ascii_chars = ascii_chars[::-1]


def lift_luminance(
    r: int, g: int, b: int, min_l: float
) -> tuple[int, int, int]:
    if min_l <= 0:
        return r, g, b
    h, luminance, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    if luminance < min_l:
        luminance = min_l
    nr, ng, nb = colorsys.hls_to_rgb(h, luminance, s)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def load_and_enhance(
    img: Image.Image,
    contrast: float,
    sharpness: float,
    brightness: float,
    saturate: float,
) -> Image.Image:
    """Apply brightness/contrast/saturation/sharpness to an opened image.

    Does not mutate ``img`` — each ImageEnhance step returns a new image.
    """
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    img = ImageEnhance.Contrast(img).enhance(contrast)
    if saturate != 1.0:
        img = ImageEnhance.Color(img).enhance(saturate)
    img = ImageEnhance.Sharpness(img).enhance(sharpness)
    return img


def resize_for(
    img: Image.Image, width: int, cell_aspect: float
) -> Image.Image:
    aspect = img.height / img.width
    height = round(width * aspect * cell_aspect)
    height = max(1, height)
    return img.resize(
        (width, height), resample=Image.Resampling.LANCZOS
    ).convert("RGB")


def build_ascii_grid(
    img: Image.Image,
    width: int,
    contrast: float,
    sharpness: float,
    brightness: float,
    min_lum: float,
    saturate: float,
) -> list[list[tuple[int, int, int, str]]]:
    """Enhance, resize, and map an image to a per-pixel ascii grid.

    Shared by ``img2ascii.image_to_ascii_html`` (--html output) and the
    SVG/PNG path (``imgsvg.ascii_grid_to_svg``). Resize uses
    ``cell_aspect=0.75`` (truncating, matching the historical ascii-grid
    math) rather than ``resize_for``'s rounding, to keep --html output
    byte-identical.

    Args:
        img: Source image, any mode.
        width: Target grid width in columns.
        contrast: Contrast multiplier.
        sharpness: Sharpness multiplier.
        brightness: Brightness multiplier.
        min_lum: Minimum HLS luminance floor (0.0-1.0), see lift_luminance.
        saturate: Saturation multiplier.

    Returns:
        Rows of ``(r, g, b, ascii_char)``, one entry per output pixel.
    """
    img = load_and_enhance(img, contrast, sharpness, brightness, saturate)

    aspect = img.height / img.width
    height = max(1, int(width * aspect * 0.75))
    img = img.resize(
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
    return rows


def build_halfblock_grid(
    img: Image.Image,
) -> list[list[tuple[tuple[int, int, int], tuple[int, int, int]]]]:
    """Sample an image into per-cell (top, bottom) half-block pixel pairs.

    Each output cell corresponds to two source rows: the top pixel becomes
    the foreground/upper-half color, the bottom pixel the background/
    lower-half color (the ``▀`` half-block convention). Shared by
    ``img2ansi.image_to_ansi`` (.ans text, quantized per-mode from this
    grid) and the SVG/PNG path (``imgsvg.ansi_grid_to_svg``, always
    truecolor).

    Args:
        img: Source image, any mode (converted to RGB).

    Returns:
        Rows of ``((top_r, top_g, top_b), (bot_r, bot_g, bot_b))``. A
        trailing odd source row is dropped.
    """
    img = img.convert("RGB")
    w, h = img.size
    rows = h // 2
    grid: list[list[tuple[tuple[int, int, int], tuple[int, int, int]]]] = []
    for cy in range(rows):
        y = cy * 2
        row: list[tuple[tuple[int, int, int], tuple[int, int, int]]] = []
        for x in range(w):
            top = img.getpixel((x, y))
            bot = img.getpixel((x, y + 1))
            row.append((top, bot))
        grid.append(row)
    return grid


def compute_auto_bg(img: Image.Image) -> str:
    """Pick an ascii background color that contrasts with the source tone.

    Glyphs never fully cover a cell, so the background color shows
    through the gaps. A fixed black background muddies high-key (mostly
    bright) sources; this picks white for those and keeps black for
    everything else.

    Args:
        img: Source image, any mode, pre-resize and pre-enhancement.

    Returns:
        "#ffffff" or "#000000".
    """
    mean_lum = ImageStat.Stat(img.convert("L")).mean[0]
    return "#ffffff" if mean_lum > 127.5 else "#000000"


