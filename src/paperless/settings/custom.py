import os
from pathlib import Path
from typing import Any

from paperless.settings.parsers import get_choice_from_env
from paperless.settings.parsers import get_int_from_env
from paperless.settings.parsers import parse_dict_from_str


def parse_db_settings(data_dir: Path) -> dict[str, dict[str, Any]]:
    """Parse database settings from environment variables.

    Core connection variables (no deprecation):
    - PAPERLESS_DBENGINE (sqlite/postgresql/mariadb)
    - PAPERLESS_DBHOST, PAPERLESS_DBPORT
    - PAPERLESS_DBNAME, PAPERLESS_DBUSER, PAPERLESS_DBPASS

    Advanced options can be set via:
    - Legacy individual env vars (deprecated in v3.0, removed in v3.2)
    - PAPERLESS_DB_OPTIONS (recommended v3+ approach)

    Args:
        data_dir: The data directory path for SQLite database location.

    Returns:
        A databases dict suitable for Django DATABASES setting.
    """
    engine = get_choice_from_env(
        "PAPERLESS_DBENGINE",
        {"sqlite", "postgresql", "mariadb"},
        default="sqlite",
    )

    db_config: dict[str, Any]
    base_options: dict[str, Any]

    match engine:
        case "sqlite":
            db_config = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str((data_dir / "db.sqlite3").resolve()),
            }
            base_options = {}

        case "postgresql":
            db_config = {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": os.getenv("PAPERLESS_DBHOST"),
                "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
                "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
                "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
            }

            base_options = {
                "sslmode": os.getenv("PAPERLESS_DBSSLMODE", "prefer"),
                "sslrootcert": os.getenv("PAPERLESS_DBSSLROOTCERT"),
                "sslcert": os.getenv("PAPERLESS_DBSSLCERT"),
                "sslkey": os.getenv("PAPERLESS_DBSSLKEY"),
            }

            if (pool_size := get_int_from_env("PAPERLESS_DB_POOLSIZE")) is not None:
                base_options["pool"] = {
                    "min_size": 1,
                    "max_size": pool_size,
                }

        case "mariadb":
            db_config = {
                "ENGINE": "django.db.backends.mysql",
                "HOST": os.getenv("PAPERLESS_DBHOST"),
                "NAME": os.getenv("PAPERLESS_DBNAME", "paperless"),
                "USER": os.getenv("PAPERLESS_DBUSER", "paperless"),
                "PASSWORD": os.getenv("PAPERLESS_DBPASS", "paperless"),
            }

            base_options = {
                "read_default_file": "/etc/mysql/my.cnf",
                "charset": "utf8mb4",
                "collation": "utf8mb4_unicode_ci",
                "ssl_mode": os.getenv("PAPERLESS_DBSSLMODE", "PREFERRED"),
                "ssl": {
                    "ca": os.getenv("PAPERLESS_DBSSLROOTCERT"),
                    "cert": os.getenv("PAPERLESS_DBSSLCERT"),
                    "key": os.getenv("PAPERLESS_DBSSLKEY"),
                },
            }
        case _:  # pragma: no cover
            raise NotImplementedError(engine)

    # Handle port setting for external databases
    if (
        engine in ("postgresql", "mariadb")
        and (port := get_int_from_env("PAPERLESS_DBPORT")) is not None
    ):
        db_config["PORT"] = port

    # Handle timeout setting (common across all engines, different key names)
    if (timeout := get_int_from_env("PAPERLESS_DB_TIMEOUT")) is not None:
        timeout_key = "timeout" if engine == "sqlite" else "connect_timeout"
        base_options[timeout_key] = timeout

    # Apply PAPERLESS_DB_OPTIONS overrides
    db_config["OPTIONS"] = parse_dict_from_str(
        os.getenv("PAPERLESS_DB_OPTIONS"),
        defaults=base_options,
        separator=";",
        type_map={
            # SQLite options
            "timeout": int,
            # Postgres/MariaDB options
            "connect_timeout": int,
            "pool.min_size": int,
            "pool.max_size": int,
        },
    )

    databases = {"default": db_config}

    # Add SQLite fallback for PostgreSQL/MariaDB
    # TODO: Is this really useful/used?
    if engine in ("postgresql", "mariadb"):
        databases["sqlite"] = {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str((data_dir / "db.sqlite3").resolve()),
            "OPTIONS": {},
        }

    return databases
