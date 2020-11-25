import os
import shutil
import tempfile
from tempfile import TemporaryDirectory
from unittest import mock

from django.test import TestCase, override_settings

from documents.parsers import get_parser_class, DocumentParser


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


def fake_get_thumbnail(self, path, mimetype):
    return os.path.join(os.path.dirname(__file__), "examples", "no-text.png")


class TestBaseParser(TestCase):

    def setUp(self) -> None:

        self.scratch = tempfile.mkdtemp()
        override_settings(
            SCRATCH_DIR=self.scratch
        ).enable()

    def tearDown(self) -> None:
        shutil.rmtree(self.scratch)

    @mock.patch("documents.parsers.DocumentParser.get_thumbnail", fake_get_thumbnail)
    def test_get_optimised_thumbnail(self):
        parser = DocumentParser(None)

        parser.get_optimised_thumbnail("any", "not important")

    @mock.patch("documents.parsers.DocumentParser.get_thumbnail", fake_get_thumbnail)
    @override_settings(OPTIMIZE_THUMBNAILS=False)
    def test_get_optimised_thumb_disabled(self):
        parser = DocumentParser(None)

        path = parser.get_optimised_thumbnail("any", "not important")
        self.assertEqual(path, fake_get_thumbnail(None, None, None))

