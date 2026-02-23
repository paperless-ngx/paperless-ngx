import os
from pathlib import Path
from unittest import mock

import pytest
from django.core.checks import Warning
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


DEPRECATED_VARS: dict[str, str] = {
    "PAPERLESS_DB_TIMEOUT": "timeout",
    "PAPERLESS_DB_POOLSIZE": "pool.min_size / pool.max_size",
    "PAPERLESS_DBSSLMODE": "sslmode",
    "PAPERLESS_DBSSLROOTCERT": "sslrootcert",
    "PAPERLESS_DBSSLCERT": "sslcert",
    "PAPERLESS_DBSSLKEY": "sslkey",
}


class TestDeprecatedDbSettings:
    """Test suite for the check_deprecated_db_settings system check."""

    def test_no_deprecated_vars_returns_empty(
        self,
        mocker: MockerFixture,
    ) -> None:
        """No warnings when none of the deprecated vars are present."""
        # clear=True ensures vars from the outer test environment do not leak in
        mocker.patch.dict(os.environ, {}, clear=True)
        result = check_deprecated_db_settings(None)
        assert result == []

    @pytest.mark.parametrize(
        ("env_var", "db_option_key"),
        [
            ("PAPERLESS_DB_TIMEOUT", "timeout"),
            ("PAPERLESS_DB_POOLSIZE", "pool.min_size / pool.max_size"),
            ("PAPERLESS_DBSSLMODE", "sslmode"),
            ("PAPERLESS_DBSSLROOTCERT", "sslrootcert"),
            ("PAPERLESS_DBSSLCERT", "sslcert"),
            ("PAPERLESS_DBSSLKEY", "sslkey"),
        ],
        ids=[
            "db-timeout",
            "db-poolsize",
            "ssl-mode",
            "ssl-rootcert",
            "ssl-cert",
            "ssl-key",
        ],
    )
    def test_single_deprecated_var_produces_one_warning(
        self,
        mocker: MockerFixture,
        env_var: str,
        db_option_key: str,
    ) -> None:
        """Each deprecated var in isolation produces exactly one warning."""
        mocker.patch.dict(os.environ, {env_var: "some_value"}, clear=True)
        result = check_deprecated_db_settings(None)

        assert len(result) == 1
        warning = result[0]
        assert isinstance(warning, Warning)
        assert warning.id == "paperless.W001"
        assert env_var in warning.hint
        assert db_option_key in warning.hint

    def test_multiple_deprecated_vars_produce_one_warning_each(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Each deprecated var present in the environment gets its own warning."""
        set_vars = {
            "PAPERLESS_DB_TIMEOUT": "30",
            "PAPERLESS_DB_POOLSIZE": "10",
            "PAPERLESS_DBSSLMODE": "require",
        }
        mocker.patch.dict(os.environ, set_vars, clear=True)
        result = check_deprecated_db_settings(None)

        assert len(result) == len(set_vars)
        assert all(isinstance(w, Warning) for w in result)
        assert all(w.id == "paperless.W001" for w in result)
        all_hints = " ".join(w.hint for w in result)
        for var_name in set_vars:
            assert var_name in all_hints

    def test_all_deprecated_vars_produces_one_warning_each(
        self,
        mocker: MockerFixture,
    ) -> None:
        """All deprecated vars set simultaneously produces one warning per var."""
        all_vars = {var: "some_value" for var in DEPRECATED_VARS}
        mocker.patch.dict(os.environ, all_vars, clear=True)
        result = check_deprecated_db_settings(None)

        assert len(result) == len(DEPRECATED_VARS)
        assert all(isinstance(w, Warning) for w in result)
        assert all(w.id == "paperless.W001" for w in result)

    def test_unset_vars_not_mentioned_in_warnings(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Vars absent from the environment do not appear in any warning."""
        mocker.patch.dict(
            os.environ,
            {"PAPERLESS_DB_TIMEOUT": "30"},
            clear=True,
        )
        result = check_deprecated_db_settings(None)

        assert len(result) == 1
        assert "PAPERLESS_DB_TIMEOUT" in result[0].hint
        unset_vars = [v for v in DEPRECATED_VARS if v != "PAPERLESS_DB_TIMEOUT"]
        for var_name in unset_vars:
            assert var_name not in result[0].hint

    def test_empty_string_var_not_treated_as_set(
        self,
        mocker: MockerFixture,
    ) -> None:
        """A var set to an empty string is not flagged as a deprecated setting."""
        mocker.patch.dict(
            os.environ,
            {"PAPERLESS_DB_TIMEOUT": ""},
            clear=True,
        )
        result = check_deprecated_db_settings(None)
        assert result == []

    def test_warning_mentions_migration_target(
        self,
        mocker: MockerFixture,
    ) -> None:
        """Each warning hints at PAPERLESS_DB_OPTIONS as the migration target."""
        mocker.patch.dict(
            os.environ,
            {"PAPERLESS_DBSSLMODE": "require"},
            clear=True,
        )
        result = check_deprecated_db_settings(None)

        assert len(result) == 1
        assert "PAPERLESS_DB_OPTIONS" in result[0].hint

    def test_warning_message_identifies_var(
        self,
        mocker: MockerFixture,
    ) -> None:
        """The warning message (not just the hint) identifies the offending var."""
        mocker.patch.dict(
            os.environ,
            {"PAPERLESS_DBSSLCERT": "/path/to/cert.pem"},
            clear=True,
        )
        result = check_deprecated_db_settings(None)

        assert len(result) == 1
        assert "PAPERLESS_DBSSLCERT" in result[0].msg
