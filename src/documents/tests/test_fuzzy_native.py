from __future__ import annotations

import importlib.machinery
import math
import multiprocessing
import random
import string
import sys
from concurrent.futures import ProcessPoolExecutor
from io import StringIO
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import django
import paperless_fuzzy_native
import pytest
import rapidfuzz
from django.core.management import CommandError
from django.core.management import call_command
from rapidfuzz.fuzz import ratio as reference_ratio
from rapidfuzz.utils import default_process as reference_process

from documents.fuzzy import NativeFuzzyError
from documents.fuzzy import native_backend
from documents.fuzzy import process_and_ratio
from documents.management.commands.base import ProcessResult
from documents.management.commands.document_fuzzy_match import Command
from documents.management.commands.document_fuzzy_match import _process_and_match
from documents.management.commands.document_fuzzy_match import _WorkPackage
from documents.models import Document
from paperless_testing.factories import DocumentFactory

if TYPE_CHECKING:
    from collections.abc import Iterator

TEXTS = [
    "",
    " \t\n\r\u00a0\u2003",
    "!!!___---",
    "Hello, WORLD!",
    "A--B",
    "Straße STRASSE ß ẞ",
    "İ I \u0131 ΟΣ ΣΣ",
    "é e\u0301 Å A\u030a",
    "中文１２３ العربية ١٢٣",
    "² Ⅳ ¼ ⑨",
    "😀🚀 🏳️\u200d🌈 x",
    "\U00010400\U00010428\U0001d7ce",
    "\U00011f02\U0001e4d0",  # Newer Unicode letters absent in the reference tables.
    "a\0b\x1fc",
    "invoice line 42\n" * 1500,
]


@pytest.fixture(autouse=True)
def clear_native_cache() -> Iterator[None]:
    assert reference_ratio.__module__.startswith("rapidfuzz.fuzz_cpp")
    assert reference_process.__module__ == "rapidfuzz.utils_cpp"
    native_backend.cache_clear()
    yield
    native_backend.cache_clear()


def reference(first: str, second: str, cutoff: float = 0.0) -> float:
    assert rapidfuzz.__version__ == "3.14.6", "Use the compatibility reference lock"
    return reference_ratio(
        reference_process(first),
        reference_process(second),
        score_cutoff=cutoff,
    )


@pytest.mark.parametrize("text", TEXTS)
def test_normalization(text: str) -> None:
    assert paperless_fuzzy_native.normalize(text) == reference_process(text)


def test_all_unicode_scalars_match_reference() -> None:
    for start in range(0, 0x110000, 4096):
        text = (
            "a"
            + "".join(
                chr(code)
                for code in range(start, min(start + 4096, 0x110000))
                if not 0xD800 <= code <= 0xDFFF
            )
            + "a"
        )
        assert paperless_fuzzy_native.normalize(text) == reference_process(text), (
            f"Normalization mismatch in block U+{start:04X}"
        )


def assert_scores(first: str, second: str) -> None:
    score = reference(first, second)
    for cutoff in {
        0.0,
        85.0,
        100.0,
        score,
        math.nextafter(score, -math.inf),
        math.nextafter(score, math.inf),
        max(0.0, score - 1e-6),
        min(100.0, score + 1e-6),
    }:
        expected = reference(first, second, cutoff)
        actual = process_and_ratio(first, second, cutoff)
        assert actual == pytest.approx(expected, abs=1e-6, rel=0)
        assert (actual >= cutoff) == (expected >= cutoff), (
            first[:100],
            second[:100],
            cutoff,
            expected,
            actual,
        )
        assert (actual == 0.0) == (expected == 0.0)


@pytest.mark.parametrize("first", TEXTS)
def test_curated_pairs_and_cutoffs(first: str) -> None:
    for second in TEXTS:
        assert_scores(first, second)


def test_randomized_pairs_and_cutoffs() -> None:
    rng = random.Random(4004)
    alphabet = string.ascii_letters + string.digits + " ,.-\nİΣßé中文\u0661😀\u0301"
    for _ in range(400):
        first = "".join(rng.choices(alphabet, k=rng.randrange(1, 300)))
        second = "".join(rng.choices(alphabet, k=rng.randrange(1, 300)))
        assert_scores(first, second)
        assert_scores(first, first[:-1] + "x")


def test_worker_preserves_document_ids() -> None:
    result = _process_and_match(_WorkPackage(901, "ABC", 17, "abe", 60.0))
    assert (result.doc_one_pk, result.doc_two_pk) == (901, 17)
    assert result.ratio == reference("ABC", "abe", 60.0)


def test_native_extension_is_executed_without_python_scoring() -> None:
    from paperless_fuzzy_native import _native

    assert any(
        _native.__file__.endswith(suffix)
        for suffix in importlib.machinery.EXTENSION_SUFFIXES
    )
    with (
        patch.object(
            _native,
            "process_and_ratio",
            wraps=_native.process_and_ratio,
        ) as rust,
        patch.object(paperless_fuzzy_native, "process_and_ratio", rust),
        patch("rapidfuzz.fuzz.ratio", side_effect=AssertionError("Python fallback")),
        patch(
            "rapidfuzz.utils.default_process",
            side_effect=AssertionError("Python fallback"),
        ),
    ):
        assert _process_and_match(_WorkPackage(1, "A", 2, "a", 100)).ratio == 100
    rust.assert_called_once_with("A", "a", 100)


@pytest.mark.parametrize("method", multiprocessing.get_all_start_methods())
def test_worker_multiprocessing(method: str) -> None:
    work = [
        _WorkPackage(10, "Invoice İΟΣ", 20, "invoice i\u03bf\u03c3", 85),
        _WorkPackage(10, "abc", 30, "different", 85),
    ]
    with ProcessPoolExecutor(
        max_workers=2,
        mp_context=multiprocessing.get_context(method),
        initializer=django.setup,
    ) as executor:
        results = list(executor.map(_process_and_match, work))
    assert results == [_process_and_match(item) for item in work]


@pytest.mark.parametrize(
    "module",
    [None, SimpleNamespace(API_VERSION=0), SimpleNamespace(API_VERSION=1)],
)
def test_missing_or_incompatible_backend_has_install_hint(
    module: SimpleNamespace | None,
) -> None:
    with patch.dict(sys.modules, {"paperless_fuzzy_native": module}):
        with pytest.raises(NativeFuzzyError, match="uv sync --frozen"):
            native_backend()


def test_native_runtime_error_becomes_command_error() -> None:
    with patch.object(
        paperless_fuzzy_native,
        "process_and_ratio",
        side_effect=RuntimeError("synthetic Rust failure"),
    ):
        with pytest.raises(CommandError, match="Rust fuzzy matching failed"):
            _process_and_match(_WorkPackage(1, "a", 2, "a", 85))


def run_command(**options: Any) -> str:
    stdout = StringIO()
    call_command(
        "document_fuzzy_match",
        no_progress_bar=True,
        stdout=stdout,
        skip_checks=True,
        **options,
    )
    return stdout.getvalue()


@pytest.mark.management
@pytest.mark.django_db(transaction=True)
def test_parallel_command_keeps_deletion_selection() -> None:
    first = DocumentFactory(content="duplicate")
    second = DocumentFactory(content="DUPLICATE!")
    unrelated = DocumentFactory(content="unrelated text")
    output = run_command(processes=2, ratio=100, delete=True, yes=True)
    assert "Found 1 matching pair(s)" in output
    assert set(Document.objects.values_list("pk", flat=True)) == {
        first.pk,
        unrelated.pk,
    }
    assert not Document.objects.filter(pk=second.pk).exists()


@pytest.mark.management
@pytest.mark.django_db
@pytest.mark.parametrize("processes", [1, 2])
def test_failure_never_deletes_partial_matches(processes: int) -> None:
    DocumentFactory(content="same")
    DocumentFactory(content="same")
    work = _WorkPackage(1, "same", 2, "same", 85)
    results = [
        ProcessResult(item=work, result=_process_and_match(work), error=None),
        ProcessResult(
            item=work,
            result=None,
            error=CommandError("Rust fuzzy matching failed"),
        ),
    ]
    with (
        patch.object(Command, "process_parallel", return_value=iter(results)),
        patch(
            "documents.management.commands.document_fuzzy_match.process_and_ratio",
            side_effect=NativeFuzzyError("Rust fuzzy matching failed"),
        ),
        patch("builtins.input") as prompt,
        pytest.raises(CommandError, match="Rust fuzzy matching failed"),
    ):
        run_command(processes=processes, delete=True, yes=True)
    assert Document.objects.count() == 2
    prompt.assert_not_called()


@pytest.mark.management
@pytest.mark.django_db
def test_missing_backend_never_prompts_or_deletes() -> None:
    DocumentFactory(content="same")
    DocumentFactory(content="same")
    with (
        patch.dict(sys.modules, {"paperless_fuzzy_native": None}),
        patch("builtins.input") as prompt,
        pytest.raises(CommandError, match="uv sync --frozen"),
    ):
        run_command(processes=1, delete=True, yes=True)
    assert Document.objects.count() == 2
    prompt.assert_not_called()


@pytest.mark.management
@pytest.mark.django_db
@pytest.mark.parametrize("answer", ["", "n", "yes", " Y "])
def test_confirmation_and_blank_content_are_preserved(answer: str) -> None:
    first = DocumentFactory(content="same")
    second = DocumentFactory(content="same")
    blank = DocumentFactory(content=" \t\n")
    empty = DocumentFactory(content="")
    with patch("builtins.input", return_value=answer) as prompt:
        output = run_command(processes=1, delete=True, ratio=0)
    prompt.assert_called_once()
    assert "Found 1 matching pair(s)" in output
    expected = {first.pk, blank.pk, empty.pk}
    if answer.strip().lower() not in {"y", "yes"}:
        expected.add(second.pk)
        assert "Deletion cancelled" in output
    assert set(Document.objects.values_list("pk", flat=True)) == expected


@pytest.mark.management
@pytest.mark.django_db
@pytest.mark.parametrize("offset", [-1e-6, 0, 1e-6])
def test_command_cutoff_preserves_reference_match_and_deletion(offset: float) -> None:
    first = DocumentFactory(content="abc")
    second = DocumentFactory(content="abe")
    cutoff = reference("abc", "abe") + offset
    output = run_command(processes=1, ratio=cutoff, delete=True, yes=True)
    matched = reference("abc", "abe", cutoff) >= cutoff
    assert Document.objects.filter(pk=first.pk).exists()
    assert Document.objects.filter(pk=second.pk).exists() is not matched
    assert ("Found 1 matching pair(s)" in output) is matched
