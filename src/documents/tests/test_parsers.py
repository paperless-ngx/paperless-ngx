import os
from collections.abc import Generator
from contextlib import contextmanager
from string import ascii_letters
from string import ascii_lowercase
from string import digits
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import override_settings
from hypothesis import example
from hypothesis import given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st
from pytest_django.fixtures import Settings

from documents import parsers as document_parsers
from documents.parsers import get_default_file_extension
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from documents.parsers import is_mime_type_supported
from paperless.parsers.registry import ParserRegistry
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.registry import reset_parser_registry
from paperless.parsers.remote import RemoteDocumentParser
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser

for _profile_name, _max_examples in (
    ("default_pbt04", 100),
    ("dev", 50),
    ("ci", 100),
    ("recorded", 250),
    ("stress", 500),
):
    hypothesis_settings.register_profile(
        _profile_name,
        max_examples=_max_examples,
        deadline=None,
        print_blob=True,
    )
_pbt04_settings = hypothesis_settings.get_profile(
    os.environ.get("HYPOTHESIS_PROFILE", "default_pbt04"),
)


@pytest.fixture()
def _tika_registry(settings: Settings) -> Generator[None, None, None]:
    """
    Rebuild the parser registry with Tika enabled for the duration of the
    test, then reset on exit so other tests see the default (Tika-disabled)
    registry.
    """
    settings.TIKA_ENABLED = True
    reset_parser_registry()
    yield
    reset_parser_registry()


@pytest.mark.django_db
class TestParserAvailability:
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("application/pdf", ".pdf", id="pdf"),
            pytest.param("image/png", ".png", id="png"),
            pytest.param("image/jpeg", ".jpg", id="jpeg"),
            pytest.param("image/tiff", ".tif", id="tiff"),
            pytest.param("image/webp", ".webp", id="webp"),
        ],
    )
    def test_tesseract_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tesseract based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            RasterisedDocumentParser,
        )

    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("text/plain", ".txt", id="plain"),
            pytest.param("text/csv", ".csv", id="csv"),
        ],
    )
    def test_text_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of a text form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The text based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TextDocumentParser,
        )

    @pytest.mark.usefixtures("_tika_registry")
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param(
                "application/vnd.oasis.opendocument.text",
                ".odt",
                id="odt",
            ),
            pytest.param("text/rtf", ".rtf", id="rtf"),
            pytest.param("application/msword", ".doc", id="doc"),
            pytest.param(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
                id="docx",
            ),
        ],
    )
    def test_tika_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of an office document form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tika/Gotenberg based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TikaDocumentParser,
        )

    def test_no_parser_for_mime(self) -> None:
        assert get_parser_registry().get_parser_for_file("text/sdgsdf", "") is None

    def test_default_extension(self) -> None:
        # Test no parser declared still returns an extension
        assert get_default_file_extension("application/zip") == ".zip"

        # Test invalid mimetype returns no extension
        assert get_default_file_extension("aasdasd/dgfgf") == ""

    def test_file_extension_support(self) -> None:
        assert is_file_ext_supported(".pdf")
        assert not is_file_ext_supported(".hsdfh")
        assert not is_file_ext_supported("")


@contextmanager
def _isolated_builtin_registry(*, tika_enabled: bool) -> Generator[None, None, None]:
    """Use built-ins without plugin discovery or remote configuration/DB reads."""
    with override_settings(TIKA_ENABLED=tika_enabled):
        registry = ParserRegistry()
        registry.register_defaults()
        with (
            patch("documents.parsers.get_parser_registry", return_value=registry),
            patch.object(RemoteDocumentParser, "score", return_value=None),
        ):
            yield


def _assert_valid_default_extension(mime: str, extensions: set[str]) -> None:
    ext = get_default_file_extension(mime)
    assert isinstance(ext, str)
    assert ext.startswith(".") and len(ext) >= 2
    assert not any(char.isspace() or char in "/\\" for char in ext)
    assert ext in extensions


_EXTENSION = st.text(ascii_lowercase + digits, min_size=1, max_size=15).map(
    lambda token: "." + token,
)
_MIME = st.text(ascii_lowercase, min_size=1, max_size=12).map(
    lambda token: "application/x-pbt-" + token,
)


@st.composite
def _registry_mappings(draw):
    mappings = draw(
        st.lists(st.dictionaries(_MIME, _EXTENSION, max_size=8), max_size=5),
    )
    mimes = sorted({mime for mapping in mappings for mime in mapping})
    aliases = {mime: draw(st.lists(_EXTENSION, max_size=4)) for mime in mimes}
    return mappings, aliases


class TestMimeExtensionProperties:
    @pytest.mark.parametrize("tika_enabled", [False, True])
    @given(data=st.data())
    @_pbt04_settings
    def test_supported_mime_has_valid_extension(self, tika_enabled, data) -> None:
        with _isolated_builtin_registry(tika_enabled=tika_enabled):
            registry = document_parsers.get_parser_registry()
            mimes = sorted(
                {
                    mime
                    for parser in registry.all_parsers()
                    for mime in parser.supported_mime_types()
                    if is_mime_type_supported(mime)
                },
            )
            assert mimes
            extensions = get_supported_file_extensions()
            _assert_valid_default_extension(
                data.draw(st.sampled_from(mimes), label="supported MIME"),
                extensions,
            )

    @pytest.mark.parametrize("tika_enabled", [False, True])
    def test_all_builtin_mappings(self, tika_enabled) -> None:
        with _isolated_builtin_registry(tika_enabled=tika_enabled):
            registry = document_parsers.get_parser_registry()
            extensions = get_supported_file_extensions()
            mimes = {
                mime
                for parser in registry.all_parsers()
                for mime in parser.supported_mime_types()
            }
            for mime in sorted(mimes):
                if is_mime_type_supported(mime):
                    _assert_valid_default_extension(mime, extensions)
            assert ".docx" in extensions
            assert (
                is_mime_type_supported(
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
                is tika_enabled
            )

    @given(data=st.data())
    @_pbt04_settings
    def test_extension_membership_is_case_insensitive(self, data) -> None:
        with _isolated_builtin_registry(tika_enabled=False):
            extensions = get_supported_file_extensions()
            ext = data.draw(
                st.one_of(
                    st.sampled_from(sorted(extensions)),
                    st.text(ascii_letters + digits + "._- ", max_size=32),
                ),
                label="extension",
            )
            flags = data.draw(
                st.lists(st.booleans(), min_size=len(ext), max_size=len(ext)),
                label="case choices",
            )
            variant = "".join(
                char.upper() if upper else char.lower()
                for char, upper in zip(ext, flags, strict=True)
            )
            expected = bool(ext) and ext.lower() in extensions
            assert is_file_ext_supported(ext) is expected
            assert is_file_ext_supported(variant) is expected

    @given(case=_registry_mappings())
    @example(case=([], {}))
    @example(
        case=(
            [
                {"application/x-pbt-a": ".a"},
                {"application/x-pbt-a": ".a", "application/x-pbt-b": ".b"},
            ],
            {"application/x-pbt-a": [".alias"], "application/x-pbt-b": []},
        ),
    )
    @_pbt04_settings
    def test_registry_extensions_include_defaults_and_aliases(self, case) -> None:
        mappings, aliases = case
        expected = {ext for mapping in mappings for ext in mapping.values()} | {
            ext for values in aliases.values() for ext in values
        }
        parsers = [
            SimpleNamespace(supported_mime_types=lambda mapping=mapping: mapping)
            for mapping in mappings
        ]
        registry = SimpleNamespace(all_parsers=lambda: parsers)
        with (
            patch("documents.parsers.get_parser_registry", return_value=registry),
            patch(
                "documents.parsers.mimetypes.guess_all_extensions",
                side_effect=lambda mime: aliases[mime],
            ),
        ):
            assert get_supported_file_extensions() == expected

    @pytest.mark.parametrize(
        ("ext", "expected"),
        [
            (".PDF", True),
            (".JpEg", True),
            ("", False),
            ("pdf", False),
            (".not-supported-pbt", False),
        ],
    )
    def test_extension_regressions(self, ext, expected) -> None:
        with _isolated_builtin_registry(tika_enabled=False):
            assert is_file_ext_supported(ext) is expected

    def test_fallback_does_not_imply_mime_support(self) -> None:
        with (
            _isolated_builtin_registry(tika_enabled=False),
            patch(
                "documents.parsers.mimetypes.guess_extension",
                side_effect=lambda mime: {"application/zip": ".zip"}.get(mime),
            ),
        ):
            assert not is_mime_type_supported("application/zip")
            assert get_default_file_extension("application/zip") == ".zip"
            assert not is_mime_type_supported("application/x-pbt-unknown")
            assert get_default_file_extension("application/x-pbt-unknown") == ""

    def test_parser_without_mapping_uses_mimetypes_fallback(self) -> None:
        parser = SimpleNamespace(supported_mime_types=dict)
        registry = SimpleNamespace(get_parser_for_file=lambda *_args: parser)
        with (
            patch("documents.parsers.get_parser_registry", return_value=registry),
            patch(
                "documents.parsers.mimetypes.guess_extension",
                return_value=".fallback",
            ),
        ):
            assert get_default_file_extension("application/x-pbt-fallback") == (
                ".fallback"
            )
