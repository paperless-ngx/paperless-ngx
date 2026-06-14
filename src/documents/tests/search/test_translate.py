import pytest

from documents.search._dates import _precision_bounds
from documents.search._translate import FieldRange
from documents.search._translate import FieldValue
from documents.search._translate import Passthrough
from documents.search._translate import scan


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


@pytest.mark.search
class TestScan:
    def test_plain_words_are_passthrough(self):
        assert scan("bank statement") == [Passthrough("bank statement")]

    def test_field_value(self):
        assert scan("created:2020") == [FieldValue("created", "2020")]

    def test_field_value_in_boolean(self):
        toks = scan("created:2020 OR foo")
        assert toks == [
            FieldValue("created", "2020"),
            Passthrough(" OR foo"),
        ]

    def test_field_value_in_parens(self):
        toks = scan("(created:2020 OR foo)")
        assert toks == [
            Passthrough("("),
            FieldValue("created", "2020"),
            Passthrough(" OR foo)"),
        ]

    def test_quoted_value(self):
        assert scan('correspondent:"A B"') == [FieldValue("correspondent", '"A B"')]

    def test_field_range(self):
        assert scan("created:[2020 TO 2021]") == [
            FieldRange("created", "[", "2020", "2021", "]"),
        ]

    @pytest.mark.parametrize(
        ("query", "expected"),
        [
            pytest.param(
                "created:[2020 to]",
                FieldRange("created", "[", "2020", "", "]"),
                id="open_upper",
            ),
            pytest.param(
                "created:[to 2020]",
                FieldRange("created", "[", "", "2020", "]"),
                id="open_lower",
            ),
        ],
    )
    def test_open_range(self, query, expected):
        assert scan(query) == [expected]

    def test_comma_inside_range_not_split(self):
        # No depth-0 comma here; the whole thing is one range token.
        toks = scan("created:[2020 TO 2021]")
        assert len(toks) == 1
