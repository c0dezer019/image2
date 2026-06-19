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
# build_ascii_grid / build_halfblock_grid
# ---------------------------------------------------------------------------


def test_build_ascii_grid_dimensions_and_chars():
    img = _solid(8, 8, (255, 255, 255))
    grid = imgcommon.build_ascii_grid(
        img,
        width=4,
        contrast=1.0,
        sharpness=1.0,
        brightness=1.0,
        min_lum=0.0,
        saturate=1.0,
    )
    # height = max(1, int(4 * (8/8) * 0.75)) = 3
    assert len(grid) == 3
    assert all(len(row) == 4 for row in grid)
    # solid white -> max luminance -> last (brightest) glyph everywhere
    r, g, b, ch = grid[0][0]
    assert (r, g, b) == (255, 255, 255)
    assert ch == imgcommon.ascii_chars[-1]


def test_build_ascii_grid_min_lum_lifts_dark_pixel():
    img = _solid(4, 4, (0, 0, 0))
    grid = imgcommon.build_ascii_grid(
        img,
        width=2,
        contrast=1.0,
        sharpness=1.0,
        brightness=1.0,
        min_lum=0.5,
        saturate=1.0,
    )
    r, g, b, _ = grid[0][0]
    assert r == g == b
    assert r > 0


def test_build_halfblock_grid_pairs_top_and_bottom():
    img = Image.new("RGB", (2, 2))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((0, 1), (0, 0, 255))
    img.putpixel((1, 1), (255, 255, 0))

    grid = imgcommon.build_halfblock_grid(img)

    assert len(grid) == 1
    assert grid[0][0] == ((255, 0, 0), (0, 0, 255))
    assert grid[0][1] == ((0, 255, 0), (255, 255, 0))


def test_build_halfblock_grid_drops_trailing_odd_row():
    img = Image.new("RGB", (1, 3), (10, 20, 30))
    grid = imgcommon.build_halfblock_grid(img)
    assert len(grid) == 1


# ---------------------------------------------------------------------------


def test_load_and_enhance_returns_image():
    img = _solid(8, 8)
    out = imgcommon.load_and_enhance(
        img, contrast=1.5, sharpness=2.5, brightness=1.0, saturate=1.0
    )
    assert isinstance(out, Image.Image)
    assert out.size == (8, 8)


def test_load_and_enhance_does_not_mutate_input():
    img = _solid(8, 8)
    original = img.copy()
    imgcommon.load_and_enhance(
        img, contrast=2.0, sharpness=2.5, brightness=1.5, saturate=1.5
    )
    assert list(img.getdata()) == list(original.getdata())


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
    assert out["brightness"] == 1.0  # mean_lum=255 -> never darkened
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


# ---------------------------------------------------------------------------
# compute_auto_bg
# ---------------------------------------------------------------------------


def test_compute_auto_bg_bright_source_picks_white():
    img = _solid(8, 8, (240, 240, 240))
    assert imgcommon.compute_auto_bg(img) == "#ffffff"


def test_compute_auto_bg_dark_source_picks_black():
    img = _solid(8, 8, (20, 20, 20))
    assert imgcommon.compute_auto_bg(img) == "#000000"
