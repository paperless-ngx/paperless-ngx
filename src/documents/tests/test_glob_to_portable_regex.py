import fnmatch
import re

import pytest

from documents.matching import _glob_to_portable_regex


@pytest.mark.parametrize(
    ("pattern", "expected"),
    [
        pytest.param("", r"^$", id="empty"),
        pytest.param("abc", r"^abc$", id="literal"),
        pytest.param("*", r"^.*$", id="star"),
        pytest.param("?", r"^.$", id="question"),
        pytest.param("*.pdf", r"^.*\.pdf$", id="star-escapes-dot"),
        pytest.param("[abc]", r"^[abc]$", id="class"),
        pytest.param("[a-z]", r"^[a-z]$", id="class-range"),
        pytest.param("[!abc]", r"^[^abc]$", id="negated-class"),
        pytest.param("[]a]", r"^[]a]$", id="leading-close-bracket-is-member"),
        pytest.param("[!]a]", r"^[^]a]$", id="negated-leading-close-bracket"),
        pytest.param("[a^b]", r"^[a\^b]$", id="caret-escaped-in-class"),
        pytest.param("[a[b]", r"^[a\[b]$", id="open-bracket-escaped-in-class"),
        pytest.param("[a\\b]", r"^[a\\b]$", id="backslash-escaped-in-class"),
        pytest.param("[abc", r"^\[abc$", id="unclosed-class-literal"),
        pytest.param("[", r"^\[$", id="lone-open-bracket"),
        pytest.param("[!", r"^\[!$", id="unclosed-negation-literal"),
        pytest.param("[]", r"^\[\]$", id="unclosed-with-only-close-bracket"),
        pytest.param("a[0-9]?*", r"^a[0-9]..*$", id="mixed"),
    ],
)
def test_translation(pattern: str, expected: str) -> None:
    """
    GIVEN:
        - A glob pattern
    WHEN:
        - It is translated to a portable regex
    THEN:
        - The exact anchored regex is produced
    """
    assert _glob_to_portable_regex(pattern) == expected


@pytest.mark.parametrize(
    "pattern",
    ["*", "?", "*.pdf", "a?c", "[abc]x", "[!abc]x", "[]a]", "[!]a]", "[a-c]*", "[a"],
)
@pytest.mark.parametrize(
    "name",
    ["", "a", "abc", "x", "]", "]x", "file.pdf", "ax", "bx", "dx", "[a"],
)
def test_agrees_with_fnmatch(pattern: str, name: str) -> None:
    """
    GIVEN:
        - A glob pattern and a name
    WHEN:
        - Matched via the portable regex and via stdlib fnmatch
    THEN:
        - Both agree
    """
    regex = _glob_to_portable_regex(pattern)
    assert bool(re.search(regex, name)) == fnmatch.fnmatchcase(name, pattern)
