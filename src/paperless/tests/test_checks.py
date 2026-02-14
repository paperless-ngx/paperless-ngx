import os
from pathlib import Path
from unittest import mock

import pytest
from django.test import TestCase
from django.test import override_settings
from pytest_mock import MockerFixture

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless.checks import audit_log_check
from paperless.checks import binaries_check
from paperless.checks import check_deprecated_db_settings
from paperless.checks import debug_mode_check
from paperless.checks import paths_check
from paperless.checks import settings_values_check


class TestChecks(DirectoriesMixin, TestCase):
    def test_binaries(self) -> None:
        self.assertEqual(binaries_check(None), [])

    @override_settings(CONVERT_BINARY="uuuhh")
    def test_binaries_fail(self) -> None:
        self.assertEqual(len(binaries_check(None)), 1)

    def test_paths_check(self) -> None:
        self.assertEqual(paths_check(None), [])

    @override_settings(
        MEDIA_ROOT=Path("uuh"),
        DATA_DIR=Path("whatever"),
        CONSUMPTION_DIR=Path("idontcare"),
    )
    def test_paths_check_dont_exist(self) -> None:
        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3, str(msgs))

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is set but doesn't exist."))

    def test_paths_check_no_access(self) -> None:
        Path(self.dirs.data_dir).chmod(0o000)
        Path(self.dirs.media_dir).chmod(0o000)
        Path(self.dirs.consumption_dir).chmod(0o000)

        self.addCleanup(os.chmod, self.dirs.data_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.media_dir, 0o777)
        self.addCleanup(os.chmod, self.dirs.consumption_dir, 0o777)

        msgs = paths_check(None)
        self.assertEqual(len(msgs), 3)

        for msg in msgs:
            self.assertTrue(msg.msg.endswith("is not writeable"))

    @override_settings(DEBUG=False)
    def test_debug_disabled(self) -> None:
        self.assertEqual(debug_mode_check(None), [])

    @override_settings(DEBUG=True)
    def test_debug_enabled(self) -> None:
        self.assertEqual(len(debug_mode_check(None)), 1)


class TestSettingsChecksAgainstDefaults(DirectoriesMixin, TestCase):
    def test_all_valid(self) -> None:
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


class TestOcrSettingsChecks(DirectoriesMixin, TestCase):
    @override_settings(OCR_OUTPUT_TYPE="notapdf")
    def test_invalid_output_type(self) -> None:
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
    def test_invalid_ocr_type(self) -> None:
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
    def test_deprecated_ocr_type(self) -> None:
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
    def test_invalid_ocr_skip_archive_file(self) -> None:
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
    def test_invalid_ocr_clean(self) -> None:
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


class TestTimezoneSettingsChecks(DirectoriesMixin, TestCase):
    @override_settings(TIME_ZONE="TheMoon\\MyCrater")
    def test_invalid_timezone(self) -> None:
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


class TestEmailCertSettingsChecks(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    @override_settings(EMAIL_CERTIFICATE_FILE=Path("/tmp/not_actually_here.pem"))
    def test_not_valid_file(self) -> None:
        """
        GIVEN:
            - Default settings
            - Email certificate is set
        WHEN:
            - Email certificate file doesn't exist
        THEN:
            - system check error reported for email certificate
        """
        self.assertIsNotFile("/tmp/not_actually_here.pem")

        msgs = settings_values_check(None)

        self.assertEqual(len(msgs), 1)

        msg = msgs[0]

        self.assertIn("Email cert /tmp/not_actually_here.pem is not a file", msg.msg)


class TestAuditLogChecks(TestCase):
    def test_was_enabled_once(self) -> None:
        """
        GIVEN:
            - Audit log is not enabled
        WHEN:
            - Database tables contain audit log entry
        THEN:
            - system check error reported for disabling audit log
        """
        introspect_mock = mock.MagicMock()
        introspect_mock.introspection.table_names.return_value = ["auditlog_logentry"]
        with override_settings(AUDIT_LOG_ENABLED=False):
            with mock.patch.dict(
                "paperless.checks.connections",
                {"default": introspect_mock},
            ):
                msgs = audit_log_check(None)

                self.assertEqual(len(msgs), 1)

                msg = msgs[0]

                self.assertIn(
                    ("auditlog table was found but audit log is disabled."),
                    msg.msg,
                )


class TestDeprecatedDbSettings:
    """Test suite for deprecated database settings system check."""

    def test_no_deprecated_vars_no_warning(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that no warning is raised when no deprecated vars are set."""
        mocker.patch.dict(os.environ, {}, clear=True)

        warnings = check_deprecated_db_settings(None)
        assert warnings == []

    @pytest.mark.parametrize(
        ("env_var", "expected_hint_fragment"),
        [
            ("PAPERLESS_DB_TIMEOUT", "timeout"),
            ("PAPERLESS_DB_POOLSIZE", "pool.min_size,pool.max_size"),
            ("PAPERLESS_DBSSLMODE", "sslmode"),
            ("PAPERLESS_DBSSLROOTCERT", "sslrootcert"),
            ("PAPERLESS_DBSSLCERT", "sslcert"),
            ("PAPERLESS_DBSSLKEY", "sslkey"),
        ],
    )
    def test_deprecated_var_triggers_warning(
        self,
        mocker: MockerFixture,
        env_var: str,
        expected_hint_fragment: str,
    ) -> None:
        """Test that each deprecated var triggers appropriate warning."""
        mocker.patch.dict(os.environ, {env_var: "some_value"}, clear=True)

        warnings = check_deprecated_db_settings(None)

        assert len(warnings) == 1
        assert warnings[0].id == "paperless.W001"
        assert env_var in warnings[0].hint
        assert expected_hint_fragment in warnings[0].hint
        assert "v3.2" in warnings[0].hint

    def test_multiple_deprecated_vars(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Test that multiple deprecated vars are all listed in warning."""
        mocker.patch.dict(
            os.environ,
            {
                "PAPERLESS_DB_TIMEOUT": "30",
                "PAPERLESS_DB_POOLSIZE": "10",
                "PAPERLESS_DBSSLMODE": "require",
            },
            clear=True,
        )

        warnings = check_deprecated_db_settings(None)

        assert len(warnings) == 1
        assert "PAPERLESS_DB_TIMEOUT" in warnings[0].hint
        assert "PAPERLESS_DB_POOLSIZE" in warnings[0].hint
        assert "PAPERLESS_DBSSLMODE" in warnings[0].hint
