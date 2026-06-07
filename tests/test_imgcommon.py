import os
import sys

import imgcommon
from PIL import Image


def test_lift_luminance_passthrough_when_min_zero():
    assert imgcommon.lift_luminance(10, 20, 30, 0.0) == (10, 20, 30)


def test_lift_luminance_raises_dark_pixel():
    # near-black pixel lifted to a higher luminance floor
    r, g, b = imgcommon.lift_luminance(0, 0, 0, 0.5)
    # all channels equal for a gray result, and clearly brighter than 0
    assert r == g == b
    assert r > 100


def test_lift_luminance_leaves_bright_pixel():
    # already-bright pixel above the floor is unchanged-ish
    r, g, b = imgcommon.lift_luminance(255, 255, 255, 0.5)
    assert (r, g, b) == (255, 255, 255)


def _solid(w, h, color=(120, 60, 200)):
    return Image.new("RGB", (w, h), color)


def test_resize_for_ascii_aspect():
    img = _solid(100, 100)
    out = imgcommon.resize_for(img, width=50, cell_aspect=0.48)
    # height = round(50 * (100/100) * 0.48) = 24
    assert out.size == (50, 24)
    assert out.mode == "RGB"


def test_resize_for_block_aspect():
    img = _solid(80, 40)
    out = imgcommon.resize_for(img, width=20, cell_aspect=1.0)
    # height = round(20 * (40/80) * 1.0) = 10
    assert out.size == (20, 10)


def test_load_and_enhance_returns_image(tmp_path):
    p = tmp_path / "src.png"
    _solid(8, 8).save(p)
    out = imgcommon.load_and_enhance(
        str(p), contrast=1.5, sharpness=2.5, brightness=1.0, saturate=1.0
    )
    assert isinstance(out, Image.Image)
    assert out.size == (8, 8)


def test_write_png_missing_html2image_returns_without_raising(
    monkeypatch, capsys, tmp_path
):
    # Force `import html2image` to raise ImportError inside the function.
    monkeypatch.setitem(sys.modules, "html2image", None)
    out = str(tmp_path / "out.png")

    imgcommon.write_png_from_html("<html></html>", out, 10, 10, False)

    captured = capsys.readouterr()
    assert "html2image" in captured.out  # prints the install hint
    assert not os.path.exists(out)       # no file written, no exception
