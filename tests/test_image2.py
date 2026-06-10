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
    monkeypatch.setattr(sys, "argv", ["img2", "ascii", src, "--html", "-o", out])
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


def test_resolve_enhance_params_all_explicit_skips_image(tmp_path):
    # nonexistent path proves the image is never opened when nothing is None
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(missing, 2.0, 1.1, 0.9, 0.05, False)
    assert result == (2.0, 1.1, 0.9, 0.05)


def test_resolve_enhance_params_auto_fills_unset(tmp_path):
    src = _tiny_image(tmp_path)
    with Image.open(src) as img:
        expected = imgcommon.compute_auto_params(img.convert("RGB"))
    result = image2.resolve_enhance_params(src, None, None, None, None, False)
    assert result == (
        expected["contrast"],
        expected["brightness"],
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_no_auto_uses_old_defaults(tmp_path):
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(
        missing, None, None, None, None, True
    )
    assert result == (1.5, 1.0, 1.0, 0.0)


def test_resolve_enhance_params_partial_override_with_auto(tmp_path):
    src = _tiny_image(tmp_path)
    with Image.open(src) as img:
        expected = imgcommon.compute_auto_params(img.convert("RGB"))
    result = image2.resolve_enhance_params(src, None, 1.2, None, None, False)
    assert result == (
        expected["contrast"],
        1.2,
        expected["saturate"],
        expected["min_lum"],
    )


def test_resolve_enhance_params_partial_override_no_auto(tmp_path):
    missing = str(tmp_path / "does-not-exist.png")
    result = image2.resolve_enhance_params(
        missing, 2.0, None, None, None, True
    )
    assert result == (2.0, 1.0, 1.0, 0.0)
