from unittest.mock import MagicMock, call, patch

import pytest

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


# ---------------------------------------------------------------------------
# write_png_from_html
# ---------------------------------------------------------------------------

_BASE_FLAGS = [
    "--hide-scrollbars",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-background-networking",
    "--log-level=3",
]
_GPU_FLAGS = [
    "--disable-gpu",
    "--disable-software-rasterizer",
    "--disable-dev-shm-usage",
]


def _make_hti_mock(monkeypatch):
    """Patch Html2Image and shutil.move; return (MockClass, mock_instance, mock_move)."""
    mock_hti = MagicMock()
    mock_cls = MagicMock(return_value=mock_hti)
    mock_move = MagicMock()
    monkeypatch.setattr("imgcommon.Html2Image", mock_cls)
    monkeypatch.setattr("imgcommon.shutil.move", mock_move)
    return mock_cls, mock_hti, mock_move


def test_write_png_screenshot_args(monkeypatch):
    """screenshot() called with correct html_str, save_as, and size."""
    mock_cls, mock_hti, _ = _make_hti_mock(monkeypatch)

    imgcommon.write_png_from_html("<h1>hi</h1>", "out.png", 800, 600, no_gpu=False)

    mock_hti.screenshot.assert_called_once_with(
        html_str="<h1>hi</h1>",
        save_as="out.png",
        size=(800, 600),
    )


def test_write_png_default_flags_no_gpu_false(monkeypatch):
    """no_gpu=False → only base flags passed to Html2Image."""
    mock_cls, _, _ = _make_hti_mock(monkeypatch)

    imgcommon.write_png_from_html("", "out.png", 1, 1, no_gpu=False)

    mock_cls.assert_called_once_with(
        custom_flags=_BASE_FLAGS, disable_logging=True
    )


def test_write_png_extra_flags_no_gpu_true(monkeypatch):
    """no_gpu=True → base flags + three disable-gpu flags."""
    mock_cls, _, _ = _make_hti_mock(monkeypatch)

    imgcommon.write_png_from_html("", "out.png", 1, 1, no_gpu=True)

    mock_cls.assert_called_once_with(
        custom_flags=_BASE_FLAGS + _GPU_FLAGS, disable_logging=True
    )


def test_write_png_moves_file_when_out_path_has_dir(monkeypatch):
    """shutil.move called when out_path contains a directory component."""
    _, _, mock_move = _make_hti_mock(monkeypatch)

    imgcommon.write_png_from_html("", "/tmp/subdir/out.png", 1, 1, no_gpu=False)

    mock_move.assert_called_once_with("out.png", "/tmp/subdir/out.png")


def test_write_png_skips_move_for_cwd_path(monkeypatch):
    """shutil.move NOT called when out_path is a bare filename (no directory)."""
    _, _, mock_move = _make_hti_mock(monkeypatch)

    imgcommon.write_png_from_html("", "out.png", 1, 1, no_gpu=False)

    mock_move.assert_not_called()


# ---------------------------------------------------------------------------


def test_load_and_enhance_returns_image(tmp_path):
    p = tmp_path / "src.png"
    _solid(8, 8).save(p)
    out = imgcommon.load_and_enhance(
        str(p), contrast=1.5, sharpness=2.5, brightness=1.0, saturate=1.0
    )
    assert isinstance(out, Image.Image)
    assert out.size == (8, 8)


# ---------------------------------------------------------------------------
# _percentile_from_histogram
# ---------------------------------------------------------------------------


def test_percentile_from_histogram_basic():
    hist = [0] * 256
    hist[20] = 10
    hist[80] = 90
    # total=100, 5th percentile threshold=5, cumulative hits 10 at index 20
    assert imgcommon._percentile_from_histogram(hist, 5) == 20


def test_percentile_from_histogram_empty():
    hist = [0] * 256
    assert imgcommon._percentile_from_histogram(hist, 5) == 0


# ---------------------------------------------------------------------------
# compute_auto_params
# ---------------------------------------------------------------------------


def test_compute_auto_params_solid_mid_gray():
    img = _solid(8, 8, (127, 127, 127))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == pytest.approx(1.0039, abs=1e-3)
    assert out["contrast"] == 2.5  # std==0 -> ratio blows up -> clamps high
    # mean_sat==0 -> ratio blows up -> clamps high
    assert out["saturate"] == 2.5
    assert out["min_lum"] == 0.0


def test_compute_auto_params_solid_near_black():
    img = _solid(8, 8, (10, 10, 10))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == 2.5  # mean_lum=10 -> ratio clamps high
    assert out["min_lum"] == pytest.approx(0.0808, abs=1e-3)


def test_compute_auto_params_solid_white():
    img = _solid(8, 8, (255, 255, 255))
    out = imgcommon.compute_auto_params(img)
    assert out["brightness"] == 0.5  # mean_lum=255 -> ratio clamps low
    assert out["min_lum"] == 0.0


def test_compute_auto_params_low_variance_gradient_boosts_contrast():
    # 51px-wide gradient from gray 100 to 150: low std -> contrast pushed up
    img = Image.new("RGB", (51, 4))
    for x in range(51):
        v = 100 + x
        for y in range(4):
            img.putpixel((x, y), (v, v, v))
    out = imgcommon.compute_auto_params(img)
    assert out["contrast"] > 1.0


def test_compute_auto_params_clamped_to_bounds():
    for color in [(0, 0, 0), (255, 255, 255), (1, 1, 1)]:
        out = imgcommon.compute_auto_params(_solid(4, 4, color))
        for key in ("brightness", "contrast", "saturate"):
            assert 0.5 <= out[key] <= 2.5
        assert 0.0 <= out["min_lum"] <= 0.3

