import sqlite3

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore


def _migrate_v1_to_v2_add_document_chunks(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    dim: int,
) -> None:
    """v1 -> v2: backfill the document_chunks side table.

    document_chunks (see PaperlessSqliteVecVectorStore._open_connection) lets
    delete()/upsert_document() find a document's chunk ids without a vec0
    full table scan on the document_id metadata column. Every row written
    before this migration predates that table, so without backfilling,
    deleting a pre-migration document would find zero chunk ids and leave its
    vec0 rows permanently orphaned. Backfilling is just the same rebuild
    compact() uses (_rebuild_into), minus "schema_version" -- the caller
    (_run_structural_migration) sets that to this migration's target version
    instead of preserving the source's.
    """
    PaperlessSqliteVecVectorStore._rebuild_into(
        src_conn,
        dst_conn,
        dim,
        meta_keys=("dim", "embed_model"),
    )


MIGRATIONS.append(
    Migration(
        from_version=1,
        to_version=2,
        kind="structural",
        description="add document_chunks side table for O(1) per-document deletes",
        apply=_migrate_v1_to_v2_add_document_chunks,
    ),
)
