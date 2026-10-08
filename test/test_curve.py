"""Unit tests for transfer curves."""

# pylint: disable=missing-function-docstring

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


def test_normalized_curves_import() -> None:
    lightshow = MagicMock()
    curves_dict: dict = {}
    lightshow.curves.curves = curves_dict
    parsed = ParsedData(lightshow)
    parsed.data = {
        "curves": {
            10: {
                "type": "SegmentsCurve",
                "points": [[0.0, 0.0], [0.5, 0.25], [1.0, 1.0]],
                "label": "NormSegments",
            },
            11: {"type": "LimitCurve", "limit": 0.5, "label": "NormLimit"},
        }
    }
    parsed.import_curves()
    assert curves_dict[10].points[1] == (128, 64)
    assert curves_dict[11].limit == 128


def test_16bit_evaluation_linear() -> None:
    curve = LinearCurve()
    assert len(curve.values_array_16bit) == 65536
    assert curve.get_level_16bit(0) == 0
    assert curve.get_level_16bit(32768) == 32768
    assert curve.get_level_16bit(65535) == 65535
    assert curve.evaluate_16bit(1000) == 1000


def test_16bit_evaluation_square_root() -> None:
    curve = SquareRootCurve()
    assert len(curve.values_array_16bit) == 65536
    assert curve.get_level_16bit(0) == 0
    assert curve.get_level_16bit(65535) == 65535
    # Value at quarter power should be half of 65535
    quarter = 65535 // 4
    half = 65535 // 2
    assert abs(curve.get_level_16bit(quarter) - half) <= 1


def test_16bit_evaluation_limit() -> None:
    curve = LimitCurve(limit=128)
    assert curve.normalized_limit == pytest.approx(128 / 255.0)
    assert curve.get_level_16bit(0) == 0
    expected_max = round(65535 * (128 / 255.0))
    assert curve.get_level_16bit(65535) == expected_max


def test_16bit_evaluation_segments() -> None:
    curve = SegmentsCurve()
    curve.add_point(128, 64)
    assert len(curve.values_array_16bit) == 65536
    assert curve.get_level_16bit(0) == 0
    assert curve.get_level_16bit(65535) == 65535
    # Verify smooth slope without 8-bit quantization steps
    mid_idx = 32768  # near 128/255
    assert curve.get_level_16bit(mid_idx) > 0
    # Steps between adjacent 16-bit indices should be small
    diff = curve.get_level_16bit(1001) - curve.get_level_16bit(1000)
    assert diff in (0, 1)


def test_16bit_evaluation_interpolate() -> None:
    curve = InterpolateCurve()
    curve.add_point(70, 40)
    assert len(curve.values_array_16bit) == 65536
    assert curve.get_level_16bit(0) == 0
    assert curve.get_level_16bit(65535) == 65535
    # Adjacent 16-bit points should be smooth
    for idx in (1000, 20000, 50000):
        diff = abs(curve.get_level_16bit(idx + 1) - curve.get_level_16bit(idx))
        assert diff <= 3


def test_evaluate_normalized() -> None:
    linear = LinearCurve()
    assert linear.evaluate_normalized(0.0) == 0.0
    assert linear.evaluate_normalized(0.5) == 0.5
    assert linear.evaluate_normalized(1.0) == 1.0

    sq = SquareRootCurve()
    assert sq.evaluate_normalized(0.0) == 0.0
    assert sq.evaluate_normalized(0.25) == pytest.approx(0.5)
    assert sq.evaluate_normalized(1.0) == 1.0


def test_evaluate_range() -> None:
    linear = LinearCurve()
    # Map [0, 100] to [10, 50]
    assert (
        linear.evaluate_range(0, in_min=0, in_max=100, out_min=10, out_max=50) == 10.0
    )
    assert (
        linear.evaluate_range(50, in_min=0, in_max=100, out_min=10, out_max=50) == 30.0
    )
    assert (
        linear.evaluate_range(100, in_min=0, in_max=100, out_min=10, out_max=50) == 50.0
    )


def test_normalized_points() -> None:
    curve = SegmentsCurve()
    assert curve.normalized_points == [(0.0, 0.0), (1.0, 1.0)]
    curve.add_normalized_point(0.5, 0.25)
    norm = curve.normalized_points
    assert len(norm) == 3
    assert norm[1][0] == pytest.approx(0.5, abs=0.01)
    assert norm[1][1] == pytest.approx(0.25, abs=0.01)
