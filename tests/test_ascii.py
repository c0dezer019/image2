import os
import sys

import pytest
from PIL import Image

import ascii


def test_default_style_is_ascii():
    args = ascii.build_parser().parse_args(["in.jpg"])
    assert args.style == "ascii"


def test_width_resolves_per_style():
    assert ascii.resolve_width("ascii", None) == 350
    assert ascii.resolve_width("ansi", None) == 80
    assert ascii.resolve_width("ascii", 120) == 120
    assert ascii.resolve_width("ansi", 120) == 120


def test_cross_style_ok_when_flags_match_style():
    p = ascii.build_parser()
    assert ascii.cross_style_error(p.parse_args(["in.jpg"])) is None
    assert ascii.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--mode", "256"])
    ) is None
    assert ascii.cross_style_error(
        p.parse_args(["in.jpg", "--html"])
    ) is None


def test_ansi_flag_under_ascii_errors():
    p = ascii.build_parser()
    msg = ascii.cross_style_error(p.parse_args(["in.jpg", "--mode", "256"]))
    assert msg == "--mode requires --style ansi"
    msg = ascii.cross_style_error(p.parse_args(["in.jpg", "--png"]))
    assert msg == "--png requires --style ansi"


def test_ascii_flag_under_ansi_errors():
    p = ascii.build_parser()
    msg = ascii.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--html"])
    )
    assert msg == "--html requires --style ascii"
    msg = ascii.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--font-size", "5"])
    )
    assert msg == "--font-size requires --style ascii"


def test_main_wrong_style_exits_2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ascii", "in.jpg", "--mode", "256"])
    with pytest.raises(SystemExit) as exc:
        ascii.main()
    assert exc.value.code == 2


def _tiny_image(tmp_path):
    path = tmp_path / "tiny.png"
    img = Image.new("RGB", (4, 4), (200, 100, 50))
    img.save(path)
    return str(path)


def test_ansi_writes_ans_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.ans")
    monkeypatch.setattr(
        sys, "argv", ["ascii", src, "--style", "ansi", "-o", out]
    )
    ascii.main()
    assert os.path.exists(out)
    data = open(out, encoding="utf-8").read()
    assert "\x1b[" in data and "▀" in data


def test_ascii_html_writes_html_file(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    out = str(tmp_path / "art.html")
    monkeypatch.setattr(sys, "argv", ["ascii", src, "--html", "-o", out])
    ascii.main()
    assert os.path.exists(out)
    assert "<pre>" in open(out, encoding="utf-8").read()


def test_ascii_default_output_path(tmp_path, monkeypatch):
    # ascii + --html with no -o -> <input>_ascii.html next to source
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ascii", src, "--html"])
    ascii.main()
    expected = os.path.splitext(src)[0] + "_ascii.html"
    assert os.path.exists(expected)


def test_ansi_default_output_path(tmp_path, monkeypatch):
    src = _tiny_image(tmp_path)
    monkeypatch.setattr(sys, "argv", ["ascii", src, "--style", "ansi"])
    ascii.main()
    expected = os.path.splitext(src)[0] + "_ansi.ans"
    assert os.path.exists(expected)
