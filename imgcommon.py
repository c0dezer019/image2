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


# Calibration constants for compute_auto_params. Tunable — these target a
# "typical photo" look (mid-gray mean, moderate spread, moderate
# saturation, lifted shadows).
_TARGET_MEAN_LUM = 0.50
_TARGET_STD_LUM = 0.22
_TARGET_MEAN_SAT = 0.45
_MIN_LUM_FLOOR = 0.12
_MIN_LUM_PCT = 5
_AUTO_CLAMP = (0.5, 2.5)
_MAX_AUTO_MIN_LUM = 0.30
_AUTO_EPS = 1e-6


def _percentile_from_histogram(hist: list[int], pct: float) -> int:
    """Return the 0-255 value at the given percentile of a 256-bin histogram."""
    total = sum(hist)
    if total == 0:
        return 0
    threshold = total * pct / 100
    cumulative = 0
    for value, count in enumerate(hist):
        cumulative += count
        if cumulative >= threshold:
            return value
    return 255


def compute_auto_params(img: Image.Image) -> dict[str, float]:
    """Derive contrast/brightness/saturate/min_lum from source image stats.

    Targets a fixed reference look (mid-gray mean luminance, moderate
    contrast spread, moderate saturation, lifted shadows) so dark, flat, or
    desaturated source images render closer to "as shot".

    Args:
        img: Source image, any mode, pre-resize and pre-enhancement.

    Returns:
        Dict with keys "brightness", "contrast", "saturate", "min_lum".
    """
    rgb = img.convert("RGB")
    gray = rgb.convert("L")
    stat = ImageStat.Stat(gray)
    mean_lum = stat.mean[0]
    std_lum = stat.stddev[0]
    low_lum = _percentile_from_histogram(gray.histogram(), _MIN_LUM_PCT)

    mean_sat = ImageStat.Stat(rgb.convert("HSV")).mean[1]

    lo, hi = _AUTO_CLAMP

    def _clamp_ratio(target: float, current: float) -> float:
        ratio = (target * 255) / max(current, _AUTO_EPS)
        return min(max(ratio, lo), hi)

    min_lum = max(0.0, _MIN_LUM_FLOOR - low_lum / 255)
    min_lum = min(min_lum, _MAX_AUTO_MIN_LUM)

    return {
        "brightness": _clamp_ratio(_TARGET_MEAN_LUM, mean_lum),
        "contrast": _clamp_ratio(_TARGET_STD_LUM, std_lum),
        "saturate": _clamp_ratio(_TARGET_MEAN_SAT, mean_sat),
        "min_lum": min_lum,
    }
