import os
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import TestCase

from documents.parsers import get_parser_class


def fake_magic_from_file(file, mime=False):

    if mime:
        if os.path.splitext(file)[1] == ".pdf":
            return "application/pdf"
        else:
            return "unknown"
    else:
        return "A verbose string that describes the contents of the file"


@mock.patch("documents.parsers.magic.from_file", fake_magic_from_file)
class TestParserDiscovery(TestCase):

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_1_parser(self, m, *args):
        class DummyParser(object):
            pass

        m.return_value = (
            (None, {"weight": 0, "parser": DummyParser, "mime_types": ["application/pdf"]}),
        )

        self.assertEqual(
            get_parser_class("doc.pdf"),
            DummyParser
        )

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_n_parsers(self, m, *args):

        class DummyParser1(object):
            pass

        class DummyParser2(object):
            pass

        m.return_value = (
            (None, {"weight": 0, "parser": DummyParser1, "mime_types": ["application/pdf"]}),
            (None, {"weight": 1, "parser": DummyParser2, "mime_types": ["application/pdf"]}),
        )

        self.assertEqual(
            get_parser_class("doc.pdf"),
            DummyParser2
        )

    @mock.patch("documents.parsers.document_consumer_declaration.send")
    def test__get_parser_class_0_parsers(self, m, *args):
        m.return_value = []
        with TemporaryDirectory() as tmpdir:
            self.assertIsNone(
                get_parser_class("doc.pdf")
            )
