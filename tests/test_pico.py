import sys

import pytest

import pico


def test_default_style_is_ascii():
    args = pico.build_parser().parse_args(["in.jpg"])
    assert args.style == "ascii"


def test_width_resolves_per_style():
    assert pico.resolve_width("ascii", None) == 350
    assert pico.resolve_width("ansi", None) == 80
    assert pico.resolve_width("ascii", 120) == 120
    assert pico.resolve_width("ansi", 120) == 120


def test_cross_style_ok_when_flags_match_style():
    p = pico.build_parser()
    assert pico.cross_style_error(p.parse_args(["in.jpg"])) is None
    assert pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--mode", "256"])
    ) is None
    assert pico.cross_style_error(
        p.parse_args(["in.jpg", "--html"])
    ) is None


def test_ansi_flag_under_ascii_errors():
    p = pico.build_parser()
    msg = pico.cross_style_error(p.parse_args(["in.jpg", "--mode", "256"]))
    assert msg == "--mode requires --style ansi"
    msg = pico.cross_style_error(p.parse_args(["in.jpg", "--png"]))
    assert msg == "--png requires --style ansi"


def test_ascii_flag_under_ansi_errors():
    p = pico.build_parser()
    msg = pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--html"])
    )
    assert msg == "--html requires --style ascii"
    msg = pico.cross_style_error(
        p.parse_args(["in.jpg", "--style", "ansi", "--font-size", "5"])
    )
    assert msg == "--font-size requires --style ascii"


def test_main_wrong_style_exits_2(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["pico", "in.jpg", "--mode", "256"])
    with pytest.raises(SystemExit) as exc:
        pico.main()
    assert exc.value.code == 2
