import sqlite3

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.tables import ChunkRow
from paperless_ai.tables import DocumentChunksTable
from paperless_ai.tables import DocumentMetaRow
from paperless_ai.tables import DocumentMetaTable
from paperless_ai.tables import IndexMetaTable
from paperless_ai.vector_store import BATCH_SIZE
from paperless_ai.vector_store import DEFAULT_TABLE_NAME

# v1's vec0 shape has never changed since it first shipped and is the ONLY
# real upgrade path -- no store has ever existed at any intermediate
# version, so this migration goes straight from that shipped shape to the
# final v2 target in one pass.
_V1_SELECT = (
    "SELECT id, document_id, modified, node_content, embedding FROM "
    + DEFAULT_TABLE_NAME
)


def _migrate_v1_to_v2(
    src_conn: sqlite3.Connection,
    dst_conn: sqlite3.Connection,
    dim: int,
) -> None:
    """v1 -> v2: document_id TEXT -> INTEGER, modified moves out of vec0
    into document_meta, document_chunks added for O(1) per-document delete.

    Freezes its own v2-shaped vec0/document_chunks/document_meta DDL inline,
    rather than delegating to the gateway "create table" helpers or the
    store's own vec0-table builder (all of which always reflect the
    *current* schema): a later schema version changing any of these tables'
    shape must not silently change what this migration produces for someone
    upgrading straight from v1.
    _open_connection() already created document_chunks/document_meta on
    dst_conn (reflecting current HEAD) as a side effect of opening it for
    this migration's rebuild -- DROP them first so this migration's own
    frozen CREATE TABLE isn't a silent no-op against that. Safe here because
    dst_conn is a freshly opened, empty rebuild file with nothing written
    yet.
    """
    dst_conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
        "CREATE VIRTUAL TABLE "
        + DEFAULT_TABLE_NAME
        + " USING vec0("
        + "id TEXT PRIMARY KEY,"
        + " document_id INTEGER,"
        + " +node_content TEXT,"
        + " embedding float["
        + str(int(dim))
        + "] distance_metric=cosine"
        + ")",
    )
    dst_conn.execute("DROP TABLE IF EXISTS document_chunks")
    dst_conn.execute(
        "CREATE TABLE document_chunks "
        "(chunk_id TEXT PRIMARY KEY, document_id INTEGER NOT NULL)",
    )
    dst_conn.execute(
        "CREATE INDEX idx_document_chunks_document_id ON document_chunks (document_id)",
    )
    dst_conn.execute("DROP TABLE IF EXISTS document_meta")
    dst_conn.execute(
        "CREATE TABLE document_meta "
        "(document_id INTEGER PRIMARY KEY, modified TEXT NOT NULL)",
    )

    IndexMetaTable.set_dim(dst_conn, dim)
    embed_model = IndexMetaTable.get_embed_model(src_conn)
    if embed_model is not None:
        IndexMetaTable.set_embed_model(dst_conn, embed_model)

    dst_conn.execute("BEGIN IMMEDIATE")
    src_cursor = src_conn.execute(_V1_SELECT)
    live = 0
    while batch := src_cursor.fetchmany(BATCH_SIZE):
        vec0_rows = []
        chunk_rows = []
        meta_by_document: dict[int, str] = {}
        for r in batch:
            document_id = int(r["document_id"])
            vec0_rows.append(
                (r["id"], document_id, r["node_content"], bytes(r["embedding"])),
            )
            chunk_rows.append(ChunkRow(r["id"], document_id))
            meta_by_document[document_id] = str(r["modified"] or "")
        dst_conn.executemany(
            "INSERT INTO "
            + DEFAULT_TABLE_NAME
            + " (id, document_id, node_content, embedding) VALUES (?, ?, ?, ?)",
            vec0_rows,
        )
        DocumentChunksTable.insert_many(dst_conn, chunk_rows)
        DocumentMetaTable.upsert_many(
            dst_conn,
            (DocumentMetaRow(doc_id, mod) for doc_id, mod in meta_by_document.items()),
        )
        live += len(batch)
    # This migration only ever copies live rows (like compact()), so the
    # cumulative counter resets to match -- the new file has no bloat yet.
    IndexMetaTable.reset_total_inserts(dst_conn, live)
    dst_conn.execute("COMMIT")


MIGRATIONS.append(
    Migration(
        from_version=1,
        to_version=2,
        kind="structural",
        description=(
            "document_id TEXT -> INTEGER; move modified into document_meta; "
            "add document_chunks for O(1) per-document delete"
        ),
        apply=_migrate_v1_to_v2,
    ),
)
