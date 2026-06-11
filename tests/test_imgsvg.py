import xml.etree.ElementTree as ET

import imgsvg

SVG_NS = "{http://www.w3.org/2000/svg}"


# ---------------------------------------------------------------------------
# merge_runs
# ---------------------------------------------------------------------------


def test_merge_runs_uniform_row_is_single_run():
    colors = [(10, 20, 30)] * 5
    runs = imgsvg.merge_runs(colors)
    assert runs == [(10, 20, 30, 0, 5)]


def test_merge_runs_alternating_colors_are_separate_runs():
    colors = [(0, 0, 0), (50, 50, 50), (100, 100, 100)]
    runs = imgsvg.merge_runs(colors)
    assert runs == [
        (0, 0, 0, 0, 1),
        (50, 50, 50, 1, 1),
        (100, 100, 100, 2, 1),
    ]


def test_merge_runs_diff_below_threshold_continues_run():
    colors = [(0, 0, 0), (9, 0, 0)]
    runs = imgsvg.merge_runs(colors)
    assert runs == [(0, 0, 0, 0, 2)]


def test_merge_runs_diff_at_threshold_breaks_run():
    colors = [(0, 0, 0), (10, 0, 0)]
    runs = imgsvg.merge_runs(colors)
    assert runs == [(0, 0, 0, 0, 1), (10, 0, 0, 1, 1)]


def test_merge_runs_empty_input():
    assert imgsvg.merge_runs([]) == []


# ---------------------------------------------------------------------------
# ascii_grid_to_svg
# ---------------------------------------------------------------------------


def _ascii_grid():
    # row: (0,0,0)/'a' and (5,5,5)/'b' merge (diff 5 < 10), (100,100,100)/'c'
    # breaks the run.
    return [
        [(0, 0, 0, "a"), (5, 5, 5, "b"), (100, 100, 100, "c")],
    ]


def test_ascii_grid_to_svg_text_and_tspan_runs():
    svg = imgsvg.ascii_grid_to_svg(
        _ascii_grid(), font_size=10, bg_color="#000000", px_w=18, px_h=8
    )
    root = ET.fromstring(svg)

    texts = root.findall(f"{SVG_NS}text")
    assert len(texts) == 1

    tspans = texts[0].findall(f"{SVG_NS}tspan")
    assert [t.text for t in tspans] == ["ab", "c"]
    assert tspans[0].get("fill") == "rgb(0,0,0)"
    assert tspans[1].get("fill") == "rgb(100,100,100)"

    assert root.get("width") == "18"
    assert root.get("height") == "8"
    assert root.get("viewBox") == "0 0 18.0 8.0"


def test_ascii_grid_to_svg_auto_select_adds_overlay_rects():
    without = ET.fromstring(
        imgsvg.ascii_grid_to_svg(
            _ascii_grid(), font_size=10, bg_color="#000000", px_w=18, px_h=8
        )
    )
    with_overlay = ET.fromstring(
        imgsvg.ascii_grid_to_svg(
            _ascii_grid(),
            font_size=10,
            bg_color="#000000",
            px_w=18,
            px_h=8,
            auto_select=True,
        )
    )

    rects_without = without.findall(f"{SVG_NS}rect")
    rects_with = with_overlay.findall(f"{SVG_NS}rect")

    assert len(rects_with) > len(rects_without)
    overlay_rects = [
        r for r in rects_with if r.get("fill") == "rgba(0,0,0,0.2)"
    ]
    assert overlay_rects


# ---------------------------------------------------------------------------
# ansi_grid_to_svg
# ---------------------------------------------------------------------------


def test_ansi_grid_to_svg_top_and_bottom_rects():
    grid = [
        [((255, 0, 0), (0, 0, 255)), ((255, 0, 0), (0, 0, 255))],
    ]
    svg = imgsvg.ansi_grid_to_svg(
        grid, cell_w=10, cell_h=20, px_w=20, px_h=20, bg_color="#000000"
    )
    root = ET.fromstring(svg)

    rects = root.findall(f"{SVG_NS}rect")
    # background rect + one merged top run + one merged bottom run
    assert len(rects) == 3

    bg_rect, top_rect, bot_rect = rects
    assert bg_rect.get("fill") == "#000000"

    assert top_rect.get("fill") == "rgb(255,0,0)"
    assert top_rect.get("x") == "0"
    assert top_rect.get("y") == "0"
    assert top_rect.get("width") == "20"
    assert top_rect.get("height") == "10.0"

    assert bot_rect.get("fill") == "rgb(0,0,255)"
    assert bot_rect.get("x") == "0"
    assert bot_rect.get("y") == "10.0"
    assert bot_rect.get("width") == "20"
    assert bot_rect.get("height") == "10.0"


# ---------------------------------------------------------------------------
# render_svg_to_png
# ---------------------------------------------------------------------------


def test_render_svg_to_png_calls_cairosvg(monkeypatch):
    calls = {}

    def fake_svg2png(bytestring, write_to):
        calls["bytestring"] = bytestring
        calls["write_to"] = write_to

    fake_cairosvg = type(
        "M", (), {"svg2png": staticmethod(fake_svg2png)}
    )
    monkeypatch.setattr(imgsvg, "cairosvg", fake_cairosvg)

    imgsvg.render_svg_to_png("<svg/>", "out.png")

    assert calls["write_to"] == "out.png"
    assert calls["bytestring"] == "<svg/>".encode("utf-8")


def test_render_svg_to_png_missing_cairosvg(monkeypatch, capsys):
    monkeypatch.setattr(imgsvg, "cairosvg", None)

    imgsvg.render_svg_to_png("<svg/>", "out.png")

    out = capsys.readouterr().out
    assert "cairosvg is required" in out
    assert "pip install cairosvg" in out
