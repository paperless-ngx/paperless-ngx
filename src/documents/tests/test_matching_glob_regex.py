import re
from fnmatch import fnmatch

import pytest

from documents.matching import glob_to_database_regex
from documents.models import Document
from paperless_testing.factories import DocumentFactory

NAMES = [
    "invoice.pdf",
    "Invoice.PDF",
    "invoice_2024.pdf",
    "a.b.c",
    "a-b",
    "sample [1].pdf",
    "sample 1.pdf",
    "x^y",
    "back\\slash",
    "dir/file.pdf",
    "",
]

PATTERNS = [
    "*",
    "invoice.pdf",
    "*.pdf",
    "*invoice*pdf",
    "*a*b*c*",
    "invoice_????.pdf",
    "sample [[]1].pdf",
    "sample [1-2].pdf",
    "sample [!2].pdf",
    "sample [^2].pdf",
    "sample [",
    "a.b.c",
    "x^y",
    "back\\slash",
    "[]]",
]


@pytest.mark.parametrize("pattern", PATTERNS)
def test_regex_agrees_with_fnmatch(pattern: str) -> None:
    regex = glob_to_database_regex(pattern)
    for name in NAMES:
        expected = fnmatch(name.lower(), pattern.lower())
        actual = re.search(regex, name, re.IGNORECASE) is not None
        assert actual is expected, f"{pattern!r} vs {name!r}"


@pytest.mark.parametrize("pattern", ["*", "*a*b*c*", "a*b*c*d*e"])
def test_regex_avoids_syntax_postgresql_rejects(pattern: str) -> None:
    regex = glob_to_database_regex(pattern)
    assert not any(marker in regex for marker in ("(?", "\\Z"))


@pytest.mark.django_db
def test_database_filter_matches_glob() -> None:
    matching = DocumentFactory(original_filename="Invoice_2024.PDF")
    DocumentFactory(original_filename="invoice_2024.txt")
    DocumentFactory(original_filename="receipt.pdf")

    found = Document.objects.filter(
        original_filename__iregex=glob_to_database_regex("*invoice*.pdf"),
    )

    assert list(found) == [matching]
