from unittest import mock

from django.core.checks import ERROR
from django.test import TestCase, override_settings

from paperless_tesseract import check_default_language_available


class TestChecks(TestCase):

    def test_default_language(self):
        msgs = check_default_language_available(None)

    @override_settings(OCR_LANGUAGE="")
    def test_no_language(self):
        msgs = check_default_language_available(None)
        self.assertEqual(len(msgs), 1)
        self.assertTrue(msgs[0].msg.startswith("No OCR language has been specified with PAPERLESS_OCR_LANGUAGE"))

    @override_settings(OCR_LANGUAGE="ita")
    @mock.patch("paperless_tesseract.checks.get_tesseract_langs")
    def test_invalid_language(self, m):
        m.return_value = ["deu", "eng"]
        msgs = check_default_language_available(None)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, ERROR)
