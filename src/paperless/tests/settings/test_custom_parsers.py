import os
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from paperless.settings.custom import parse_db_settings


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
                        "NAME": None,  # Will be replaced with tmp_path
                        "OPTIONS": {},
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
                        "NAME": None,  # Will be replaced with tmp_path
                        "OPTIONS": {
                            "timeout": 30,
                        },
                    },
                },
                id="sqlite-with-timeout-override",
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
                    "PAPERLESS_DB_OPTIONS": "pool.max_size=50;pool.min_size=2;sslmode=require",
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
                        },
                    },
                },
                id="mariadb-defaults",
            ),
            pytest.param(
                {
                    "PAPERLESS_DBENGINE": "mariadb",
                    "PAPERLESS_DBHOST": "paperless-mariadb-host",
                    "PAPERLESS_DBPORT": "5555",
                    "PAPERLESS_DBUSER": "my-cool-user",
                    "PAPERLESS_DBPASS": "my-secure-password",
                    "PAPERLESS_DB_OPTIONS": "ssl.ca=/path/to/ca.pem;ssl_mode=REQUIRED",
                },
                {
                    "default": {
                        "ENGINE": "django.db.backends.mysql",
                        "HOST": "paperless-mariadb-host",
                        "PORT": 5555,
                        "NAME": "paperless",
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
        # Clear environment and set test vars
        mocker.patch.dict(os.environ, env_vars, clear=True)

        # Update expected paths with actual tmp_path
        if (
            "default" in expected_database_settings
            and expected_database_settings["default"]["NAME"] is None
        ):
            expected_database_settings["default"]["NAME"] = str(
                tmp_path / "db.sqlite3",
            )

        settings = parse_db_settings(tmp_path)

        assert settings == expected_database_settings
