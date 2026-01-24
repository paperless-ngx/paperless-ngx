import django
from django.apps import apps
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


def _target_tables() -> list[str]:
    tables = {
        model._meta.db_table for model in apps.get_models(include_auto_created=True)
    }
    tables.add(MigrationRecorder.Migration._meta.db_table)
    existing = set(connection.introspection.table_names())
    return sorted(tables & existing)


def _drop_sqlite_tables() -> None:
    tables = _target_tables()
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA foreign_keys=OFF;")
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}";')
        cursor.execute("PRAGMA foreign_keys=ON;")


def _drop_postgres_tables() -> None:
    tables = _target_tables()
    if not tables:
        return
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')


def _drop_mysql_tables() -> None:
    tables = _target_tables()
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        for table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`;")
        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")


def main() -> None:
    django.setup()
    vendor = connection.vendor
    print(f"Wiping database for {vendor}...")  # noqa: T201

    if vendor == "sqlite":
        _drop_sqlite_tables()
    elif vendor == "postgresql":
        _drop_postgres_tables()
    elif vendor == "mysql":
        _drop_mysql_tables()
    else:
        raise SystemExit(f"Unsupported database vendor: {vendor}")

    print("Database wipe complete.")  # noqa: T201


if __name__ == "__main__":
    main()
