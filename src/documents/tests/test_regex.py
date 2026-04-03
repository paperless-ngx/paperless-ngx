import pytest
import regex
from pytest_mock import MockerFixture

from documents.regex import safe_regex_finditer
from documents.regex import safe_regex_match
from documents.regex import safe_regex_search
from documents.regex import safe_regex_sub
from documents.regex import validate_regex_pattern


class TestValidateRegexPattern:
    def test_valid_pattern(self):
        validate_regex_pattern(r"\d+")

    def test_invalid_pattern_raises(self):
        with pytest.raises(ValueError):
            validate_regex_pattern(r"[invalid")


class TestSafeRegexSearchAndMatch:
    """Tests for safe_regex_search and safe_regex_match (same contract)."""

    @pytest.mark.parametrize(
        ("func", "pattern", "text", "expected_group"),
        [
            pytest.param(
                safe_regex_search,
                r"\d+",
                "abc123def",
                "123",
                id="search-match-found",
            ),
            pytest.param(
                safe_regex_match,
                r"\d+",
                "123abc",
                "123",
                id="match-match-found",
            ),
        ],
    )
    def test_match_found(self, func, pattern, text, expected_group):
        result = func(pattern, text)
        assert result is not None
        assert result.group() == expected_group

    @pytest.mark.parametrize(
        ("func", "pattern", "text"),
        [
            pytest.param(safe_regex_search, r"\d+", "abcdef", id="search-no-match"),
            pytest.param(safe_regex_match, r"\d+", "abc123", id="match-no-match"),
        ],
    )
    def test_no_match(self, func, pattern, text):
        assert func(pattern, text) is None

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(safe_regex_search, id="search"),
            pytest.param(safe_regex_match, id="match"),
        ],
    )
    def test_invalid_pattern_returns_none(self, func):
        assert func(r"[invalid", "test") is None

    @pytest.mark.parametrize(
        "func",
        [
            pytest.param(safe_regex_search, id="search"),
            pytest.param(safe_regex_match, id="match"),
        ],
    )
    def test_flags_respected(self, func):
        assert func(r"abc", "ABC", flags=regex.IGNORECASE) is not None

    @pytest.mark.parametrize(
        ("func", "method_name"),
        [
            pytest.param(safe_regex_search, "search", id="search"),
            pytest.param(safe_regex_match, "match", id="match"),
        ],
    )
    def test_timeout_returns_none(self, func, method_name, mocker: MockerFixture):
        mock_compile = mocker.patch("documents.regex.regex.compile")
        getattr(mock_compile.return_value, method_name).side_effect = TimeoutError
        assert func(r"\d+", "test") is None


class TestSafeRegexSub:
    @pytest.mark.parametrize(
        ("pattern", "repl", "text", "expected"),
        [
            pytest.param(r"\d+", "NUM", "abc123def456", "abcNUMdefNUM", id="basic-sub"),
            pytest.param(r"\d+", "NUM", "abcdef", "abcdef", id="no-match"),
            pytest.param(r"abc", "X", "ABC", "X", id="flags"),
        ],
    )
    def test_substitution(self, pattern, repl, text, expected):
        flags = regex.IGNORECASE if pattern == r"abc" else 0
        result = safe_regex_sub(pattern, repl, text, flags=flags)
        assert result == expected

    def test_invalid_pattern_returns_none(self):
        assert safe_regex_sub(r"[invalid", "x", "test") is None

    def test_timeout_returns_none(self, mocker: MockerFixture):
        mock_compile = mocker.patch("documents.regex.regex.compile")
        mock_compile.return_value.sub.side_effect = TimeoutError
        assert safe_regex_sub(r"\d+", "X", "test") is None


class TestSafeRegexFinditer:
    def test_yields_matches(self):
        pattern = regex.compile(r"\d+")
        matches = list(safe_regex_finditer(pattern, "a1b22c333"))
        assert [m.group() for m in matches] == ["1", "22", "333"]

    def test_no_matches(self):
        pattern = regex.compile(r"\d+")
        assert list(safe_regex_finditer(pattern, "abcdef")) == []

    def test_timeout_stops_iteration(self, mocker: MockerFixture):
        mock_pattern = mocker.MagicMock()
        mock_pattern.finditer.side_effect = TimeoutError
        mock_pattern.pattern = r"\d+"
        assert list(safe_regex_finditer(mock_pattern, "test")) == []
