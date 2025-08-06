from django.db import connection
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "1068_alter_document_created"),
    ]

    operations = []

    vendor = connection.vendor

    if vendor == "postgresql":
        operations += [
            migrations.RunSQL(
                """
            CREATE INDEX IF NOT EXISTS document_title_fts
            ON documents_document
            USING GIN (to_tsvector('simple', title));
            """,
                reverse_sql="""
            DROP INDEX IF EXISTS document_title_fts;
            """,
            ),
            migrations.RunSQL(
                """
            CREATE INDEX IF NOT EXISTS document_content_fts
            ON documents_document
            USING GIN (to_tsvector('simple', content));
            """,
                reverse_sql="""
            DROP INDEX IF EXISTS document_content_fts;
            """,
            ),
        ]
    elif vendor in {"mysql", "mariadb"}:
        operations += [
            migrations.RunSQL(
                """
            ALTER TABLE documents_document
            ADD FULLTEXT INDEX document_title_fts (title);
            """,
                reverse_sql="""
            ALTER TABLE documents_document
            DROP INDEX document_title_fts;
            """,
            ),
            migrations.RunSQL(
                """
            ALTER TABLE documents_document
            ADD FULLTEXT INDEX document_content_fts (content);
            """,
                reverse_sql="""
            ALTER TABLE documents_document
            DROP INDEX document_content_fts;
            """,
            ),
        ]
    else:
        operations += [
            # Avoid prefixes in the SQLite FTS table to limit disk usage.
            # Queries will work even without indexing the prefixes.
            migrations.RunSQL(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_document_fts
                USING fts5(title, content, content='', contentless_delete=1);
                """,
                reverse_sql="DROP TABLE IF EXISTS documents_document_fts;",
            ),
            migrations.RunSQL(
                """
                INSERT INTO documents_document_fts(rowid, title, content)
                SELECT id, title, content FROM documents_document;
                """,
                reverse_sql="DELETE FROM documents_document_fts;",
            ),
            migrations.RunSQL(
                """
                CREATE TRIGGER documents_document_ai AFTER INSERT ON documents_document BEGIN
                INSERT INTO documents_document_fts(rowid, title, content)
                VALUES (new.id, new.title, new.content);
                END;
                """,
                reverse_sql="DROP TRIGGER IF EXISTS documents_document_ai;",
            ),
            migrations.RunSQL(
                """
                CREATE TRIGGER documents_document_au AFTER UPDATE ON documents_document BEGIN
                UPDATE documents_document_fts SET
                    title = new.title,
                    content = new.content
                WHERE rowid = new.id;
                END;
                """,
                reverse_sql="DROP TRIGGER IF EXISTS documents_document_au;",
            ),
            migrations.RunSQL(
                """
                CREATE TRIGGER documents_document_ad AFTER DELETE ON documents_document BEGIN
                DELETE FROM documents_document_fts WHERE rowid = old.id;
                END;
                """,
                reverse_sql="DROP TRIGGER IF EXISTS documents_document_ad;",
            ),
        ]
