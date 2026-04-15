import datetime
import os
from pathlib import Path
from typing import Any

import pytest
from celery.schedules import crontab
from pytest_mock import MockerFixture

from paperless.settings.custom import parse_beat_schedule
from paperless.settings.custom import parse_dateparser_languages
from paperless.settings.custom import parse_db_settings
from paperless.settings.custom import parse_hosting_settings
from paperless.settings.custom import parse_ignore_dates
from paperless.settings.custom import parse_redis_url


class TestRedisSocketConversion:
    @pytest.mark.parametrize(
        ("input_url", "expected"),
        [
            pytest.param(
                None,
                ("redis://localhost:6379", "redis://localhost:6379"),
                id="none_uses_default",
            ),
            pytest.param(
                "redis+socket:///run/redis/redis.sock",
                (
                    "redis+socket:///run/redis/redis.sock",
                    "unix:///run/redis/redis.sock",
                ),
                id="celery_style_socket",
            ),
            pytest.param(
                "unix:///run/redis/redis.sock",
                (
                    "redis+socket:///run/redis/redis.sock",
                    "unix:///run/redis/redis.sock",
                ),
                id="redis_py_style_socket",
            ),
            pytest.param(
                "redis+socket:///run/redis/redis.sock?virtual_host=5",
                (
                    "redis+socket:///run/redis/redis.sock?virtual_host=5",
                    "unix:///run/redis/redis.sock?db=5",
                ),
                id="celery_style_socket_with_db",
            ),
            pytest.param(
                "unix:///run/redis/redis.sock?db=10",
                (
                    "redis+socket:///run/redis/redis.sock?virtual_host=10",
                    "unix:///run/redis/redis.sock?db=10",
                ),
                id="redis_py_style_socket_with_db",
            ),
            pytest.param(
                "redis://myredishost:6379",
                ("redis://myredishost:6379", "redis://myredishost:6379"),
                id="host_with_port_unchanged",
            ),
            # Credentials in unix:// URL contain multiple colons (user:password@)
            # Regression test for https://github.com/paperless-ngx/paperless-ngx/pull/12239
            pytest.param(
                "unix://user:password@/run/redis/redis.sock",
                (
                    "redis+socket://user:password@/run/redis/redis.sock",
                    "unix://user:password@/run/redis/redis.sock",
                ),
                id="redis_py_style_socket_with_credentials",
            ),
            pytest.param(
                "redis+socket://user:password@/run/redis/redis.sock",
                (
                    "redis+socket://user:password@/run/redis/redis.sock",
                    "unix://user:password@/run/redis/redis.sock",
                ),
                id="celery_style_socket_with_credentials",
            ),
            # Empty username, password only: unix://:SECRET@/path.sock
            pytest.param(
                "unix://:SECRET@/run/redis/paperless.sock",
                (
                    "redis+socket://:SECRET@/run/redis/paperless.sock",
                    "unix://:SECRET@/run/redis/paperless.sock",
                ),
                id="redis_py_style_socket_with_password_only",
            ),
        ],
    )
    def test_redis_socket_parsing(
        self,
        input_url: str | None,
        expected: tuple[str, str],
    ) -> None:
        """
        GIVEN:
            - Various Redis connection URI formats
        WHEN:
            - The URI is parsed
        THEN:
            - Socket based URIs are translated
            - Non-socket URIs are unchanged
            - None provided uses default
        """
        result = parse_redis_url(input_url)
        assert expected == result


class TestParseHostingSettings:
    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            pytest.param(
                {},
                (
                    None,
                    "/",
                    "/accounts/login/",
                    "/dashboard",
                    "/accounts/login/?loggedout=1",
                ),
                id="no_env_vars",
            ),
            pytest.param(
                {"PAPERLESS_FORCE_SCRIPT_NAME": "/paperless"},
                (
                    "/paperless",
                    "/paperless/",
                    "/paperless/accounts/login/",
                    "/paperless/dashboard",
                    "/paperless/accounts/login/?loggedout=1",
                ),
                id="force_script_name_only",
            ),
            pytest.param(
                {
                    "PAPERLESS_FORCE_SCRIPT_NAME": "/docs",
                    "PAPERLESS_LOGOUT_REDIRECT_URL": "/custom/logout",
                },
                (
                    "/docs",
                    "/docs/",
                    "/docs/accounts/login/",
                    "/docs/dashboard",
                    "/custom/logout",
                ),
                id="force_script_name_and_logout_redirect",
            ),
        ],
    )
    def test_parse_hosting_settings(
        self,
        mocker: MockerFixture,
        env: dict[str, str],
        expected: tuple[str | None, str, str, str, str],
    ) -> None:
        """Test parse_hosting_settings with various env configurations."""
        mocker.patch.dict(os.environ, env, clear=True)

        result = parse_hosting_settings()

        assert result == expected


def make_expected_schedule(
    overrides: dict[str, dict[str, Any]] | None = None,
    disabled: set[str] | None = None,
) -> dict[str, Any]:
    """
    Build the expected schedule with optional overrides and disabled tasks.
    """

    mail_expire = 9.0 * 60.0
    classifier_expire = 59.0 * 60.0
    index_expire = 23.0 * 60.0 * 60.0
    sanity_expire = ((7.0 * 24.0) - 1.0) * 60.0 * 60.0
    empty_trash_expire = 23.0 * 60.0 * 60.0
    workflow_expire = 59.0 * 60.0
    llm_index_expire = 23.0 * 60.0 * 60.0
    share_link_cleanup_expire = 23.0 * 60.0 * 60.0

    schedule: dict[str, Any] = {
        "Check all e-mail accounts": {
            "task": "paperless_mail.tasks.process_mail_accounts",
            "schedule": crontab(minute="*/10"),
            "options": {
                "expires": mail_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Train the classifier": {
            "task": "documents.tasks.train_classifier",
            "schedule": crontab(minute="5", hour="*/1"),
            "options": {
                "expires": classifier_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Optimize the index": {
            "task": "documents.tasks.index_optimize",
            "schedule": crontab(minute=0, hour=0),
            "options": {
                "expires": index_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Perform sanity check": {
            "task": "documents.tasks.sanity_check",
            "schedule": crontab(minute=30, hour=0, day_of_week="sun"),
            "options": {
                "expires": sanity_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Empty trash": {
            "task": "documents.tasks.empty_trash",
            "schedule": crontab(minute=0, hour="1"),
            "options": {
                "expires": empty_trash_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Check and run scheduled workflows": {
            "task": "documents.tasks.check_scheduled_workflows",
            "schedule": crontab(minute="5", hour="*/1"),
            "options": {
                "expires": workflow_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Rebuild LLM index": {
            "task": "documents.tasks.llmindex_index",
            "schedule": crontab(minute="10", hour="2"),
            "options": {
                "expires": llm_index_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
        "Cleanup expired share link bundles": {
            "task": "documents.tasks.cleanup_expired_share_link_bundles",
            "schedule": crontab(minute=0, hour="2"),
            "options": {
                "expires": share_link_cleanup_expire,
                "headers": {"trigger_source": "scheduled"},
            },
        },
    }

    overrides = overrides or {}
    disabled = disabled or set()

    for key, val in overrides.items():
        schedule[key] = {**schedule.get(key, {}), **val}

    for key in disabled:
        schedule.pop(key, None)

    return schedule


class TestParseBeatSchedule:
    @pytest.mark.parametrize(
        ("env", "expected"),
        [
            pytest.param({}, make_expected_schedule(), id="defaults"),
            pytest.param(
                {"PAPERLESS_EMAIL_TASK_CRON": "*/50 * * * mon"},
                make_expected_schedule(
                    overrides={
                        "Check all e-mail accounts": {
                            "schedule": crontab(minute="*/50", day_of_week="mon"),
                        },
                    },
                ),
                id="email-changed",
            ),
            pytest.param(
                {"PAPERLESS_INDEX_TASK_CRON": "disable"},
                make_expected_schedule(disabled={"Optimize the index"}),
                id="index-disabled",
            ),
            pytest.param(
                {
                    "PAPERLESS_EMAIL_TASK_CRON": "disable",
                    "PAPERLESS_TRAIN_TASK_CRON": "disable",
                    "PAPERLESS_SANITY_TASK_CRON": "disable",
                    "PAPERLESS_INDEX_TASK_CRON": "disable",
                    "PAPERLESS_EMPTY_TRASH_TASK_CRON": "disable",
                    "PAPERLESS_WORKFLOW_SCHEDULED_TASK_CRON": "disable",
                    "PAPERLESS_LLM_INDEX_TASK_CRON": "disable",
                    "PAPERLESS_SHARE_LINK_BUNDLE_CLEANUP_CRON": "disable",
                },
                {},
                id="all-disabled",
            ),
        ],
    )
    def test_parse_beat_schedule(
        self,
        env: dict[str, str],
        expected: dict[str, Any],
        mocker: MockerFixture,
    ) -> None:
        mocker.patch.dict(os.environ, env, clear=False)
        schedule = parse_beat_schedule()
        assert schedule == expected

    def test_parse_beat_schedule_all_entries_have_trigger_source_header(self) -> None:
        """Every beat entry must carry trigger_source=scheduled so the task signal
        handler can identify scheduler-originated tasks."""
        schedule = parse_beat_schedule()
        for name, entry in schedule.items():
            headers = entry.get("options", {}).get("headers", {})
            assert headers.get("trigger_source") == "scheduled", (
                f"Beat entry '{name}' is missing trigger_source header"
            )


class TestParseDbSettings:
    """Test suite for parse_db_settings function."""

    @pytest.mark.parametrize(
        ("env_vars", "expected_database_settings"),
        [
            pytest.param(
                {},
                {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": None,  # replaced with tmp_path in test body
                        "OPTIONS": {
                            "init_command": (
                                "PRAGMA journal_mode=WAL;"
                                "PRAGMA synchronous=NORMAL;"
                                "PRAGMA busy_timeout=5000;"
                                "PRAGMA temp_store=MEMORY;"
                                "PRAGMA mmap_size=134217728;"
                                "PRAGMA journal_size_limit=67108864;"
                                "PRAGMA cache_size=-8000"
                            ),
                            "transaction_mode": "IMMEDIATE",
                        },
                    },
                },
                id="default-sqlite",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "sqlite",
                    "PAPERLESS_DB_OPTIONS": "timeout=30",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": None,
                        "OPTIONS": {
                            "init_command": (
                                "PRAGMA journal_mode=WAL;"
                                "PRAGMA synchronous=NORMAL;"
                                "PRAGMA busy_timeout=5000;"
                                "PRAGMA temp_store=MEMORY;"
                                "PRAGMA mmap_size=134217728;"
                                "PRAGMA journal_size_limit=67108864;"
                                "PRAGMA cache_size=-8000"
                            ),
                            "transaction_mode": "IMMEDIATE",
                            "timeout": 30,
                        },
                    },
                },
                id="sqlite-with-timeout-override",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "sqlite",
                    "PAPERLESS_DB_OPTIONS": "init_command=PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL,transaction_mode=DEFERRED",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.sqlite3",
                        "NAME": None,
                        "OPTIONS": {
                            "init_command": "PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL",
                            "transaction_mode": "DEFERRED",
                        },
                    },
                },
                id="sqlite-options-override",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "postgresql",
                    "PAPERLESS_DBHOST": "localhost",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.postgresql",
                        "HOST": "localhost",
                        "NAME": "paperless",
                        "USER": "paperless",
                        "PASSWORD": "paperless",
                        "OPTIONS": {
                            "sslmode": "prefer",
                            "sslrootcert": None,
                            "sslcert": None,
                            "sslkey": None,
                            "application_name": "paperless-ngx",
                        },
                    },
                },
                id="postgresql-defaults",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "postgresql",
                    "PAPERLESS_DBHOST": "paperless-db-host",
                    "PAPERLESS_DBPORT": "1111",
                    "PAPERLESS_DBNAME": "customdb",
                    "PAPERLESS_DBUSER": "customuser",
                    "PAPERLESS_DBPASS": "custompass",
                    "PAPERLESS_DB_OPTIONS": "pool.max_size=50,pool.min_size=2,sslmode=require",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.postgresql",
                        "HOST": "paperless-db-host",
                        "PORT": 1111,
                        "NAME": "customdb",
                        "USER": "customuser",
                        "PASSWORD": "custompass",
                        "OPTIONS": {
                            "sslmode": "require",
                            "sslrootcert": None,
                            "sslcert": None,
                            "sslkey": None,
                            "application_name": "paperless-ngx",
                            "pool": {
                                "min_size": 2,
                                "max_size": 50,
                            },
                        },
                    },
                },
                id="postgresql-overrides",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "postgresql",
                    "PAPERLESS_DBHOST": "pghost",
                    "PAPERLESS_DB_POOLSIZE": "10",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.postgresql",
                        "HOST": "pghost",
                        "NAME": "paperless",
                        "USER": "paperless",
                        "PASSWORD": "paperless",
                        "OPTIONS": {
                            "sslmode": "prefer",
                            "sslrootcert": None,
                            "sslcert": None,
                            "sslkey": None,
                            "application_name": "paperless-ngx",
                            "pool": {
                                "min_size": 1,
                                "max_size": 10,
                            },
                        },
                    },
                },
                id="postgresql-legacy-poolsize",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "postgresql",
                    "PAPERLESS_DBHOST": "pghost",
                    "PAPERLESS_DBSSLMODE": "require",
                    "PAPERLESS_DBSSLROOTCERT": "/certs/ca.crt",
                    "PAPERLESS_DB_TIMEOUT": "30",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.postgresql",
                        "HOST": "pghost",
                        "NAME": "paperless",
                        "USER": "paperless",
                        "PASSWORD": "paperless",
                        "OPTIONS": {
                            "sslmode": "require",
                            "sslrootcert": "/certs/ca.crt",
                            "sslcert": None,
                            "sslkey": None,
                            "application_name": "paperless-ngx",
                            "connect_timeout": 30,
                        },
                    },
                },
                id="postgresql-legacy-ssl-and-timeout",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "mariadb",
                    "PAPERLESS_DBHOST": "localhost",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.mysql",
                        "HOST": "localhost",
                        "NAME": "paperless",
                        "USER": "paperless",
                        "PASSWORD": "paperless",
                        "OPTIONS": {
                            "read_default_file": "/etc/mysql/my.cnf",
                            "charset": "utf8mb4",
                            "collation": "utf8mb4_unicode_ci",
                            "ssl_mode": "PREFERRED",
                            "ssl": {
                                "ca": None,
                                "cert": None,
                                "key": None,
                            },
                            "isolation_level": "read committed",
                        },
                    },
                },
                id="mariadb-defaults",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "mariadb",
                    "PAPERLESS_DBHOST": "mariahost",
                    "PAPERLESS_DBNAME": "paperlessdb",
                    "PAPERLESS_DBUSER": "my-cool-user",
                    "PAPERLESS_DBPASS": "my-secure-password",
                    "PAPERLESS_DB_OPTIONS": "ssl_mode=REQUIRED,ssl.ca=/path/to/ca.pem",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.mysql",
                        "HOST": "mariahost",
                        "NAME": "paperlessdb",
                        "USER": "my-cool-user",
                        "PASSWORD": "my-secure-password",
                        "OPTIONS": {
                            "read_default_file": "/etc/mysql/my.cnf",
                            "charset": "utf8mb4",
                            "collation": "utf8mb4_unicode_ci",
                            "ssl_mode": "REQUIRED",
                            "ssl": {
                                "ca": "/path/to/ca.pem",
                                "cert": None,
                                "key": None,
                            },
                            "isolation_level": "read committed",
                        },
                    },
                },
                id="mariadb-overrides",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "mariadb",
                    "PAPERLESS_DBHOST": "mariahost",
                    "PAPERLESS_DBSSLMODE": "REQUIRED",
                    "PAPERLESS_DBSSLROOTCERT": "/certs/ca.pem",
                    "PAPERLESS_DBSSLCERT": "/certs/client.pem",
                    "PAPERLESS_DBSSLKEY": "/certs/client.key",
                    "PAPERLESS_DB_TIMEOUT": "25",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.mysql",
                        "HOST": "mariahost",
                        "NAME": "paperless",
                        "USER": "paperless",
                        "PASSWORD": "paperless",
                        "OPTIONS": {
                            "read_default_file": "/etc/mysql/my.cnf",
                            "charset": "utf8mb4",
                            "collation": "utf8mb4_unicode_ci",
                            "ssl_mode": "REQUIRED",
                            "ssl": {
                                "ca": "/certs/ca.pem",
                                "cert": "/certs/client.pem",
                                "key": "/certs/client.key",
                            },
                            "connect_timeout": 25,
                            "isolation_level": "read committed",
                        },
                    },
                },
                id="mariadb-legacy-ssl-and-timeout",
            ),
        ],
    )
    def test_parse_db_settings(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
        env_vars: dict[str, str],
        expected_database_settings: dict[str, dict],
    ) -> None:
        """Test various database configurations with defaults and overrides."""
        mocker.patch.dict(os.environ, env_vars, clear=True)

        if (
            "default" in expected_database_settings
            and expected_database_settings["default"]["NAME"] is None
        ):
            expected_database_settings["default"]["NAME"] = str(
                tmp_path / "db.sqlite3",
            )

        settings = parse_db_settings(tmp_path)

        assert settings == expected_database_settings


class TestParseIgnoreDates:
    """Tests the parsing of the PAPERLESS_IGNORE_DATES setting value."""

    def test_no_ignore_dates_set(self) -> None:
        """
        GIVEN:
            - No ignore dates are set
        THEN:
            - No ignore dates are parsed
        """
        assert parse_ignore_dates("", "YMD") == set()

    @pytest.mark.parametrize(
        ("env_str", "date_format", "expected"),
        [
            pytest.param(
                "1985-05-01",
                "YMD",
                {datetime.date(1985, 5, 1)},
                id="single-ymd",
            ),
            pytest.param(
                "1985-05-01,1991-12-05",
                "YMD",
                {datetime.date(1985, 5, 1), datetime.date(1991, 12, 5)},
                id="multiple-ymd",
            ),
            pytest.param(
                "2010-12-13",
                "YMD",
                {datetime.date(2010, 12, 13)},
                id="single-ymd-2",
            ),
            pytest.param(
                "11.01.10",
                "DMY",
                {datetime.date(2010, 1, 11)},
                id="single-dmy",
            ),
            pytest.param(
                "11.01.2001,15-06-1996",
                "DMY",
                {datetime.date(2001, 1, 11), datetime.date(1996, 6, 15)},
                id="multiple-dmy",
            ),
        ],
    )
    def test_ignore_dates_parsed(
        self,
        env_str: str,
        date_format: str,
        expected: set[datetime.date],
    ) -> None:
        """
        GIVEN:
            - Ignore dates are set per certain inputs
        THEN:
            - All ignore dates are parsed
        """
        assert parse_ignore_dates(env_str, date_format) == expected


@pytest.mark.parametrize(
    ("languages", "expected"),
    [
        ("de", ["de"]),
        ("zh", ["zh"]),
        ("fr+en", ["fr", "en"]),
        # Locales must be supported
        ("en-001+fr-CA", ["en-001", "fr-CA"]),
        ("en-001+fr", ["en-001", "fr"]),
        # Special case for Chinese: variants seem to miss some dates,
        # so we always add "zh" as a fallback.
        ("en+zh-Hans-HK", ["en", "zh-Hans-HK", "zh"]),
        ("en+zh-Hans", ["en", "zh-Hans", "zh"]),
        ("en+zh-Hans+zh-Hant", ["en", "zh-Hans", "zh-Hant", "zh"]),
    ],
)
def test_parse_dateparser_languages(languages: str, expected: list[str]) -> None:
    assert sorted(parse_dateparser_languages(languages)) == sorted(expected)
