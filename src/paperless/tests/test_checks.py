import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from django.core.checks import Error
from django.core.checks import Warning
from pytest_django.fixtures import SettingsWrapper
from pytest_mock import MockerFixture

from paperless.checks import audit_log_check
from paperless.checks import binaries_check
from paperless.checks import check_deprecated_db_settings
from paperless.checks import check_v3_minimum_upgrade_version
from paperless.checks import debug_mode_check
from paperless.checks import paths_check
from paperless.checks import settings_values_check


@dataclass(frozen=True, slots=True)
class PaperlessTestDirs:
    data_dir: Path
    media_dir: Path
    consumption_dir: Path


# TODO: consolidate with documents/tests/conftest.py PaperlessDirs/paperless_dirs
#       once the paperless and documents test suites are ready to share fixtures.
@pytest.fixture()
def directories(tmp_path: Path, settings: SettingsWrapper) -> PaperlessTestDirs:
    data_dir = tmp_path / "data"
    media_dir = tmp_path / "media"
    consumption_dir = tmp_path / "consumption"

    for d in (data_dir, media_dir, consumption_dir):
        d.mkdir()

    settings.DATA_DIR = data_dir
    settings.MEDIA_ROOT = media_dir
    settings.CONSUMPTION_DIR = consumption_dir

    return PaperlessTestDirs(
        data_dir=data_dir,
        media_dir=media_dir,
        consumption_dir=consumption_dir,
    )


class TestChecks:
    def test_binaries(self) -> None:
        assert binaries_check(None) == []

    def test_binaries_fail(self, settings: SettingsWrapper) -> None:
        settings.CONVERT_BINARY = "uuuhh"
        assert len(binaries_check(None)) == 1

    @pytest.mark.usefixtures("directories")
    def test_paths_check(self) -> None:
        assert paths_check(None) == []

    def test_paths_check_dont_exist(self, settings: SettingsWrapper) -> None:
        settings.MEDIA_ROOT = Path("uuh")
        settings.DATA_DIR = Path("whatever")
        settings.CONSUMPTION_DIR = Path("idontcare")

        msgs = paths_check(None)

        assert len(msgs) == 3, str(msgs)
        for msg in msgs:
            assert msg.msg.endswith("is set but doesn't exist.")

    def test_paths_check_no_access(self, directories: PaperlessTestDirs) -> None:
        directories.data_dir.chmod(0o000)
        directories.media_dir.chmod(0o000)
        directories.consumption_dir.chmod(0o000)

        try:
            msgs = paths_check(None)
        finally:
            directories.data_dir.chmod(0o777)
            directories.media_dir.chmod(0o777)
            directories.consumption_dir.chmod(0o777)

        assert len(msgs) == 3
        for msg in msgs:
            assert msg.msg.endswith("is not writeable")

    def test_debug_disabled(self, settings: SettingsWrapper) -> None:
        settings.DEBUG = False
        assert debug_mode_check(None) == []

    def test_debug_enabled(self, settings: SettingsWrapper) -> None:
        settings.DEBUG = True
        assert len(debug_mode_check(None)) == 1


class TestSettingsChecksAgainstDefaults:
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
        assert len(msgs) == 0


class TestOcrSettingsChecks:
    @pytest.mark.parametrize(
        ("setting", "value", "expected_msg"),
        [
            pytest.param(
                "OCR_OUTPUT_TYPE",
                "notapdf",
                'OCR output type "notapdf"',
                id="invalid-output-type",
            ),
            pytest.param(
                "OCR_MODE",
                "makeitso",
                'OCR output mode "makeitso"',
                id="invalid-mode",
            ),
            pytest.param(
                "OCR_MODE",
                "skip_noarchive",
                "deprecated",
                id="deprecated-mode",
            ),
            pytest.param(
                "OCR_SKIP_ARCHIVE_FILE",
                "invalid",
                'OCR_SKIP_ARCHIVE_FILE setting "invalid"',
                id="invalid-skip-archive-file",
            ),
            pytest.param(
                "OCR_CLEAN",
                "cleanme",
                'OCR clean mode "cleanme"',
                id="invalid-clean",
            ),
        ],
    )
    def test_invalid_setting_produces_one_error(
        self,
        settings: SettingsWrapper,
        setting: str,
        value: str,
        expected_msg: str,
    ) -> None:
        """
        GIVEN:
            - Default settings
            - One OCR setting is set to an invalid value
        WHEN:
            - Settings are validated
        THEN:
            - Exactly one system check error is reported containing the expected message
        """
        setattr(settings, setting, value)

        msgs = settings_values_check(None)

        assert len(msgs) == 1
        assert expected_msg in msgs[0].msg


class TestTimezoneSettingsChecks:
    def test_invalid_timezone(self, settings: SettingsWrapper) -> None:
        """
        GIVEN:
            - Default settings
            - Timezone is invalid
        WHEN:
            - Settings are validated
        THEN:
            - system check error reported for timezone
        """
        settings.TIME_ZONE = "TheMoon\\MyCrater"

        msgs = settings_values_check(None)

        assert len(msgs) == 1
        assert 'Timezone "TheMoon\\MyCrater"' in msgs[0].msg


class TestEmailCertSettingsChecks:
    def test_not_valid_file(self, settings: SettingsWrapper) -> None:
        """
        GIVEN:
            - Default settings
            - Email certificate is set
        WHEN:
            - Email certificate file doesn't exist
        THEN:
            - system check error reported for email certificate
        """
        cert_path = Path("/tmp/not_actually_here.pem")
        assert not cert_path.is_file()
        settings.EMAIL_CERTIFICATE_FILE = cert_path

        msgs = settings_values_check(None)

        assert len(msgs) == 1
        assert "Email cert /tmp/not_actually_here.pem is not a file" in msgs[0].msg


class TestAuditLogChecks:
    def test_was_enabled_once(
        self,
        settings: SettingsWrapper,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - Audit log is not enabled
        WHEN:
            - Database tables contain audit log entry
        THEN:
            - system check error reported for disabling audit log
        """
        settings.AUDIT_LOG_ENABLED = False
        introspect_mock = mocker.MagicMock()
        introspect_mock.introspection.table_names.return_value = ["auditlog_logentry"]
        mocker.patch.dict(
            "paperless.checks.connections",
            {"default": introspect_mock},
        )

        msgs = audit_log_check(None)

        assert len(msgs) == 1
        assert "auditlog table was found but audit log is disabled." in msgs[0].msg


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
            pytest.param("PAPERLESS_DB_TIMEOUT", "timeout", id="db-timeout"),
            pytest.param(
                "PAPERLESS_DB_POOLSIZE",
                "pool.min_size / pool.max_size",
                id="db-poolsize",
            ),
            pytest.param("PAPERLESS_DBSSLMODE", "sslmode", id="ssl-mode"),
            pytest.param("PAPERLESS_DBSSLROOTCERT", "sslrootcert", id="ssl-rootcert"),
            pytest.param("PAPERLESS_DBSSLCERT", "sslcert", id="ssl-cert"),
            pytest.param("PAPERLESS_DBSSLKEY", "sslkey", id="ssl-key"),
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
        all_vars = dict.fromkeys(DEPRECATED_VARS, "some_value")
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


class TestV3MinimumUpgradeVersionCheck:
    """Test suite for check_v3_minimum_upgrade_version system check."""

    @pytest.fixture
    def build_conn_mock(self, mocker: MockerFixture):
        """Factory fixture that builds a connections['default'] mock.

        Usage::

            conn = build_conn_mock(tables=["django_migrations"], applied=["1075_..."])
        """

        def _build(tables: list[str], applied: list[str]) -> mock.MagicMock:
            conn = mocker.MagicMock()
            conn.introspection.table_names.return_value = tables
            cursor = conn.cursor.return_value.__enter__.return_value
            cursor.fetchall.return_value = [(name,) for name in applied]
            return conn

        return _build

    def test_no_migrations_table_fresh_install(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - No django_migrations table exists in the database
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No errors are reported (fresh install, nothing to enforce)
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {"default": build_conn_mock([], [])},
        )
        assert check_v3_minimum_upgrade_version(None) == []

    def test_no_documents_migrations_fresh_install(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - django_migrations table exists but has no documents app rows
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No errors are reported (fresh install, nothing to enforce)
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {"default": build_conn_mock(["django_migrations"], [])},
        )
        assert check_v3_minimum_upgrade_version(None) == []

    def test_v3_state_with_0001_squashed(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - 0001_squashed is recorded in django_migrations
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No errors are reported (DB is already in a valid v3 state)
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {
                "default": build_conn_mock(
                    ["django_migrations"],
                    ["0001_squashed", "0002_squashed", "0003_workflowaction_order"],
                ),
            },
        )
        assert check_v3_minimum_upgrade_version(None) == []

    def test_v3_state_with_0002_squashed_only(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - Only 0002_squashed is recorded in django_migrations
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No errors are reported (0002_squashed alone confirms a valid v3 state)
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {"default": build_conn_mock(["django_migrations"], ["0002_squashed"])},
        )
        assert check_v3_minimum_upgrade_version(None) == []

    def test_v2_20_9_state_ready_to_upgrade(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - 1075_workflowaction_order (the last v2.20.9 migration) is in the DB
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No errors are reported (squash will pick up cleanly from this state)
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {
                "default": build_conn_mock(
                    ["django_migrations"],
                    [
                        "1074_workflowrun_deleted_at_workflowrun_restored_at_and_more",
                        "1075_workflowaction_order",
                    ],
                ),
            },
        )
        assert check_v3_minimum_upgrade_version(None) == []

    def test_v2_20_8_raises_error(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - 1074 (last v2.20.8 migration) is applied but 1075 is not
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - An Error with id paperless.E002 is returned
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {
                "default": build_conn_mock(
                    ["django_migrations"],
                    ["1074_workflowrun_deleted_at_workflowrun_restored_at_and_more"],
                ),
            },
        )
        result = check_v3_minimum_upgrade_version(None)
        assert len(result) == 1
        assert isinstance(result[0], Error)
        assert result[0].id == "paperless.E002"

    def test_very_old_version_raises_error(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - Only old migrations (well below v2.20.9) are applied
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - An Error with id paperless.E002 is returned
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {
                "default": build_conn_mock(
                    ["django_migrations"],
                    ["1000_update_paperless_all", "1022_paperlesstask"],
                ),
            },
        )
        result = check_v3_minimum_upgrade_version(None)
        assert len(result) == 1
        assert isinstance(result[0], Error)
        assert result[0].id == "paperless.E002"

    def test_error_hint_mentions_v2_20_9(
        self,
        mocker: MockerFixture,
        build_conn_mock,
    ) -> None:
        """
        GIVEN:
            - DB is on an old v2 version (pre-v2.20.9)
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - The error hint explicitly references v2.20.9 so users know what to do
        """
        mocker.patch.dict(
            "paperless.checks.connections",
            {"default": build_conn_mock(["django_migrations"], ["1022_paperlesstask"])},
        )
        result = check_v3_minimum_upgrade_version(None)
        assert len(result) == 1
        assert "v2.20.9" in result[0].hint

    def test_db_error_is_swallowed(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - A DatabaseError is raised when querying the DB
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No exception propagates and an empty list is returned
        """
        from django.db import DatabaseError

        conn = mocker.MagicMock()
        conn.introspection.table_names.side_effect = DatabaseError("connection refused")
        mocker.patch.dict("paperless.checks.connections", {"default": conn})
        assert check_v3_minimum_upgrade_version(None) == []

    def test_operational_error_is_swallowed(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - An OperationalError is raised when querying the DB
        WHEN:
            - The v3 upgrade check runs
        THEN:
            - No exception propagates and an empty list is returned
        """
        from django.db import OperationalError

        conn = mocker.MagicMock()
        conn.introspection.table_names.side_effect = OperationalError("DB unavailable")
        mocker.patch.dict("paperless.checks.connections", {"default": conn})
        assert check_v3_minimum_upgrade_version(None) == []
