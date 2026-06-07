import img2ansi


def test_rgb_to_256_black_and_white():
    assert img2ansi.rgb_to_256(0, 0, 0) == 16
    assert img2ansi.rgb_to_256(255, 255, 255) == 231


def test_rgb_to_256_pure_red_in_cube():
    # pure red maps into the 16..231 color cube
    idx = img2ansi.rgb_to_256(255, 0, 0)
    assert 16 <= idx <= 231


def test_rgb_to_16_red():
    fg, bg = img2ansi.rgb_to_16(255, 0, 0)
    # bright or normal red foreground, matching background offset
    assert fg in (31, 91)
    assert bg in (41, 101)


def test_rgb_to_16_black_white():
    fg_k, _ = img2ansi.rgb_to_16(0, 0, 0)
    fg_w, _ = img2ansi.rgb_to_16(255, 255, 255)
    assert fg_k == 30          # black
    assert fg_w in (37, 97)    # white / bright white


from PIL import Image


def _two_row(top, bot, width=1):
    img = Image.new("RGB", (width, 2))
    for x in range(width):
        img.putpixel((x, 0), top)
        img.putpixel((x, 1), bot)
    return img


def test_truecolor_single_cell():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    line = out.splitlines()[0]
    assert "\x1b[38;2;255;0;0m" in line   # fg = top
    assert "\x1b[48;2;0;0;255m" in line   # bg = bottom
    assert "▀" in line               # ▀
    assert line.rstrip().endswith("\x1b[0m")


def test_cell_count_matches_width():
    img = _two_row((10, 20, 30), (40, 50, 60), width=5)
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    assert out.splitlines()[0].count("▀") == 5


def test_256_mode_uses_5_prefix():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="256")
    assert "\x1b[38;5;" in out
    assert "\x1b[48;5;" in out


def test_bbs16_mode_uses_sgr_codes():
    img = _two_row((255, 0, 0), (0, 0, 255))
    out = img2ansi.image_to_ansi(img, mode="bbs16")
    # red fg (31 or 91), blue bg (44 or 104)
    assert ("\x1b[31m" in out) or ("\x1b[91m" in out)
    assert ("\x1b[44m" in out) or ("\x1b[104m" in out)


def test_odd_height_drops_trailing_row():
    img = Image.new("RGB", (1, 3), (0, 0, 0))
    out = img2ansi.image_to_ansi(img, mode="truecolor")
    # 3 rows -> 1 cell row (floor(3/2))
    assert len([ln for ln in out.splitlines() if ln]) == 1
