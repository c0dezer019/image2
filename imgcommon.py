#!/usr/bin/env python3
# flake8: noqa: E501
"""imgcommon.py — shared image-prep helpers for img2ascii / img2ansi."""

import colorsys
import os
import shutil

try:
    from html2image import Html2Image  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    Html2Image = None  # type: ignore[assignment]
from PIL import Image, ImageEnhance, ImageStat


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


def write_png_from_html(
    html: str,
    out_path: str,
    px_w: int,
    px_h: int,
    no_gpu: bool,
) -> None:
    """Rasterize HTML to a PNG via headless Chrome (html2image).

    Uses shutil.move so output across filesystems works.
    """
    flags = [
        "--hide-scrollbars",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-background-networking",
        "--log-level=3",
    ]
    if no_gpu:
        flags += [
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
        ]
    if Html2Image is None:
        print(
            "html2image is required to save a PNG. Run: pip install html2image"
        )
        return
    hti = Html2Image(custom_flags=flags, disable_logging=True)
    print(f"Snapping the PNG to {out_path}...")
    hti.screenshot(
        html_str=html,
        save_as=os.path.basename(out_path),
        size=(px_w, px_h),
    )
    if os.path.dirname(out_path):
        shutil.move(os.path.basename(out_path), out_path)
    print("Image generated, stay frosty.")


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
