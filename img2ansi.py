#!/usr/bin/env python3
# flake8: noqa: E501
"""img2ansi.py — Convert an image to traditional ANSI art (half-block glyphs).

Usage:
    python3 img2ansi.py <input_image> [options]
"""

import sys
import os
import argparse

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
        if r > 248:
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
