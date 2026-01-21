# Migration to enable PostgreSQL Row-Level Security (RLS) for tenant isolation

from django.db import migrations, connection
from psycopg import sql


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
        'documents_note',
    ]

    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            # Enable Row-Level Security
            cursor.execute(
                sql.SQL("ALTER TABLE {} ENABLE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )

            # Drop policy if it exists, then create it (idempotent)
            cursor.execute(
                sql.SQL("DROP POLICY IF EXISTS tenant_isolation_policy ON {}").format(
                    sql.Identifier(table)
                )
            )

            # Create policy with both USING (for SELECT) and WITH CHECK (for INSERT/UPDATE/DELETE)
            cursor.execute(
                sql.SQL("""
                    CREATE POLICY tenant_isolation_policy ON {}
                        FOR ALL
                        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
                        WITH CHECK (tenant_id = current_setting('app.current_tenant', true)::uuid)
                """).format(sql.Identifier(table))
            )

            # Force RLS (prevent superuser bypass)
            cursor.execute(
                sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )


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
        'documents_note',
    ]

    for table in tables:
        with schema_editor.connection.cursor() as cursor:
            # Drop tenant isolation policy
            cursor.execute(
                sql.SQL("DROP POLICY IF EXISTS tenant_isolation_policy ON {}").format(
                    sql.Identifier(table)
                )
            )

            # Disable FORCE RLS
            cursor.execute(
                sql.SQL("ALTER TABLE {} NO FORCE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )

            # Disable Row-Level Security
            cursor.execute(
                sql.SQL("ALTER TABLE {} DISABLE ROW LEVEL SECURITY").format(
                    sql.Identifier(table)
                )
            )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '1080_make_tenant_id_non_nullable'),
    ]

    operations = [
        migrations.RunPython(enable_rls_forward, reverse_code=disable_rls_reverse),
    ]
