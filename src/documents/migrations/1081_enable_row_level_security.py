# Migration to enable PostgreSQL Row-Level Security (RLS) for tenant isolation

from django.db import migrations, connection


def is_postgresql(schema_editor):
    """Check if the database backend is PostgreSQL."""
    return schema_editor.connection.vendor == 'postgresql'


def enable_rls_forward(apps, schema_editor):
    """
    Enable RLS on all tenant-aware tables.
    Only runs on PostgreSQL databases.
    """
    if not is_postgresql(schema_editor):
        return  # Skip for non-PostgreSQL databases

    tables = [
        'documents_document',
        'documents_tag',
        'documents_correspondent',
        'documents_documenttype',
        'documents_savedview',
        'documents_storagepath',
        'documents_paperlesstask',
    ]

    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            # Enable Row-Level Security
            cursor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

            # Drop policy if it exists, then create it (idempotent)
            cursor.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")

            cursor.execute(f"""
                CREATE POLICY tenant_isolation_policy ON {table}
                    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
            """)

            # Force RLS (prevent superuser bypass)
            cursor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")


def disable_rls_reverse(apps, schema_editor):
    """
    Disable RLS on all tenant-aware tables.
    Only runs on PostgreSQL databases.
    """
    if not is_postgresql(schema_editor):
        return  # Skip for non-PostgreSQL databases

    tables = [
        'documents_document',
        'documents_tag',
        'documents_correspondent',
        'documents_documenttype',
        'documents_savedview',
        'documents_storagepath',
        'documents_paperlesstask',
    ]

    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            # Drop tenant isolation policy
            cursor.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")

            # Disable FORCE RLS
            cursor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")

            # Disable Row-Level Security
            cursor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1080_make_tenant_id_non_nullable'),
    ]

    operations = [
        migrations.RunPython(enable_rls_forward, reverse_code=disable_rls_reverse),
    ]
