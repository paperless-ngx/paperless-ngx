"""
Tests for :mod:`paperless.parsers` (ParserProtocol) and
:mod:`paperless.parsers.registry` (ParserRegistry + module-level helpers).

All tests use pytest-style functions/classes — no unittest.TestCase.
The ``clean_registry`` fixture ensures complete isolation between tests by
resetting the module-level singleton before and after every test.
"""

from __future__ import annotations

import logging
from importlib.metadata import EntryPoint
from pathlib import Path
from typing import Self
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from paperless.parsers import ParserContext
from paperless.parsers import ParserProtocol
from paperless.parsers.registry import ParserRegistry
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.registry import init_builtin_parsers
from paperless.parsers.registry import reset_parser_registry


@pytest.fixture()
def dummy_parser_cls() -> type:
    """Return a class that fully satisfies :class:`ParserProtocol`.

    GIVEN: A need to exercise registry and Protocol logic with a minimal
           but complete parser.
    WHEN:  A test requests this fixture.
    THEN:  A class with all required attributes and methods is returned.
    """

    class DummyParser:
        name = "dummy-parser"
        version = "0.1.0"
        author = "Test Author"
        url = "https://example.com/dummy-parser"

        @classmethod
        def supported_mime_types(cls) -> dict[str, str]:
            return {"text/plain": ".txt"}

        @classmethod
        def score(
            cls,
            mime_type: str,
            filename: str,
            path: Path | None = None,
        ) -> int | None:
            return 10

        @property
        def can_produce_archive(self) -> bool:
            return False

        @property
        def requires_pdf_rendition(self) -> bool:
            return False

        def parse(
            self,
            document_path: Path,
            mime_type: str,
            *,
            produce_archive: bool = True,
        ) -> None:
            """
            Required to exist, but doesn't need to do anything
            """

        def get_text(self) -> str | None:
            return None

        def get_date(self) -> None:
            return None

        def get_archive_path(self) -> Path | None:
            return None

        def get_thumbnail(
            self,
            document_path: Path,
            mime_type: str,
        ) -> Path:
            return Path("/tmp/thumbnail.webp")

        def get_page_count(
            self,
            document_path: Path,
            mime_type: str,
        ) -> int | None:
            return None

        def extract_metadata(
            self,
            document_path: Path,
            mime_type: str,
        ) -> list:
            return []

        def configure(self, context: ParserContext) -> None:
            """
            Required to exist, but doesn't need to do anything
            """

        def __enter__(self) -> Self:
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            """
            Required to exist, but doesn't need to do anything
            """

    return DummyParser


class TestParserProtocol:
    """Verify runtime isinstance() checks against ParserProtocol."""

    def test_compliant_class_instance_passes_isinstance(
        self,
        dummy_parser_cls: type,
    ) -> None:
        """
        GIVEN: A class that implements every method required by ParserProtocol.
        WHEN:  isinstance() is called with the Protocol.
        THEN:  The check passes (returns True).
        """
        instance = dummy_parser_cls()
        assert isinstance(instance, ParserProtocol)

    def test_non_compliant_class_instance_fails_isinstance(self) -> None:
        """
        GIVEN: A plain class with no parser-related methods.
        WHEN:  isinstance() is called with ParserProtocol.
        THEN:  The check fails (returns False).
        """

        class Unrelated:
            pass

        assert not isinstance(Unrelated(), ParserProtocol)

    @pytest.mark.parametrize(
        "missing_method",
        [
            pytest.param("configure", id="missing-configure"),
            pytest.param("parse", id="missing-parse"),
            pytest.param("get_text", id="missing-get_text"),
            pytest.param("get_thumbnail", id="missing-get_thumbnail"),
            pytest.param("__enter__", id="missing-__enter__"),
            pytest.param("__exit__", id="missing-__exit__"),
        ],
    )
    def test_partial_compliant_fails_isinstance(
        self,
        dummy_parser_cls: type,
        missing_method: str,
    ) -> None:
        """
        GIVEN: A class that satisfies ParserProtocol except for one method.
        WHEN:  isinstance() is called with ParserProtocol.
        THEN:  The check fails because the Protocol is not fully satisfied.
        """
        # Create a subclass and delete the specified method to break compliance.
        partial_cls = type(
            "PartialParser",
            (dummy_parser_cls,),
            {missing_method: None},  # Replace with None — not callable
        )
        assert not isinstance(partial_cls(), ParserProtocol)


class TestRegistrySingleton:
    """Verify the module-level singleton lifecycle functions."""

    def test_get_parser_registry_returns_instance(self) -> None:
        """
        GIVEN: No registry has been created yet.
        WHEN:  get_parser_registry() is called.
        THEN:  A ParserRegistry instance is returned.
        """
        registry = get_parser_registry()
        assert isinstance(registry, ParserRegistry)

    def test_get_parser_registry_same_instance_on_repeated_calls(self) -> None:
        """
        GIVEN: A registry instance was created by a prior call.
        WHEN:  get_parser_registry() is called a second time.
        THEN:  The exact same object (identity) is returned.
        """
        first = get_parser_registry()
        second = get_parser_registry()
        assert first is second

    def test_reset_parser_registry_gives_fresh_instance(self) -> None:
        """
        GIVEN: A registry instance already exists.
        WHEN:  reset_parser_registry() is called and then get_parser_registry()
               is called again.
        THEN:  A new, distinct registry instance is returned.
        """
        first = get_parser_registry()
        reset_parser_registry()
        second = get_parser_registry()
        assert first is not second

    def test_init_builtin_parsers_does_not_run_discover(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        GIVEN: discover() would raise an exception if called.
        WHEN:  init_builtin_parsers() is called.
        THEN:  No exception is raised, confirming discover() was not invoked.
        """

        def exploding_discover(self) -> None:
            raise RuntimeError(
                "discover() must not be called from init_builtin_parsers",
            )

        monkeypatch.setattr(ParserRegistry, "discover", exploding_discover)

        # Should complete without raising.
        init_builtin_parsers()

    def test_init_builtin_parsers_idempotent(self) -> None:
        """
        GIVEN: init_builtin_parsers() has already been called once.
        WHEN:  init_builtin_parsers() is called a second time.
        THEN:  No error is raised and the same registry instance is reused.
        """
        init_builtin_parsers()
        # Capture the registry created by the first call.
        import paperless.parsers.registry as reg_module

        first_registry = reg_module._registry

        init_builtin_parsers()

        assert reg_module._registry is first_registry


class TestParserRegistryGetParserForFile:
    """Verify parser selection logic in get_parser_for_file()."""

    def test_returns_none_when_no_parsers_registered(self) -> None:
        """
        GIVEN: A registry with no parsers registered.
        WHEN:  get_parser_for_file() is called for any MIME type.
        THEN:  None is returned.
        """
        registry = ParserRegistry()
        result = registry.get_parser_for_file("text/plain", "doc.txt")
        assert result is None

    def test_returns_none_for_unsupported_mime_type(
        self,
        dummy_parser_cls: type,
    ) -> None:
        """
        GIVEN: A registry with a parser that supports only 'text/plain'.
        WHEN:  get_parser_for_file() is called with 'application/pdf'.
        THEN:  None is returned.
        """
        registry = ParserRegistry()
        registry.register_builtin(dummy_parser_cls)
        result = registry.get_parser_for_file("application/pdf", "file.pdf")
        assert result is None

    def test_returns_parser_for_supported_mime_type(
        self,
        dummy_parser_cls: type,
    ) -> None:
        """
        GIVEN: A registry with a parser registered for 'text/plain'.
        WHEN:  get_parser_for_file() is called with 'text/plain'.
        THEN:  The registered parser class is returned.
        """
        registry = ParserRegistry()
        registry.register_builtin(dummy_parser_cls)
        result = registry.get_parser_for_file("text/plain", "readme.txt")
        assert result is dummy_parser_cls

    def test_highest_score_wins(self) -> None:
        """
        GIVEN: Two parsers both supporting 'text/plain' with scores 5 and 20.
        WHEN:  get_parser_for_file() is called for 'text/plain'.
        THEN:  The parser with score 20 is returned.
        """

        class LowScoreParser:
            name = "low"
            version = "1.0"
            author = "A"
            url = "https://example.com/low"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 5

        class HighScoreParser:
            name = "high"
            version = "1.0"
            author = "B"
            url = "https://example.com/high"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 20

        registry = ParserRegistry()
        registry.register_builtin(LowScoreParser)
        registry.register_builtin(HighScoreParser)
        result = registry.get_parser_for_file("text/plain", "readme.txt")
        assert result is HighScoreParser

    def test_parser_returning_none_score_is_skipped(self) -> None:
        """
        GIVEN: A parser that returns None from score() for the given file.
        WHEN:  get_parser_for_file() is called.
        THEN:  That parser is skipped and None is returned (no other candidates).
        """

        class DecliningParser:
            name = "declining"
            version = "1.0"
            author = "A"
            url = "https://example.com"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return None  # Explicitly declines

        registry = ParserRegistry()
        registry.register_builtin(DecliningParser)
        result = registry.get_parser_for_file("text/plain", "readme.txt")
        assert result is None

    def test_all_parsers_decline_returns_none(self) -> None:
        """
        GIVEN: Multiple parsers that all return None from score().
        WHEN:  get_parser_for_file() is called.
        THEN:  None is returned.
        """

        class AlwaysDeclines:
            name = "declines"
            version = "1.0"
            author = "A"
            url = "https://example.com"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return None

        registry = ParserRegistry()
        registry.register_builtin(AlwaysDeclines)
        registry._external.append(AlwaysDeclines)
        result = registry.get_parser_for_file("text/plain", "file.txt")
        assert result is None

    def test_external_parser_beats_builtin_same_score(self) -> None:
        """
        GIVEN: An external and a built-in parser both returning score 10.
        WHEN:  get_parser_for_file() is called.
        THEN:  The external parser wins because externals are evaluated first
               and the first-seen-wins policy applies at equal scores.
        """

        class BuiltinParser:
            name = "builtin"
            version = "1.0"
            author = "Core"
            url = "https://example.com/builtin"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 10

        class ExternalParser:
            name = "external"
            version = "2.0"
            author = "Third Party"
            url = "https://example.com/external"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 10

        registry = ParserRegistry()
        registry.register_builtin(BuiltinParser)
        registry._external.append(ExternalParser)
        result = registry.get_parser_for_file("text/plain", "file.txt")
        assert result is ExternalParser

    def test_builtin_wins_when_external_declines(self) -> None:
        """
        GIVEN: An external parser that declines (score None) and a built-in
               that returns score 5.
        WHEN:  get_parser_for_file() is called.
        THEN:  The built-in parser is returned.
        """

        class DecliningExternal:
            name = "declining-external"
            version = "1.0"
            author = "Third Party"
            url = "https://example.com/declining"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return None

        class AcceptingBuiltin:
            name = "accepting-builtin"
            version = "1.0"
            author = "Core"
            url = "https://example.com/accepting"

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 5

        registry = ParserRegistry()
        registry.register_builtin(AcceptingBuiltin)
        registry._external.append(DecliningExternal)
        result = registry.get_parser_for_file("text/plain", "file.txt")
        assert result is AcceptingBuiltin


class TestDiscover:
    """Verify entrypoint discovery in ParserRegistry.discover()."""

    def test_discover_with_no_entrypoints(self) -> None:
        """
        GIVEN: No entrypoints are registered under 'paperless_ngx.parsers'.
        WHEN:  discover() is called.
        THEN:  _external remains empty and no errors are raised.
        """
        registry = ParserRegistry()

        with patch(
            "paperless.parsers.registry.entry_points",
            return_value=[],
        ):
            registry.discover()

        assert registry._external == []

    def test_discover_adds_valid_external_parser(self) -> None:
        """
        GIVEN: One valid entrypoint whose loaded class has all required attrs.
        WHEN:  discover() is called.
        THEN:  The class is appended to _external.
        """

        class ValidExternal:
            name = "valid-external"
            version = "3.0.0"
            author = "Someone"
            url = "https://example.com/valid"

            @classmethod
            def supported_mime_types(cls):
                return {"application/pdf": ".pdf"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 5

        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "valid_external"
        mock_ep.load.return_value = ValidExternal

        registry = ParserRegistry()

        with patch(
            "paperless.parsers.registry.entry_points",
            return_value=[mock_ep],
        ):
            registry.discover()

        assert ValidExternal in registry._external

    def test_discover_skips_entrypoint_with_load_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: An entrypoint whose load() method raises ImportError.
        WHEN:  discover() is called.
        THEN:  The entrypoint is skipped, an error is logged, and _external
               remains empty.
        """
        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "broken_ep"
        mock_ep.load.side_effect = ImportError("missing dependency")

        registry = ParserRegistry()

        with caplog.at_level(logging.ERROR, logger="paperless.parsers.registry"):
            with patch(
                "paperless.parsers.registry.entry_points",
                return_value=[mock_ep],
            ):
                registry.discover()

        assert registry._external == []
        assert any(
            "broken_ep" in record.message
            for record in caplog.records
            if record.levelno >= logging.ERROR
        )

    def test_discover_skips_entrypoint_with_missing_attrs(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: A class loaded from an entrypoint that is missing the 'score'
               attribute.
        WHEN:  discover() is called.
        THEN:  The entrypoint is skipped, a warning is logged, and _external
               remains empty.
        """

        class MissingScore:
            name = "missing-score"
            version = "1.0"
            author = "Someone"
            url = "https://example.com"

            # 'score' classmethod is intentionally absent.

            @classmethod
            def supported_mime_types(cls):
                return {"text/plain": ".txt"}

        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "missing_score_ep"
        mock_ep.load.return_value = MissingScore

        registry = ParserRegistry()

        with caplog.at_level(logging.WARNING, logger="paperless.parsers.registry"):
            with patch(
                "paperless.parsers.registry.entry_points",
                return_value=[mock_ep],
            ):
                registry.discover()

        assert registry._external == []
        assert any(
            "missing_score_ep" in record.message
            for record in caplog.records
            if record.levelno >= logging.WARNING
        )

    def test_discover_logs_loaded_parser_info(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: A valid entrypoint that loads successfully.
        WHEN:  discover() is called.
        THEN:  An INFO log message is emitted containing the parser name,
               version, author, and entrypoint name.
        """

        class LoggableParser:
            name = "loggable"
            version = "4.2.0"
            author = "Log Tester"
            url = "https://example.com/loggable"

            @classmethod
            def supported_mime_types(cls):
                return {"image/png": ".png"}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return 1

        mock_ep = MagicMock(spec=EntryPoint)
        mock_ep.name = "loggable_ep"
        mock_ep.load.return_value = LoggableParser

        registry = ParserRegistry()

        with caplog.at_level(logging.INFO, logger="paperless.parsers.registry"):
            with patch(
                "paperless.parsers.registry.entry_points",
                return_value=[mock_ep],
            ):
                registry.discover()

        info_messages = " ".join(
            r.message for r in caplog.records if r.levelno == logging.INFO
        )
        assert "loggable" in info_messages
        assert "4.2.0" in info_messages
        assert "Log Tester" in info_messages
        assert "loggable_ep" in info_messages


class TestLogSummary:
    """Verify log output from ParserRegistry.log_summary()."""

    def test_log_summary_with_no_external_parsers(
        self,
        dummy_parser_cls: type,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: A registry with one built-in parser and no external parsers.
        WHEN:  log_summary() is called.
        THEN:  The built-in parser name appears in the logs.
        """
        registry = ParserRegistry()
        registry.register_builtin(dummy_parser_cls)

        with caplog.at_level(logging.INFO, logger="paperless.parsers.registry"):
            registry.log_summary()

        all_messages = " ".join(r.message for r in caplog.records)
        assert dummy_parser_cls.name in all_messages

    def test_log_summary_with_external_parsers(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: A registry with one external parser registered.
        WHEN:  log_summary() is called.
        THEN:  The external parser name, version, author, and url appear in
               the log output.
        """

        class ExtParser:
            name = "ext-parser"
            version = "9.9.9"
            author = "Ext Corp"
            url = "https://ext.example.com"

            @classmethod
            def supported_mime_types(cls):
                return {}

            @classmethod
            def score(cls, mime_type, filename, path=None):
                return None

        registry = ParserRegistry()
        registry._external.append(ExtParser)

        with caplog.at_level(logging.INFO, logger="paperless.parsers.registry"):
            registry.log_summary()

        all_messages = " ".join(r.message for r in caplog.records)
        assert "ext-parser" in all_messages
        assert "9.9.9" in all_messages
        assert "Ext Corp" in all_messages
        assert "https://ext.example.com" in all_messages

    def test_log_summary_logs_no_third_party_message_when_none(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN: A registry with no external parsers.
        WHEN:  log_summary() is called.
        THEN:  A message containing 'No third-party parsers discovered.' is
               logged.
        """
        registry = ParserRegistry()

        with caplog.at_level(logging.INFO, logger="paperless.parsers.registry"):
            registry.log_summary()

        all_messages = " ".join(r.message for r in caplog.records)
        assert "No third-party parsers discovered." in all_messages
