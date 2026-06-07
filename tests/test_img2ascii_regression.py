import img2ascii
from PIL import Image


def test_image_to_ascii_html_stable_output(tmp_path):
    # deterministic 4-color image, fixed params -> stable HTML
    img = Image.new("RGB", (4, 4))
    img.putpixel((0, 0), (255, 0, 0))
    img.putpixel((1, 0), (0, 255, 0))
    img.putpixel((2, 0), (0, 0, 255))
    img.putpixel((3, 0), (255, 255, 255))

    html = img2ascii.image_to_ascii_html(
        img,
        width=4,
        contrast=1.5,
        sharpness=2.5,
        brightness=1.0,
        min_lum=0.0,
        saturate=1.0,
        bg_color="#000000",
        font_size=4.0,
        auto_select=False,
        text_scale=1.0,
    )
    assert "<pre>" in html
    assert "rgb(" in html
    assert "font-size: 4.0px" in html


def test_lift_luminance_still_exposed():
    # img2ascii must still expose lift_luminance (re-exported from imgcommon)
    assert img2ascii.lift_luminance(10, 20, 30, 0.0) == (10, 20, 30)
