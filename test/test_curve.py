from curve import LinearCurve, SquareRootCurve, LimitCurve


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
