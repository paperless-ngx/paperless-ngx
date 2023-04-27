import os

from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from paperless.checks import binaries_check
from paperless.checks import debug_mode_check
from paperless.checks import paths_check
from paperless.checks import settings_values_check


class TestChecks(DirectoriesMixin, TestCase):
    def test_binaries(self):
        self.assertEqual(binaries_check(None), [])

    @override_settings(CONVERT_BINARY="uuuhh")
    def test_binaries_fail(self):
        self.assertEqual(len(binaries_check(None)), 1)

    def test_paths_check(self):
        self.assertEqual(paths_check(None), [])

    @override_settings(
        MEDIA_ROOT="uuh",
        DATA_DIR="whatever",
        CONSUMPTION_DIR="idontcare",
    )
    def test_paths_check_dont_exist(self):
        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3, str(msgs))

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is set but doesn't exist."))

    def test_paths_check_no_access(self):
        os.chmod(self.dirs.data_dir, 0o000)
        os.chmod(self.dirs.media_dir, 0o000)
        os.chmod(self.dirs.consumption_dir, 0o000)

        self.addCleanup(os.chmod, self.dirs.data_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.media_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.consumption_dir, 0o777)

        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3)

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is not writeable"))

    @override_settings(DEBUG=False)
    def test_debug_disabled(self):
        self.assertEqual(debug_mode_check(None), [])

    @override_settings(DEBUG=True)
    def test_debug_enabled(self):
        self.assertEqual(len(debug_mode_check(None)), 1)


class TestSettingsChecks(DirectoriesMixin, TestCase):
    def test_all_valid(self):
        """
        GIVEN:
            - Default settings
        WHEN:
            - Settings are validated
        THEN:
            - No system check errors reported
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 0)

    @override_settings(OCR_OUTPUT_TYPE="notapdf")
    def test_invalid_output_type(self):
        """
        GIVEN:
            - Default settings
            - OCR output type is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for OCR output type
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('OCR output type "notapdf"', msg.msg)

    @override_settings(OCR_MODE="makeitso")
    def test_invalid_ocr_type(self):
        """
        GIVEN:
            - Default settings
            - OCR type is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for OCR type
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('OCR output mode "makeitso"', msg.msg)

    @override_settings(OCR_MODE="skip_noarchive")
    def test_deprecated_ocr_type(self):
        """
        GIVEN:
            - Default settings
            - OCR type is deprecated
        WHEN:
            - Settings are validated
        THEN:
            - deprecation warning reported for OCR type
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn("deprecated", msg.msg)

    @override_settings(OCR_SKIP_ARCHIVE_FILE="invalid")
    def test_invalid_ocr_skip_archive_file(self):
        """
        GIVEN:
            - Default settings
            - OCR_SKIP_ARCHIVE_FILE is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for OCR_SKIP_ARCHIVE_FILE
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('OCR_SKIP_ARCHIVE_FILE setting "invalid"', msg.msg)

    @override_settings(OCR_CLEAN="cleanme")
    def test_invalid_ocr_clean(self):
        """
        GIVEN:
            - Default settings
            - OCR cleaning type is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for OCR cleaning type
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('OCR clean mode "cleanme"', msg.msg)

    @override_settings(TIME_ZONE="TheMoon\\MyCrater")
    def test_invalid_timezone(self):
        """
        GIVEN:
            - Default settings
            - Timezone is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for timezone
        """
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('Timezone "TheMoon\\MyCrater"', msg.msg)

    @override_settings(CONSUMER_BARCODE_SCANNER="Invalid")
    def test_barcode_scanner_invalid(self):
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('Invalid Barcode Scanner "Invalid"', msg.msg)

    @override_settings(CONSUMER_BARCODE_SCANNER="")
    def test_barcode_scanner_empty(self):
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn('Invalid Barcode Scanner ""', msg.msg)

    @override_settings(CONSUMER_BARCODE_SCANNER="PYZBAR")
    def test_barcode_scanner_valid(self):
        msgs = settings_values_check(None)
        self.assertEqual(len(msgs), 0)
