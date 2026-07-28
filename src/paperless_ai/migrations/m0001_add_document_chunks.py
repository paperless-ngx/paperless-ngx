import sqlite3

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.vector_store import COMPACT_BATCH_SIZE
from paperless_ai.vector_store import DEFAULT_TABLE_NAME
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
    vec0 rows permanently orphaned.

    Deliberately spells out its own v2-shaped vec0 table and row copy,
    rather than delegating to PaperlessSqliteVecVectorStore's
    _create_vec_table()/_rebuild_into()/_copy_rows(): those always reflect
    whatever the *current* schema is. If a later migration changes that
    schema (bumping SCHEMA_VERSION again), this migration must keep
    producing its own historical v2 shape regardless -- otherwise a user
    upgrading across multiple versions in one go (e.g. v1 straight to v4)
    would have this migration silently produce a v4-shaped table instead
    of v2, and the v2 -> v3 migration that runs right after it would find
    the columns it expects to migrate *from* already gone.
    """
    dst_conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        "CREATE VIRTUAL TABLE "
        + DEFAULT_TABLE_NAME
        + " USING vec0("
        + "id TEXT PRIMARY KEY,"
        + " document_id TEXT,"
        + " modified TEXT,"
        + " +node_content TEXT,"
        + " embedding float["
        + str(int(dim))
        + "] distance_metric=cosine"
        + ")",
    )
    PaperlessSqliteVecVectorStore._meta_set_on(dst_conn, "dim", str(dim))
    embed_model = PaperlessSqliteVecVectorStore._meta_get_on(src_conn, "embed_model")
    if embed_model is not None:
        PaperlessSqliteVecVectorStore._meta_set_on(dst_conn, "embed_model", embed_model)

    dst_conn.execute("BEGIN IMMEDIATE")
    src_cursor = src_conn.execute(
        "SELECT id, document_id, modified, node_content, embedding FROM "
        + DEFAULT_TABLE_NAME,
    )
    live = 0
    while batch := src_cursor.fetchmany(COMPACT_BATCH_SIZE):
        dst_conn.executemany(
            "INSERT INTO "
            + DEFAULT_TABLE_NAME
            + " (id, document_id, modified, node_content, embedding) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    r["id"],
                    r["document_id"],
                    r["modified"],
                    r["node_content"],
                    bytes(r["embedding"]),
                )
                for r in batch
            ],
        )
        dst_conn.executemany(
            "INSERT INTO document_chunks (chunk_id, document_id) VALUES (?, ?)",
            [(r["id"], r["document_id"]) for r in batch],
        )
        live += len(batch)
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
