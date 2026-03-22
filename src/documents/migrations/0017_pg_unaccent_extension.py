"""Install the PostgreSQL ``unaccent`` extension for accent-insensitive search.

This is a no-op on SQLite and MariaDB.
"""

from django.db import migrations


def install_unaccent(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("CREATE EXTENSION IF NOT EXISTS unaccent")


def remove_unaccent(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute("DROP EXTENSION IF EXISTS unaccent")


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0016_document_version_index_and_more"),
    ]

    operations = [
        migrations.RunPython(install_unaccent, remove_unaccent),
    ]
