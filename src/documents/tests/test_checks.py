from unittest import mock

from django.core.checks import Error
from django.core.checks import Warning
from django.test import TestCase
from django.test import override_settings

from documents.checks import filename_format_check
from documents.checks import parser_check


class TestDocumentChecks(TestCase):
    def test_parser_check(self) -> None:
        self.assertEqual(parser_check(None), [])

        with mock.patch("documents.checks.document_consumer_declaration.send") as m:
            m.return_value = []

            self.assertEqual(
                parser_check(None),
                [
                    Error(
                        "No parsers found. This is a bug. The consumer won't be "
                        "able to consume any documents without parsers.",
                    ),
                ],
            )

    def test_filename_format_check(self) -> None:
        self.assertEqual(filename_format_check(None), [])

        with override_settings(FILENAME_FORMAT="{created}/{title}"):
            self.assertEqual(
                filename_format_check(None),
                [
                    Warning(
                        "Filename format {created}/{title} is using the old style, please update to use double curly brackets",
                        hint="{{ created }}/{{ title }}",
                    ),
                ],
            )
