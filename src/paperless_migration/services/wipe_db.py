"""Database wipe service for migration import process.

This module can be run as a script via:
    python -m paperless_migration.services.wipe_db

It uses the paperless_migration settings to wipe all tables
before running v3 migrations.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.backends.base.base import BaseDatabaseWrapper

logger = logging.getLogger(__name__)


def _get_target_tables(connection: BaseDatabaseWrapper) -> list[str]:
    """Get list of tables to drop that exist in the database."""
    from django.apps import apps
    from django.db.migrations.recorder import MigrationRecorder

    model_tables = {
        model._meta.db_table for model in apps.get_models(include_auto_created=True)
    }
    model_tables.add(MigrationRecorder.Migration._meta.db_table)
    existing_tables = set(connection.introspection.table_names())
    return sorted(model_tables & existing_tables)


def _drop_sqlite_tables(connection: BaseDatabaseWrapper) -> int:
    """Drop tables for SQLite database. Returns count of tables dropped."""
    tables = _get_target_tables(connection)
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys=OFF;")
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}";')
        cursor.execute("PRAGMA foreign_keys=ON;")
    return len(tables)


def _drop_postgres_tables(connection: BaseDatabaseWrapper) -> int:
    """Drop tables for PostgreSQL database. Returns count of tables dropped."""
    tables = _get_target_tables(connection)
    if not tables:
        return 0
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
    return len(tables)


def _drop_mysql_tables(connection: BaseDatabaseWrapper) -> int:
    """Drop tables for MySQL/MariaDB database. Returns count of tables dropped."""
    tables = _get_target_tables(connection)
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
    return len(tables)


def wipe_database() -> tuple[bool, str]:
    """Wipe all application tables from the database.

    Returns:
        Tuple of (success: bool, message: str)
    """
    from django.db import connection

    vendor = connection.vendor
    logger.info("Wiping database for vendor: %s", vendor)

    try:
        match vendor:
            case "sqlite":
                count = _drop_sqlite_tables(connection)
            case "postgresql":
                count = _drop_postgres_tables(connection)
            case "mysql":
                count = _drop_mysql_tables(connection)
            case _:
                return False, f"Unsupported database vendor: {vendor}"

        message = f"Dropped {count} tables from {vendor} database"
        logger.info(message)
        return True, message

    except Exception as exc:
        message = f"Failed to wipe database: {exc}"
        logger.exception(message)
        return False, message


def main() -> int:
    """Entry point when run as a script."""
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "paperless_migration.settings")
    django.setup()

    success, message = wipe_database()
    print(message)  # noqa: T201
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
