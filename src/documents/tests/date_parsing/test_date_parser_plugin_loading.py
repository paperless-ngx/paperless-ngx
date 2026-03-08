import datetime
import logging
from collections.abc import Iterator
from importlib.metadata import EntryPoint

import pytest
import pytest_mock
from django.utils import timezone

from documents.plugins.date_parsing import DATE_PARSER_ENTRY_POINT_GROUP
from documents.plugins.date_parsing import _discover_parser_class
from documents.plugins.date_parsing import get_date_parser
from documents.plugins.date_parsing.base import DateParserConfig
from documents.plugins.date_parsing.base import DateParserPluginBase
from documents.plugins.date_parsing.regex_parser import RegexDateParserPlugin


class AlphaParser(DateParserPluginBase):
    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        yield timezone.now()


class BetaParser(DateParserPluginBase):
    def parse(self, filename: str, content: str) -> Iterator[datetime.datetime]:
        yield timezone.now()


@pytest.mark.date_parsing
@pytest.mark.usefixtures("clear_lru_cache")
class TestDiscoverParserClass:
    """Tests for the _discover_parser_class() function."""

    def test_returns_default_when_no_plugins_found(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(),
        )
        result = _discover_parser_class()
        assert result is RegexDateParserPlugin

    def test_returns_default_when_entrypoint_query_fails(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            side_effect=RuntimeError("boom"),
        )
        result = _discover_parser_class()
        assert result is RegexDateParserPlugin
        assert "Could not query entry points" in caplog.text

    def test_filters_out_invalid_plugins(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_ep = mocker.MagicMock(spec=EntryPoint)
        fake_ep.name = "bad_plugin"
        fake_ep.load.return_value = object  # not subclass of DateParser

        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(fake_ep,),
        )

        result = _discover_parser_class()
        assert result is RegexDateParserPlugin
        assert "does not subclass DateParser" in caplog.text

    def test_skips_plugins_that_fail_to_load(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_ep = mocker.MagicMock(spec=EntryPoint)
        fake_ep.name = "failing_plugin"
        fake_ep.load.side_effect = ImportError("cannot import")

        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(fake_ep,),
        )

        result = _discover_parser_class()
        assert result is RegexDateParserPlugin
        assert "Unable to load date parser plugin failing_plugin" in caplog.text

    def test_returns_single_valid_plugin_without_warning(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """If exactly one valid plugin is discovered, it should be returned without logging a warning."""

        ep = mocker.MagicMock(spec=EntryPoint)
        ep.name = "alpha"
        ep.load.return_value = AlphaParser

        mock_entry_points = mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(ep,),
        )

        with caplog.at_level(
            logging.WARNING,
            logger="documents.plugins.date_parsing",
        ):
            result = _discover_parser_class()

        # It should have called entry_points with the correct group
        mock_entry_points.assert_called_once_with(group=DATE_PARSER_ENTRY_POINT_GROUP)

        # The discovered class should be exactly our AlphaParser
        assert result is AlphaParser

        # No warnings should have been logged
        assert not any(
            "Multiple date parsers found" in record.message for record in caplog.records
        ), "Unexpected warning logged when only one plugin was found"

    def test_returns_first_valid_plugin_by_name(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        ep_a = mocker.MagicMock(spec=EntryPoint)
        ep_a.name = "alpha"
        ep_a.load.return_value = AlphaParser

        ep_b = mocker.MagicMock(spec=EntryPoint)
        ep_b.name = "beta"
        ep_b.load.return_value = BetaParser

        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(ep_b, ep_a),
        )

        result = _discover_parser_class()
        assert result is AlphaParser

    def test_logs_warning_if_multiple_plugins_found(
        self,
        mocker: pytest_mock.MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        ep1 = mocker.MagicMock(spec=EntryPoint)
        ep1.name = "a"
        ep1.load.return_value = AlphaParser

        ep2 = mocker.MagicMock(spec=EntryPoint)
        ep2.name = "b"
        ep2.load.return_value = BetaParser

        mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(ep1, ep2),
        )

        with caplog.at_level(
            logging.WARNING,
            logger="documents.plugins.date_parsing",
        ):
            result = _discover_parser_class()

        # Should select alphabetically first plugin ("a")
        assert result is AlphaParser

        # Should log a warning mentioning multiple parsers
        assert any(
            "Multiple date parsers found" in record.message for record in caplog.records
        ), "Expected a warning about multiple date parsers"

    def test_cache_behavior_only_runs_once(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mock_entry_points = mocker.patch(
            "documents.plugins.date_parsing.entry_points",
            return_value=(),
        )

        # First call populates cache
        _discover_parser_class()
        # Second call should not re-invoke entry_points
        _discover_parser_class()
        mock_entry_points.assert_called_once()


@pytest.mark.django_db
@pytest.mark.date_parsing
@pytest.mark.usefixtures("mock_date_parser_settings")
class TestGetDateParser:
    """Tests for the get_date_parser() factory function."""

    def test_returns_instance_of_discovered_class(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "documents.plugins.date_parsing._discover_parser_class",
            return_value=AlphaParser,
        )
        parser = get_date_parser()
        assert isinstance(parser, AlphaParser)
        assert isinstance(parser.config, DateParserConfig)
        assert parser.config.languages == ["en", "de"]
        assert parser.config.timezone_str == "UTC"
        assert parser.config.ignore_dates == [datetime.date(1900, 1, 1)]
        assert parser.config.filename_date_order == "YMD"
        assert parser.config.content_date_order == "DMY"
        # Check reference_time near now
        delta = abs((parser.config.reference_time - timezone.now()).total_seconds())
        assert delta < 2

    def test_uses_default_regex_parser_when_no_plugins(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        mocker.patch(
            "documents.plugins.date_parsing._discover_parser_class",
            return_value=RegexDateParserPlugin,
        )
        parser = get_date_parser()
        assert isinstance(parser, RegexDateParserPlugin)
