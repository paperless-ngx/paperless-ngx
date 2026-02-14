import os
from pathlib import Path
from typing import TypeAlias

from celery.schedules import crontab

from paperless.settings.parsers import get_choice_from_env
from paperless.settings.parsers import get_int_from_env
from paperless.settings.parsers import parse_dict_from_str

# Covers: ENGINE/NAME/HOST/USER/PASSWORD (str), PORT (int), OPTIONS (dict)
DatabaseConfig: TypeAlias = dict[str, str | int | dict[str, str | int | dict | None]]


def parse_hosting_settings() -> tuple[str | None, str, str, str, str]:
    script_name = os.getenv("PAPERLESS_FORCE_SCRIPT_NAME")
    base_url = (script_name or "") + "/"
    login_url = base_url + "accounts/login/"
    login_redirect_url = base_url + "dashboard"
    logout_redirect_url = os.getenv(
        "PAPERLESS_LOGOUT_REDIRECT_URL",
        login_url + "?loggedout=1",
    )
    return script_name, base_url, login_url, login_redirect_url, logout_redirect_url


def parse_redis_url(env_redis: str | None) -> tuple[str, str]:
    """
    Gets the Redis information from the environment or a default and handles
    converting from incompatible django_channels and celery formats.

    Returns a tuple of (celery_url, channels_url)
    """

    # Not set, return a compatible default
    if env_redis is None:
        return ("redis://localhost:6379", "redis://localhost:6379")

    if "unix" in env_redis.lower():
        # channels_redis socket format, looks like:
        # "unix:///path/to/redis.sock"
        _, path = env_redis.split(":")
        # Optionally setting a db number
        if "?db=" in env_redis:
            path, number = path.split("?db=")
            return (f"redis+socket:{path}?virtual_host={number}", env_redis)
        else:
            return (f"redis+socket:{path}", env_redis)

    elif "+socket" in env_redis.lower():
        # celery socket style, looks like:
        # "redis+socket:///path/to/redis.sock"
        _, path = env_redis.split(":")
        if "?virtual_host=" in env_redis:
            # Virtual host (aka db number)
            path, number = path.split("?virtual_host=")
            return (env_redis, f"unix:{path}?db={number}")
        else:
            return (env_redis, f"unix:{path}")

    # Not a socket
    return (env_redis, env_redis)


def parse_beat_schedule() -> dict:
    """
    Configures the scheduled tasks, according to default or
    environment variables.  Task expiration is configured so the task will
    expire (and not run), shortly before the default frequency will put another
    of the same task into the queue


    https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html#beat-entries
    https://docs.celeryq.dev/en/latest/userguide/calling.html#expiration
    """
    schedule = {}
    tasks = [
        {
            "name": "Check all e-mail accounts",
            "env_key": "PAPERLESS_EMAIL_TASK_CRON",
            # Default every ten minutes
            "env_default": "*/10 * * * *",
            "task": "paperless_mail.tasks.process_mail_accounts",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 9.0 * 60.0,
            },
        },
        {
            "name": "Train the classifier",
            "env_key": "PAPERLESS_TRAIN_TASK_CRON",
            # Default hourly at 5 minutes past the hour
            "env_default": "5 */1 * * *",
            "task": "documents.tasks.train_classifier",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 59.0 * 60.0,
            },
        },
        {
            "name": "Optimize the index",
            "env_key": "PAPERLESS_INDEX_TASK_CRON",
            # Default daily at midnight
            "env_default": "0 0 * * *",
            "task": "documents.tasks.index_optimize",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Perform sanity check",
            "env_key": "PAPERLESS_SANITY_TASK_CRON",
            # Default Sunday at 00:30
            "env_default": "30 0 * * sun",
            "task": "documents.tasks.sanity_check",
            "options": {
                # 1 hour before default schedule sends again
                "expires": ((7.0 * 24.0) - 1.0) * 60.0 * 60.0,
            },
        },
        {
            "name": "Empty trash",
            "env_key": "PAPERLESS_EMPTY_TRASH_TASK_CRON",
            # Default daily at 01:00
            "env_default": "0 1 * * *",
            "task": "documents.tasks.empty_trash",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Check and run scheduled workflows",
            "env_key": "PAPERLESS_WORKFLOW_SCHEDULED_TASK_CRON",
            # Default hourly at 5 minutes past the hour
            "env_default": "5 */1 * * *",
            "task": "documents.tasks.check_scheduled_workflows",
            "options": {
                # 1 minute before default schedule sends again
                "expires": 59.0 * 60.0,
            },
        },
    ]
    for task in tasks:
        # Either get the environment setting or use the default
        value = os.getenv(task["env_key"], task["env_default"])
        # Don't add disabled tasks to the schedule
        if value == "disable":
            continue
        # I find https://crontab.guru/ super helpful
        # crontab(5) format
        #   - five time-and-date fields
        #   - separated by at least one blank
        minute, hour, day_month, month, day_week = value.split(" ")

        schedule[task["name"]] = {
            "task": task["task"],
            "schedule": crontab(minute, hour, day_week, day_month, month),
            "options": task["options"],
        }

    return schedule


def parse_db_settings(data_dir: Path) -> dict[str, DatabaseConfig]:
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
