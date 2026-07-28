import sqlite3

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore
from paperless_ai.vector_store import _copy_rows


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
    vec0 rows permanently orphaned. Backfilling is a plain row copy into the
    new-schema file (``_copy_rows``, the same helper compact() uses), which
    records every copied row in document_chunks as it goes.
    """
    PaperlessSqliteVecVectorStore._create_vec_table(dst_conn, dim)
    PaperlessSqliteVecVectorStore._meta_set_on(dst_conn, "dim", str(dim))
    embed_model = PaperlessSqliteVecVectorStore._meta_get_on(src_conn, "embed_model")
    if embed_model is not None:
        PaperlessSqliteVecVectorStore._meta_set_on(dst_conn, "embed_model", embed_model)

    dst_conn.execute("BEGIN IMMEDIATE")
    live = _copy_rows(src_conn, dst_conn)
    # This migration only ever copies live rows (like compact()), so the
    # cumulative counter resets to match -- the new file has no bloat yet.
    PaperlessSqliteVecVectorStore._meta_set_on(dst_conn, "total_inserts", str(live))
    dst_conn.execute("COMMIT")


MIGRATIONS.append(
    Migration(
        from_version=1,
        to_version=2,
        kind="structural",
        description="add document_chunks side table for O(1) per-document deletes",
        apply=_migrate_v1_to_v2_add_document_chunks,
    ),
)
