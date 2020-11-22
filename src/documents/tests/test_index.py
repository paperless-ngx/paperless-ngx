from django.test import TestCase

from documents.index import JsonFormatter


class JsonFormatterTest(TestCase):

    def setUp(self) -> None:
        self.formatter = JsonFormatter()

    def test_empty_fragments(self):
        self.assertListEqual(self.formatter.format([]), [])


