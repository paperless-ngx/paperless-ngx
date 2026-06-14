import pytest

from documents.search._dates import _precision_bounds


@pytest.mark.search
class TestPrecisionBounds:
    @pytest.mark.parametrize(
        ("digits", "expected"),
        [
            ("2020", ((2020, 1, 1), (2021, 1, 1))),
            ("202003", ((2020, 3, 1), (2020, 4, 1))),
            ("202012", ((2020, 12, 1), (2021, 1, 1))),
            ("20200115", ((2020, 1, 15), (2020, 1, 16))),
            ("20201231", ((2020, 12, 31), (2021, 1, 1))),
        ],
    )
    def test_valid(self, digits, expected):
        lo, hi = _precision_bounds(digits)
        assert (lo.year, lo.month, lo.day) == expected[0]
        assert (hi.year, hi.month, hi.day) == expected[1]

    @pytest.mark.parametrize("digits", ["202023", "20200230", "20201301", "20", "abcd"])
    def test_invalid_returns_none(self, digits):
        assert _precision_bounds(digits) is None
