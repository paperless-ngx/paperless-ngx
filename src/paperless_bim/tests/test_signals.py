"""
Verify that paperless_bim registers itself with the consumer pipeline
and that BimDocumentParser is wired up correctly.
"""
from unittest import mock

from django.test import SimpleTestCase

from paperless_bim.parsers import BimDocumentParser
from paperless_bim.signals import bim_consumer_declaration


class SignalsTests(SimpleTestCase):
    def test_declaration_has_parser_and_weight(self):
        declaration = bim_consumer_declaration(None)
        self.assertEqual(declaration["weight"], 20)
        self.assertIn("application/x-step", declaration["mime_types"])
        self.assertEqual(declaration["mime_types"]["application/x-step"], ".ifc")

    def test_get_parser_returns_bim_parser(self):
        from paperless_bim.signals import get_parser

        with mock.patch.object(BimDocumentParser, "__init__", return_value=None):
            parser = get_parser(logging_group=None)
        self.assertIsInstance(parser, BimDocumentParser)
