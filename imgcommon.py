#!/usr/bin/env python3
# flake8: noqa: E501
"""imgcommon.py — shared image-prep helpers for img2ascii / img2ansi."""

import colorsys
import os
import shutil

from html2image import Html2Image  # type: ignore[import-untyped]
from PIL import Image, ImageEnhance


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
    path: str,
    contrast: float,
    sharpness: float,
    brightness: float,
    saturate: float,
) -> Image.Image:
    img = Image.open(path)
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
    flags = ["--hide-scrollbars", "--no-sandbox", "--disable-setuid-sandbox"]
    if no_gpu:
        flags += [
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-dev-shm-usage",
        ]
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
