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
# compute_auto_bg
# ---------------------------------------------------------------------------


def test_compute_auto_bg_bright_source_picks_white():
    img = _solid(8, 8, (240, 240, 240))
    assert imgcommon.compute_auto_bg(img) == "#ffffff"


def test_compute_auto_bg_dark_source_picks_black():
    img = _solid(8, 8, (20, 20, 20))
    assert imgcommon.compute_auto_bg(img) == "#000000"
