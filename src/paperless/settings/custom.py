import datetime
import logging
import os
from pathlib import Path
from typing import Any

from celery.schedules import crontab
from dateparser.languages.loader import LocaleDataLoader

from paperless.settings.parsers import get_choice_from_env
from paperless.settings.parsers import get_int_from_env
from paperless.settings.parsers import parse_dict_from_str

logger = logging.getLogger(__name__)


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
        _, path = env_redis.split(":", maxsplit=1)
        # Optionally setting a db number
        if "?db=" in env_redis:
            path, number = path.split("?db=")
            return (f"redis+socket:{path}?virtual_host={number}", env_redis)
        else:
            return (f"redis+socket:{path}", env_redis)

    elif "+socket" in env_redis.lower():
        # celery socket style, looks like:
        # "redis+socket:///path/to/redis.sock"
        _, path = env_redis.split(":", maxsplit=1)
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
        {
            "name": "Rebuild LLM index",
            "env_key": "PAPERLESS_LLM_INDEX_TASK_CRON",
            # Default daily at 02:10
            "env_default": "10 2 * * *",
            "task": "documents.tasks.llmindex_index",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
            },
        },
        {
            "name": "Cleanup expired share link bundles",
            "env_key": "PAPERLESS_SHARE_LINK_BUNDLE_CLEANUP_CRON",
            # Default daily at 02:00
            "env_default": "0 2 * * *",
            "task": "documents.tasks.cleanup_expired_share_link_bundles",
            "options": {
                # 1 hour before default schedule sends again
                "expires": 23.0 * 60.0 * 60.0,
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
            "options": {
                **task["options"],
                # PaperlessTask.TriggerSource.SCHEDULED -- models can't be imported here
                "headers": {"trigger_source": "scheduled"},
            },
        }

    return schedule


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
    try:
        engine = get_choice_from_env(
            "PAPERLESS_DBENGINE",
            {"sqlite", "postgresql", "mariadb"},
        )
    except ValueError:
        # MariaDB users already had to set PAPERLESS_DBENGINE, so it was picked up above
        # SQLite users didn't need to set anything
        engine = "postgresql" if "PAPERLESS_DBHOST" in os.environ else "sqlite"

    db_config: dict[str, Any]
    base_options: dict[str, Any]

    match engine:
        case "sqlite":
            db_config = {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": str((data_dir / "db.sqlite3").resolve()),
            }
            base_options = {
                # Django splits init_command on ";" and calls conn.execute()
                # once per statement, so multiple PRAGMAs work correctly.
                # foreign_keys is omitted — Django sets it natively.
                "init_command": (
                    "PRAGMA journal_mode=WAL;"
                    "PRAGMA synchronous=NORMAL;"
                    "PRAGMA busy_timeout=5000;"
                    "PRAGMA temp_store=MEMORY;"
                    "PRAGMA mmap_size=134217728;"
                    "PRAGMA journal_size_limit=67108864;"
                    "PRAGMA cache_size=-8000"  # negative = KiB; -8000 ≈ 8 MB
                ),
                # IMMEDIATE acquires the write lock at BEGIN, ensuring
                # busy_timeout is respected from the start of the transaction.
                "transaction_mode": "IMMEDIATE",
            }

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
                "application_name": "paperless-ngx",
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
                # READ COMMITTED eliminates gap locking and reduces deadlocks.
                # Django also defaults to "read committed" for MySQL/MariaDB, but
                # we set it explicitly so the intent is clear and survives any
                # future changes to Django's default.
                # Requires binlog_format=ROW if binary logging is enabled.
                "isolation_level": "read committed",
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
        separator=",",
        type_map={
            # SQLite options
            "timeout": int,
            # Postgres/MariaDB options
            "connect_timeout": int,
            "pool.min_size": int,
            "pool.max_size": int,
        },
    )

    return {"default": db_config}


def parse_dateparser_languages(languages: str | None) -> list[str]:
    language_list = languages.split("+") if languages else []
    # There is an unfixed issue in zh-Hant and zh-Hans locales in the dateparser lib.
    # See: https://github.com/scrapinghub/dateparser/issues/875
    for index, language in enumerate(language_list):
        if language.startswith("zh-") and "zh" not in language_list:
            logger.warning(
                f"Chinese locale detected: {language}. dateparser might fail to parse"
                f' some dates with this locale, so Chinese ("zh") will be used as a fallback.',
            )
            language_list.append("zh")

    return list(LocaleDataLoader().get_locale_map(locales=language_list))


def parse_ignore_dates(
    env_ignore: str,
    date_order: str,
) -> set[datetime.date]:
    """
    If the PAPERLESS_IGNORE_DATES environment variable is set, parse the
    user provided string(s) into dates

    Args:
        env_ignore (str): The value of the environment variable, comma separated dates
        date_order (str): The format of the date strings.

    Returns:
        set[datetime.date]: The set of parsed date objects
    """
    import dateparser

    ignored_dates = set()
    for s in env_ignore.split(","):
        d = dateparser.parse(
            s,
            settings={
                "DATE_ORDER": date_order,
            },
        )
        if d:
            ignored_dates.add(d.date())
    return ignored_dates
