from curve import (
    LinearCurve,
    SquareRootCurve,
    LimitCurve,
    SegmentsCurve,
    InterpolateCurve,
)


def test_get_level():
    curve = LinearCurve()
    assert curve.name == "Linear"
    for x in range(256):
        assert curve.get_level(x) == x


def test_get_level_square_root():
    curve = SquareRootCurve()
    assert curve.name == "Square root"
    assert curve.get_level(0) == 0
    assert curve.get_level(25) == 80
    assert curve.get_level(255) == 255


def test_get_level_limit():
    curve = LimitCurve(limit=127)
    assert curve.name == "Limit"
    assert curve.limit == 127
    assert curve.get_level(0) == 0
    assert curve.get_level(255) == 127


def test_get_level_segments():
    curve = SegmentsCurve()
    curve.add_point(2, 0)
    curve.add_point(3, 255)
    assert curve.name == "Segment"
    assert curve.get_level(0) == 0
    assert curve.get_level(3) == 255
    assert curve.get_level(255) == 255


def test_get_level_interpolate():
    curve = InterpolateCurve()
    curve.add_point(70, 40)
    assert curve.name == "Interpolate"
    assert curve.get_level(0) == 0
    assert curve.get_level(40) == 20
    assert curve.get_level(70) == 40
    assert curve.get_level(100) == 64
    assert curve.get_level(255) == 255


def test_set_point_segments():
    curve = SegmentsCurve()
    curve.set_point(0, 0, 255)
    assert curve.get_level(0) == 255
