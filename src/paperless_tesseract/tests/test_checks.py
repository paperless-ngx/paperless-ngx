from unittest import mock

from django.core.checks import ERROR
from django.test import TestCase
from django.test import override_settings

from paperless_tesseract import check_default_language_available


class TestChecks(TestCase):
    def test_default_language(self):
        check_default_language_available(None)

    @override_settings(OCR_LANGUAGE="")
    def test_no_language(self):
        msgs = check_default_language_available(None)
        self.assertEqual(len(msgs), 1)
        self.assertTrue(
            msgs[0].msg.startswith(
                "No OCR language has been specified with PAPERLESS_OCR_LANGUAGE",
            ),
        )

    @override_settings(OCR_LANGUAGE="ita")
    @mock.patch("paperless_tesseract.checks.get_tesseract_langs")
    def test_invalid_language(self, m):
        m.return_value = ["deu", "eng"]
        msgs = check_default_language_available(None)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, ERROR)

    @override_settings(OCR_LANGUAGE="chi_sim")
    @mock.patch("paperless_tesseract.checks.get_tesseract_langs")
    def test_multi_part_language(self, m):
        """
        GIVEN:
            - An OCR language which is multi part (ie chi-sim)
            - The language is correctly formatted
        WHEN:
            - Installed packages are checked
        THEN:
            - No errors are reported
        """
        m.return_value = ["chi_sim", "eng"]

        msgs = check_default_language_available(None)

        self.assertEqual(len(msgs), 0)

    @override_settings(OCR_LANGUAGE="chi-sim")
    @mock.patch("paperless_tesseract.checks.get_tesseract_langs")
    def test_multi_part_language_bad_format(self, m):
        """
        GIVEN:
            - An OCR language which is multi part (ie chi-sim)
            - The language is correctly NOT formatted
        WHEN:
            - Installed packages are checked
        THEN:
            - No errors are reported
        """
        m.return_value = ["chi_sim", "eng"]

        msgs = check_default_language_available(None)

        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].level, ERROR)
