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
