import os
import sys

import pytest
from PIL import Image

import image2
import imgcommon


def test_ascii_subcommand_sets_style():
    args = image2.build_parser().parse_args(["ascii", "in.jpg"])
    assert args.style == "ascii"


def test_ansi_subcommand_sets_style():
    args = image2.build_parser().parse_args(["ansi", "in.jpg"])
    assert args.style == "ansi"


def test_no_subcommand_exits():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args([])


def test_width_resolves_per_style():
    assert image2.resolve_width("ascii", None) == 350
    assert image2.resolve_width("ansi", None) == 80
    assert image2.resolve_width("ascii", 120) == 120
    assert image2.resolve_width("ansi", 120) == 120


def test_ascii_only_flags_available_under_ascii():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--html", "--font-size", "5"])
    assert args.html is True
    assert args.font_size == 5.0


def test_ansi_only_flags_available_under_ansi():
    p = image2.build_parser()
    args = p.parse_args(["ansi", "in.jpg", "--mode", "256"])
    assert args.mode == "256"


def test_ansi_flag_rejected_under_ascii():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(["ascii", "in.jpg", "--mode", "256"])


def test_ascii_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(["ansi", "in.jpg", "--html"])


def _tiny_image(tmp_path):
    path = tmp_path / "tiny.png"
    img = Image.new("RGB", (4, 4), (200, 100, 50))
    img.save(path)
    return str(path)


def _noisy_image(tmp_path):
    import random

    path = tmp_path / "noisy.png"
    img = Image.new("RGB", (8, 8))
    rng = random.Random(0)
    for y in range(8):
        for x in range(8):
            img.putpixel(
                (x, y),
                (
                    rng.randint(0, 255),
                    rng.randint(0, 255),
                    rng.randint(0, 255),
                ),
            )
    img.save(path)
    return str(path)


def test_ansi_writes_ans_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.ans")
    monkeypatch.setattr(sys, "argv", ["img2", "ansi", src, "-o", out])
    image2.main()
    assert os.path.exists(out)
    data = open(out, encoding="utf-8").read()
    assert "\x1b[" in data and "▀" in data


def test_ascii_html_writes_html_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--html", "-o", out]
    )
    image2.main()
    assert os.path.exists(out)
    assert "<pre>" in open(out, encoding="utf-8").read()


def test_ascii_default_output_path(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["img2", "ascii", src, "--html"])
    image2.main()
    expected = os.path.splitext(src)[0] + "_ascii.html"
    assert os.path.exists(expected)


def test_ansi_default_output_path(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["img2", "ansi", src])
    image2.main()
    expected = os.path.splitext(src)[0] + "_ansi.ans"
    assert os.path.exists(expected)


def _tiny_pil_image():
    return Image.new("RGB", (4, 4), (200, 100, 50))


@pytest.mark.parametrize(
    "extra_args, out_name",
    [
        (["ansi"], "art.ans"),
        (["ascii", "--html"], "art.html"),
    ],
)
def test_main_opens_source_image_only_once(
    tmp_path, monkeypatch, extra_args, out_name
):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / out_name)
    style, *flags = extra_args
    monkeypatch.setattr(
        sys, "argv", ["img2", style, src, *flags, "-o", out]
    )

    real_open = Image.open
    calls = []

    def counting_open(fp, *args, **kwargs):
        calls.append(fp)
        return real_open(fp, *args, **kwargs)

    monkeypatch.setattr(Image, "open", counting_open)
    image2.main()
    assert calls.count(src) == 1


def test_resolve_enhance_params_all_explicit_skips_image():
    # bogus non-Image sentinel proves the image is never touched when
    # nothing is None
    result = image2.resolve_enhance_params(
        object(), 2.0, 1.1, 0.9, 0.05, False
    )
    assert result == (2.0, 1.1, 0.9, 0.05)


def test_resolve_enhance_params_auto_fills_unset():
    img = _tiny_pil_image()
    expected = imgcommon.compute_auto_params(img)
    result = image2.resolve_enhance_params(img, None, None, None, None, False)
    assert result == (
        expected["contrast"],
        expected["brightness"],
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_no_auto_uses_old_defaults():
    result = image2.resolve_enhance_params(
        object(), None, None, None, None, True
    )
    assert result == (1.5, 1.0, 1.0, 0.0)


def test_invert_flag_available_for_both_styles():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--invert"])
    assert args.invert is True
    args = p.parse_args(["ansi", "in.jpg", "--invert"])
    assert args.invert is True


def test_invert_flag_defaults_false():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.invert is False


def test_blur_flag_defaults_zero():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.blur == 0.0


def test_blur_flag_available_for_both_styles():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg", "--blur", "1.5"])
    assert args.blur == 1.5
    args = p.parse_args(["ansi", "in.jpg", "--blur", "1.5"])
    assert args.blur == 1.5


def test_ansi_blur_changes_output(tmp_path, monkeypatch):
    src = _noisy_image(tmp_path)
    out_normal = str(tmp_path / "normal.ans")
    out_blurred = str(tmp_path / "blurred.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_normal, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ansi", src, "-o", out_blurred, "--no-auto", "--blur", "2.0"],
    )
    image2.main()

    normal = open(out_normal, encoding="utf-8").read()
    blurred = open(out_blurred, encoding="utf-8").read()
    assert normal != blurred


def test_ansi_blur_zero_is_noop(tmp_path, monkeypatch):
    src = _noisy_image(tmp_path)
    out_default = str(tmp_path / "default.ans")
    out_explicit_zero = str(tmp_path / "explicit_zero.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_default, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "img2", "ansi", src, "-o", out_explicit_zero,
            "--no-auto", "--blur", "0",
        ],
    )
    image2.main()

    default = open(out_default, encoding="utf-8").read()
    explicit_zero = open(out_explicit_zero, encoding="utf-8").read()
    assert default == explicit_zero


def test_ansi_invert_changes_output(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out_normal = str(tmp_path / "normal.ans")
    out_inverted = str(tmp_path / "inverted.ans")

    monkeypatch.setattr(
        sys, "argv", ["img2", "ansi", src, "-o", out_normal, "--no-auto"]
    )
    image2.main()

    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ansi", src, "-o", out_inverted, "--no-auto", "--invert"],
    )
    image2.main()

    normal = open(out_normal, encoding="utf-8").read()
    inverted = open(out_inverted, encoding="utf-8").read()
    assert normal != inverted


def test_resolve_enhance_params_partial_override_with_auto():
    img = _tiny_pil_image()
    expected = imgcommon.compute_auto_params(img)
    result = image2.resolve_enhance_params(img, None, 1.2, None, None, False)
    assert result == (
        expected["contrast"],
        1.2,
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_partial_override_no_auto():
    result = image2.resolve_enhance_params(
        object(), 2.0, None, None, None, True
    )
    assert result == (2.0, 1.0, 1.0, 0.0)


def test_monochrome_flags_available_for_ascii():
    p = image2.build_parser()
    args = p.parse_args(
        ["ascii", "in.jpg", "--monochrome", "--font-color", "#00ff00"]
    )
    assert args.monochrome is True
    assert args.font_color == "#00ff00"


def test_monochrome_flags_default():
    p = image2.build_parser()
    args = p.parse_args(["ascii", "in.jpg"])
    assert args.monochrome is False
    assert args.font_color is None


def test_monochrome_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(["ansi", "in.jpg", "--monochrome"])


def test_font_color_flag_rejected_under_ansi():
    with pytest.raises(SystemExit):
        image2.build_parser().parse_args(
            ["ansi", "in.jpg", "--font-color", "#00ff00"]
        )


def test_ascii_monochrome_default_color(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ascii", src, "--html", "-o", out, "--monochrome"],
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "color:#ffffff" in html
    assert "rgb(" not in html


def test_ascii_font_color_implies_monochrome(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys,
        "argv",
        ["img2", "ascii", src, "--html", "-o", out, "--font-color", "#00ff00"],
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "color:#00ff00" in html
    assert "rgb(" not in html


def test_ascii_no_monochrome_uses_per_pixel_color(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(
        sys, "argv", ["img2", "ascii", src, "--html", "-o", out]
    )
    image2.main()
    html = open(out, encoding="utf-8").read()
    assert "rgb(" in html
