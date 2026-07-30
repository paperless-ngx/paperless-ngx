from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import connection

if TYPE_CHECKING:
    from django.db.models import QuerySet


def _reset_table_names() -> list[str]:
    from guardian.models import GroupObjectPermission
    from guardian.models import UserObjectPermission

    from documents.models import Correspondent
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag

    return [
        Document.tags.through._meta.db_table,
        Document._meta.db_table,
        Tag._meta.db_table,
        Correspondent._meta.db_table,
        DocumentType._meta.db_table,
        StoragePath._meta.db_table,
        UserObjectPermission._meta.db_table,
        GroupObjectPermission._meta.db_table,
    ]


def _delete_all_users_and_groups() -> None:
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    get_user_model().objects.all().delete()
    Group.objects.all().delete()


def _reset_postgresql() -> None:
    tables = _reset_table_names()
    with connection.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;")
    _delete_all_users_and_groups()


def _reset_mariadb() -> None:
    # MariaDB's TRUNCATE has no CASCADE clause and refuses to truncate a
    # table referenced by a foreign key while checks are enabled, so
    # checks are disabled for the duration of the reset.
    tables = _reset_table_names()
    with connection.cursor() as cursor:
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
        try:
            for table in tables:
                cursor.execute(f"TRUNCATE TABLE {table};")
        finally:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    _delete_all_users_and_groups()


def _reset_sqlite() -> None:
    from documents.models import Correspondent
    from documents.models import Document
    from documents.models import DocumentType
    from documents.models import StoragePath
    from documents.models import Tag

    Document.global_objects.all().delete()
    Tag.objects.all().delete()
    Correspondent.objects.all().delete()
    DocumentType.objects.all().delete()
    StoragePath.objects.all().delete()
    _delete_all_users_and_groups()


def reset_benchmark_data() -> None:
    """
    Remove all previously-seeded benchmark data (documents, tags,
    correspondents, document types, storage paths, guardian permission
    rows, users, and groups) so a fresh `benchmark seed` run starts
    from an empty slate. Dispatches per-backend because TRUNCATE syntax
    and cascade behavior differ across the 3 supported databases.
    """
    if connection.vendor == "postgresql":
        _reset_postgresql()
    elif connection.vendor == "mysql":
        # MariaDB also reports vendor == "mysql" under Django's mysql backend.
        _reset_mariadb()
    else:
        _reset_sqlite()


def capture_explain(queryset: QuerySet) -> str:
    """
    Return the query plan for `queryset` using the current backend's
    explain facility. PostgreSQL and MariaDB both support EXPLAIN ANALYZE
    (real execution stats). SQLite only supports EXPLAIN QUERY PLAN (the
    chosen plan, not real timing/row counts) -- that output is clearly
    labeled rather than silently looking equivalent to the other two
    backends' output.
    """
    sql, params = queryset.query.sql_with_params()
    with connection.cursor() as cursor:
        if connection.vendor in ("postgresql", "mysql"):
            cursor.execute(f"EXPLAIN ANALYZE {sql}", params)
            return "\n".join(str(row[0]) for row in cursor.fetchall())
        cursor.execute(f"EXPLAIN QUERY PLAN {sql}", params)
        rows = "\n".join(" | ".join(str(c) for c in row) for row in cursor.fetchall())
        return f"(plan only -- no execution stats on SQLite)\n{rows}"
