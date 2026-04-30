import pytest
from django.core.checks import Error
from django.core.checks import Warning
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from documents.checks import filename_format_check
from documents.checks import parser_check


class TestParserCheck:
    def test_returns_empty_when_parsers_present(self) -> None:
        assert parser_check(None) == []

    def test_returns_error_when_no_parsers(self, mocker: MockerFixture) -> None:
        mock_registry = mocker.patch(
            "documents.checks.get_parser_registry",
        ).return_value
        mock_registry.all_parsers.return_value = []

        assert parser_check(None) == [
            Error(
                "No parsers found. This is a bug. The consumer won't be "
                "able to consume any documents without parsers.",
            ),
        ]


class TestFilenameFormatCheck:
    def test_returns_empty_when_unset(self) -> None:
        assert filename_format_check(None) == []

    @pytest.mark.parametrize(
        ("filename_format", "expected_hint"),
        [
            pytest.param(
                "{created}/{title}",
                "{{ created }}/{{ title }}",
                id="created-and-title",
            ),
            pytest.param(
                "{correspondent}",
                "{{ correspondent }}",
                id="correspondent",
            ),
        ],
    )
    def test_warns_on_old_style_format(
        self,
        settings: SettingsWrapper,
        filename_format: str,
        expected_hint: str,
    ) -> None:
        settings.FILENAME_FORMAT = filename_format

        assert filename_format_check(None) == [
            Warning(
                f"Filename format {filename_format} is using the old style, please update to use double curly brackets",
                hint=expected_hint,
            ),
        ]
