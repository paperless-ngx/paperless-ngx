"""Thin gateways over the plain relational side tables that sit alongside the
vec0 table. Each method takes the sqlite3.Connection to operate on
explicitly, rather than owning one -- the store swaps connections during
compact()/migration, and migrations always work across two connections
(src_conn, dst_conn) at once.

PRECONDITION: Callers must set conn.row_factory = sqlite3.Row before passing a
connection to any of these gateways' read methods. The read methods across all
three classes (DocumentChunksTable.chunk_ids_for_document, IndexMetaTable._get,
DocumentMetaTable.all_modified_times, DocumentMetaTable.copy_all) use
row["column_name"] dictionary-style indexing, which requires sqlite3.Row as the
row factory -- without it, sqlite3.Row is not set, rows are returned as plain
tuples, and tuple indices must be integers, raising TypeError.
"""

import sqlite3
from collections.abc import Iterable
from typing import NamedTuple


class ChunkRow(NamedTuple):
    chunk_id: str
    document_id: int


class DocumentMetaRow(NamedTuple):
    document_id: int
    modified: str


class DocumentChunksTable:
    """chunk_id -> document_id, indexed by document_id. Gives O(1)
    per-document chunk lookup that vec0's own document_id metadata column
    cannot (see PaperlessSqliteVecVectorStore._delete_chunks_by_document_id).
    """

    @staticmethod
    def create(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS document_chunks "
            "(chunk_id TEXT PRIMARY KEY, document_id INTEGER NOT NULL)",
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id "
            "ON document_chunks (document_id)",
        )

    @staticmethod
    def insert_many(conn: sqlite3.Connection, rows: Iterable[ChunkRow]) -> None:
        """rows must already be batch-bounded by the caller (e.g. vec0's own
        fetchmany() loop) -- this never reads, so it can't itself introduce
        an unbounded scan, but a whole-table iterable defeats the point."""
        conn.executemany(
            "INSERT INTO document_chunks (chunk_id, document_id) VALUES (?, ?)",
            rows,
        )

    @staticmethod
    def chunk_ids_for_document(
        conn: sqlite3.Connection,
        document_id: int,
    ) -> list[str]:
        return [
            row["chunk_id"]
            for row in conn.execute(
                "SELECT chunk_id FROM document_chunks WHERE document_id = ?",
                (document_id,),
            ).fetchall()
        ]

    @staticmethod
    def delete_for_document(conn: sqlite3.Connection, document_id: int) -> None:
        conn.execute(
            "DELETE FROM document_chunks WHERE document_id = ?",
            (document_id,),
        )

    @staticmethod
    def delete_all(conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM document_chunks")

    @staticmethod
    def count(conn: sqlite3.Connection) -> int:
        """Cheap stand-in for vec0's own row count -- see compact()."""
        return conn.execute("SELECT count(*) FROM document_chunks").fetchone()[0]


class DocumentMetaTable:
    """document_id -> modified, one row per document. Lives outside vec0
    because vec0 only inlines TEXT metadata up to 12 bytes and `modified`
    (an ISO timestamp) is always longer.
    """

    @staticmethod
    def create(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS document_meta "
            "(document_id INTEGER PRIMARY KEY, modified TEXT NOT NULL)",
        )

    @staticmethod
    def upsert_many(
        conn: sqlite3.Connection,
        rows: Iterable[DocumentMetaRow],
    ) -> None:
        conn.executemany(
            "INSERT INTO document_meta (document_id, modified) VALUES (?, ?) "
            "ON CONFLICT(document_id) DO UPDATE SET modified = excluded.modified",
            rows,
        )

    @staticmethod
    def delete_for_document(conn: sqlite3.Connection, document_id: int) -> None:
        conn.execute(
            "DELETE FROM document_meta WHERE document_id = ?",
            (document_id,),
        )

    @staticmethod
    def delete_all(conn: sqlite3.Connection) -> None:
        conn.execute("DELETE FROM document_meta")

    @staticmethod
    def copy_all(
        src_conn: sqlite3.Connection,
        dst_conn: sqlite3.Connection,
        batch_size: int,
    ) -> None:
        """Stream document_meta from src_conn into dst_conn in bounded
        batches. The *only* sanctioned way to move this table across
        connections (compact()/migrations) -- an unbounded fetchall here
        would defeat the same OOM-avoidance the vec0 row copy already relies
        on. batch_size has no default: forces the call site to think about
        it (pass COMPACT_BATCH_SIZE)."""
        cursor = src_conn.execute(
            "SELECT document_id, modified FROM document_meta",
        )
        while batch := cursor.fetchmany(batch_size):
            DocumentMetaTable.upsert_many(
                dst_conn,
                (DocumentMetaRow(r["document_id"], r["modified"]) for r in batch),
            )

    @staticmethod
    def all_modified_times(conn: sqlite3.Connection) -> dict[str, str]:
        """Full document_id -> modified map, for get_modified_times()'s
        public API only. One unbounded read by design (existing behavior).
        Never use this for cross-connection copying; see copy_all()."""
        return {
            str(row["document_id"]): str(row["modified"] or "")
            for row in conn.execute(
                "SELECT document_id, modified FROM document_meta",
            )
        }


class IndexMetaTable:
    """Typed accessors over index_meta's key/value rows -- replaces
    PaperlessSqliteVecVectorStore._meta_get_on/_meta_set_on, which returned
    untyped str | None regardless of whether the key held an int (dim,
    schema_version, total_inserts) or a string (embed_model).
    """

    @staticmethod
    def create(conn: sqlite3.Connection) -> None:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)",
        )

    @staticmethod
    def _get(conn: sqlite3.Connection, key: str) -> str | None:
        row = conn.execute(
            "SELECT value FROM index_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    @staticmethod
    def _set(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    @staticmethod
    def get_dim(conn: sqlite3.Connection) -> int | None:
        value = IndexMetaTable._get(conn, "dim")
        return int(value) if value is not None else None

    @staticmethod
    def set_dim(conn: sqlite3.Connection, dim: int) -> None:
        IndexMetaTable._set(conn, "dim", str(dim))

    @staticmethod
    def get_embed_model(conn: sqlite3.Connection) -> str | None:
        return IndexMetaTable._get(conn, "embed_model")

    @staticmethod
    def set_embed_model(conn: sqlite3.Connection, name: str) -> None:
        IndexMetaTable._set(conn, "embed_model", name)

    @staticmethod
    def get_schema_version(conn: sqlite3.Connection) -> int | None:
        value = IndexMetaTable._get(conn, "schema_version")
        return int(value) if value is not None else None

    @staticmethod
    def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
        IndexMetaTable._set(conn, "schema_version", str(version))

    @staticmethod
    def get_total_inserts(conn: sqlite3.Connection) -> int:
        value = IndexMetaTable._get(conn, "total_inserts")
        return int(value) if value is not None else 0

    @staticmethod
    def increment_total_inserts(conn: sqlite3.Connection, count: int) -> None:
        """Atomically add ``count`` to the stored counter in one statement
        (INSERT .. ON CONFLICT DO UPDATE with arithmetic), instead of a
        separate read-then-write -- called once per add()/upsert_document(),
        so halving the statement count here is a real, if small, per-call
        saving. index_meta.value has TEXT affinity, so the incremented
        result is stored as its text representation -- get_total_inserts()
        already expects that (int(value)), so this is not a behavior
        change, only fewer statements.
        """
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES ('total_inserts', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = "
            "CAST(index_meta.value AS INTEGER) + CAST(excluded.value AS INTEGER)",
            (str(count),),
        )

    @staticmethod
    def reset_total_inserts(conn: sqlite3.Connection, count: int) -> None:
        """Set total_inserts to an absolute value -- distinct from
        increment_total_inserts(): used by compact()'s rebuild and by
        m0001_v1_to_v2 after copying live rows into a fresh file, where
        total_inserts must become exactly the live row count, not add to
        whatever the source file's counter held."""
        IndexMetaTable._set(conn, "total_inserts", str(count))
