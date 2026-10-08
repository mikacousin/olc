from unittest.mock import MagicMock

import pytest
from olc.curve import (
    Curves,
    InterpolateCurve,
    LimitCurve,
    LinearCurve,
    SegmentsCurve,
    SquareRootCurve,
)
from olc.files.parsed_data import ParsedData
from olc.gtk3.widgets.curve import get_curve_display_name


def test_get_level() -> None:
    curve = LinearCurve()
    assert curve.name == "Linear"
    for x in range(256):
        assert curve.get_level(x) == x


def test_get_level_square_root() -> None:
    curve = SquareRootCurve()
    assert curve.name == "Square root"
    assert curve.get_level(0) == 0
    assert curve.get_level(25) == 80
    assert curve.get_level(255) == 255


def test_get_level_limit() -> None:
    curve = LimitCurve(limit=127)
    assert curve.name == "Limit"
    assert curve.limit == 127
    assert curve.get_level(0) == 0
    assert curve.get_level(255) == 127


def test_get_level_segments() -> None:
    curve = SegmentsCurve()
    curve.add_point(2, 0)
    curve.add_point(3, 255)
    assert curve.name == "Segment"
    assert curve.get_level(0) == 0
    assert curve.get_level(3) == 255
    assert curve.get_level(255) == 255


def test_get_level_interpolate() -> None:
    curve = InterpolateCurve()
    curve.add_point(70, 40)
    assert curve.name == "Interpolate"
    assert curve.get_level(0) == 0
    assert curve.get_level(40) == 20
    assert curve.get_level(70) == 40
    assert curve.get_level(100) == 64
    assert curve.get_level(255) == 255


def test_set_point_segments() -> None:
    curve = SegmentsCurve()
    curve.set_point(0, 0, 255)
    assert curve.get_level(0) == 255


def test_default_curve_names() -> None:
    curves = Curves(MagicMock())
    curve0 = curves.get_curve(0)
    assert curve0 is not None and curve0.name == "Linear"
    curve1 = curves.get_curve(1)
    assert curve1 is not None and curve1.name == "Square root"
    curve2 = curves.get_curve(2)
    assert curve2 is not None and curve2.name == "Full at 1%"
    curve3 = curves.get_curve(3)
    assert curve3 is not None and curve3.name == "IES Square"
    curve4 = curves.get_curve(4)
    assert curve4 is not None and curve4.name == "Slow Bottom"
    curve5 = curves.get_curve(5)
    assert curve5 is not None and curve5.name == "Fast Bottom"
    curve6 = curves.get_curve(6)
    assert curve6 is not None and curve6.name == "Fast Top"


def test_get_curve_display_name() -> None:
    assert get_curve_display_name(None) == ""
    linear = LinearCurve()
    assert get_curve_display_name(linear) == "Linear"
    limit = LimitCurve(limit=128)
    assert get_curve_display_name(limit) == "Limit 50%"


def test_get_curve_display_name_translated(monkeypatch: pytest.MonkeyPatch) -> None:
    translations = {
        "Linear": "Linéaire",
        "Limit": "Limite à",
        "Segment": "Segments",
    }
    monkeypatch.setattr("olc.gtk3.widgets.curve._", lambda s: translations.get(s, s))
    linear = LinearCurve()
    assert linear.name == "Linear"
    assert get_curve_display_name(linear) == "Linéaire"
    limit = LimitCurve(limit=128)
    assert limit.name == "Limit"
    assert get_curve_display_name(limit) == "Limite à 50%"


def test_legacy_curve_names_import() -> None:
    lightshow = MagicMock()
    curves_dict: dict = {}
    lightshow.curves.curves = curves_dict
    parsed = ParsedData(lightshow)
    parsed.data = {
        "curves": {
            10: {
                "type": "SegmentsCurve",
                "points": [[0, 0], [255, 255]],
                "label": "Segments",
            },
            11: {"type": "LimitCurve", "limit": 128, "label": "Limite à"},
            12: {"type": "LimitCurve", "limit": 200, "label": "Custom Limit"},
        }
    }
    parsed.import_curves()
    assert curves_dict[10].name == "Segment"
    assert curves_dict[11].name == "Limit"
    assert curves_dict[12].name == "Custom Limit"
