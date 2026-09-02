import json
import logging
import sqlite3
import struct
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import Any
from typing import NamedTuple

import sqlite_vec
from llama_index.core.bridge.pydantic import PrivateAttr
from llama_index.core.schema import BaseNode
from llama_index.core.vector_stores.types import BasePydanticVectorStore
from llama_index.core.vector_stores.types import FilterCondition
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery
from llama_index.core.vector_stores.types import VectorStoreQueryResult
from llama_index.core.vector_stores.utils import metadata_dict_to_node
from llama_index.core.vector_stores.utils import node_to_metadata_dict

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.tables import ChunkRow
from paperless_ai.tables import DocumentChunksTable
from paperless_ai.tables import DocumentMetaRow
from paperless_ai.tables import DocumentMetaTable
from paperless_ai.tables import IndexMetaTable
from paperless_ai.tables import PermittedIdsTable

logger = logging.getLogger("paperless_ai.vector_store")

DB_FILENAME = "llmindex.db"
DEFAULT_TABLE_NAME = "documents"

# Current schema version. Written to index_meta at table creation and bumped
# whenever a Migration is added to MIGRATIONS. check_and_run_migrations() uses
# this to decide which migrations to run on an existing store.
SCHEMA_VERSION = 2

# compact(): rebuild when the cumulative rowid count exceeds this multiple of
# the live row count. DELETEs on vec0 tables never reclaim space (upstream
# asg017/sqlite-vec#54), so per-document re-index churn grows the file until
# a rebuild copies the live rows into a fresh table.
COMPACT_BLOAT_RATIO = 2.0

# Number of rows fetched/copied per batch whenever this module streams rows
# instead of materializing them all at once, keeping memory bounded regardless
# of index size -- used by compact()'s rebuild, m0001_v1_to_v2's migration
# copy, and DocumentMetaTable.copy_all(). No longer compact()-specific, hence
# the plain name.
BATCH_SIZE = 500

# Filterable vec0 metadata columns. _build_where() only ever receives filter
# keys we construct ourselves, but allowlisting keeps SQL identifiers safe by
# construction. "modified" is not here: it is never filtered on, and as of
# schema v2 it isn't even a vec0 column anymore (see document_meta).
_FILTER_COLUMNS = frozenset({"document_id"})


class _Row(NamedTuple):
    """One node, ready to write. ``modified`` is not a vec0 column (see
    document_meta) -- it rides along here because every row-producing call
    site needs both the vec0 insert values and the document_meta upsert
    value from the same node.
    """

    chunk_id: str
    document_id: int
    modified: str
    node_content: str
    embedding: bytes


# _build_where(): the largest IN value list translated into a literal
# IN (?,?,...) clause. SQLite's own hard limit (SQLITE_MAX_VARIABLE_NUMBER)
# is 32766 by default; this leaves headroom below that for the query's other
# bound parameters (the embedding blob, k, and any NE clause) and for the
# limit itself to move. Above this threshold _build_where() switches to
# PermittedIdsTable instead of failing closed -- see its docstring.
_MAX_IN_VALUES = 32700


def _pack(embedding: Sequence[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


_INSERT = (
    "INSERT INTO "
    + DEFAULT_TABLE_NAME
    + " (id, document_id, node_content, embedding) VALUES (?, ?, ?, ?)"
)


def _vec0_params(rows: list[_Row]) -> list[tuple[str, int, str, bytes]]:
    """``rows``, minus the ``modified`` field vec0 no longer stores."""
    return [(r.chunk_id, r.document_id, r.node_content, r.embedding) for r in rows]


def _build_where(
    conn: sqlite3.Connection,
    filters: MetadataFilters | None,
) -> tuple[str, list[int]]:
    """Translate the EQ / IN / NIN / NE filters we use into a parameterized
    SQL clause on vec0 metadata columns. Returns ("", []) when there is
    nothing to filter. document_id is vec0's only filterable column and is
    INTEGER; every value is coerced via int() here so callers (which today
    still pass strings in places, e.g. indexing.py's MetadataFilter
    construction) don't have to be individually correct -- vec0 doesn't
    coerce types itself.

    ``conn`` is only used for an IN/NOT IN filter over _MAX_IN_VALUES: it
    loads the ids into PermittedIdsTable's TEMP TABLE on that connection
    rather than binding them as SQL parameters.
    """
    if filters is None or not filters.filters:
        return "", []
    clauses: list[str] = []
    params: list[int] = []
    for f in filters.filters:
        # filters.filters is Union[MetadataFilter, ExactMatchFilter, MetadataFilters];
        # we only build MetadataFilter entries, so skip anything else at runtime.
        if not isinstance(f, MetadataFilter):
            continue
        if f.key not in _FILTER_COLUMNS:  # pragma: no cover - we build the keys
            raise NotImplementedError(f"Unsupported filter column: {f.key}")
        if f.operator in (FilterOperator.IN, FilterOperator.NIN):
            is_in = f.operator == FilterOperator.IN
            sql_op = "IN" if is_in else "NOT IN"
            values = [int(v) for v in f.value]  # type: ignore[union-attr]
            if not values:
                # An empty IN list matches nothing; an empty NOT IN list
                # excludes nothing, so it matches everything.
                clauses.append("1 = 0" if is_in else "1 = 1")
                continue
            if len(values) > _MAX_IN_VALUES:
                # A literal list this large would exceed SQLite's own
                # bound-parameter limit. Load the ids into a TEMP TABLE on
                # this connection instead and filter via subquery, which has
                # no such limit -- see PermittedIdsTable. Applies to NOT IN
                # too (e.g. an install with an enormous trash), not just IN.
                PermittedIdsTable.load(conn, values)
                clauses.append(
                    f"{f.key} {sql_op} (SELECT id FROM {PermittedIdsTable.TABLE_NAME})",
                )
                continue
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{f.key} {sql_op} ({placeholders})")
            params.extend(values)
        elif f.operator == FilterOperator.EQ:
            clauses.append(f"{f.key} = ?")
            params.append(int(f.value))
        elif f.operator == FilterOperator.NE:
            clauses.append(f"{f.key} != ?")
            params.append(int(f.value))
        else:  # pragma: no cover - we only ever build EQ/IN/NIN/NE filters
            raise NotImplementedError(f"Unsupported filter operator: {f.operator}")
    if not clauses:
        # Filters were requested but none could be translated. Fail closed
        # rather than emit "()" (invalid SQL): filters scope document access,
        # so an empty translation must match no rows, never widen the scope.
        return "1 = 0", []
    joiner = " OR " if filters.condition == FilterCondition.OR else " AND "
    return "(" + joiner.join(clauses) + ")", params


class PaperlessSqliteVecVectorStore(BasePydanticVectorStore):
    """A llama-index vector store backed by a sqlite-vec vec0 table.

    Stores one row per node: the node id (TEXT primary key), its document id
    (metadata column, used for EQ/IN filtering and per-document delete), the
    document's modified timestamp, the embedding (float32, cosine metric), and
    the serialized node (text + metadata) as JSON in an auxiliary column.
    ``stores_text`` lets llama-index run off this store alone, with no
    separate docstore or index store.

    Everything lives in one SQLite database file (``DB_FILENAME``) inside the
    directory given as ``uri`` (kept as a directory for compatibility with the
    previous LanceDB layout). WAL mode allows readers in other processes to
    proceed while the (FileLock-serialized) writer holds a transaction.

    Implemented surface of ``BasePydanticVectorStore``
    ---------------------------------------------------
    Only the methods actively used by this codebase are implemented.
    ``delete_nodes`` and the ``node_ids`` lookup path of ``get_nodes`` are
    part of the llama-index interface contract and may be needed if a future
    retriever or extension invokes them — add them then, with tests.
    """

    stores_text: bool = True
    flat_metadata: bool = False

    _uri: str = PrivateAttr()
    _embed_model_name: str | None = PrivateAttr()
    _conn: Any = PrivateAttr()

    def __init__(
        self,
        uri: str,
        embed_model_name: str | None = None,
    ) -> None:
        super().__init__(stores_text=True, flat_metadata=False)
        self._uri = uri
        self._embed_model_name = embed_model_name
        self._conn = self._open_connection(str(Path(uri) / DB_FILENAME))

    @staticmethod
    def _open_connection(db_path: str) -> sqlite3.Connection:
        conn = sqlite3.connect(
            db_path,
            timeout=30,
            isolation_level=None,  # autocommit; explicit transactions below
        )
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)  # noqa: FBT003
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)  # noqa: FBT003
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        IndexMetaTable.create(conn)
        # vec0 metadata columns only get an efficient lookup path inside a
        # KNN (MATCH) query; a plain `WHERE document_id = ?` is a full table
        # scan regardless of index size. This plain, indexed table is how
        # delete()/upsert_document() find a document's chunk ids without
        # that scan.
        DocumentChunksTable.create(conn)
        # modified used to be a vec0 metadata column, but vec0 only inlines
        # TEXT metadata up to 12 bytes -- an ISO timestamp is always longer,
        # so every read recompiled and stepped a fresh SQL statement per row.
        # It was never filtered on inside a KNN query either, so it never
        # needed to be a vec0 column at all. One row per document here (not
        # per chunk, like document_chunks), since every chunk of a document
        # shares the same modified value -- see get_modified_times().
        DocumentMetaTable.create(conn)
        return conn

    @property
    def client(self) -> Any:
        return self._conn

    def close(self) -> None:
        """Close the underlying SQLite connection (idempotent)."""
        self._conn.close()

    def __enter__(self) -> "PaperlessSqliteVecVectorStore":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # Deterministically release the connection (and its WAL/SHM handles) so
        # it is never left open across a compaction/migration file swap.
        self.close()

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:  # pragma: no cover
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    def table_exists(self) -> bool:
        return (
            self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (DEFAULT_TABLE_NAME,),
            ).fetchone()
            is not None
        )

    def vector_dim(self) -> int | None:
        if not self.table_exists():
            return None
        return IndexMetaTable.get_dim(self._conn)

    def drop_table(self) -> None:
        self._conn.execute("DROP TABLE IF EXISTS " + DEFAULT_TABLE_NAME)
        self._conn.execute("DELETE FROM index_meta")
        DocumentChunksTable.delete_all(self._conn)
        DocumentMetaTable.delete_all(self._conn)

    def stored_model_name(self) -> str | None:
        """Return the embedding model name recorded at table creation, or None."""
        if not self.table_exists():
            return None
        return IndexMetaTable.get_embed_model(self._conn)

    def config_mismatch(self, model_name: str) -> bool:
        """True when the stored model name differs from ``model_name``.

        Returns False when no table exists or when the table predates
        model-name tracking — conservative default avoids spurious rebuilds.
        """
        stored = self.stored_model_name()
        if stored is None:
            return False
        return stored != model_name

    @staticmethod
    def _create_vec_table(conn: sqlite3.Connection, dim: int) -> None:
        # document_id is deliberately a metadata column, NOT a partition key:
        # partition keys change KNN `k` to per-partition semantics under IN
        # filters (asg017/sqlite-vec#142); metadata columns give a correct
        # global top-k. INTEGER (not TEXT, as in schema v1): EQ/NE/IN
        # comparisons become a native i64 array compare instead of per-row
        # strncmp against a 16-byte text view, and this drops the unused
        # metadatatext shadow table TEXT columns carry. modified is not a
        # column here at all as of v2 -- see document_meta.
        conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
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

    def _create_table(self, dim: int) -> None:
        self._create_vec_table(self._conn, dim)
        IndexMetaTable.set_dim(self._conn, dim)
        IndexMetaTable.set_schema_version(self._conn, SCHEMA_VERSION)
        if self._embed_model_name:
            IndexMetaTable.set_embed_model(self._conn, self._embed_model_name)

    def _ensure_table(self, dim: int, *, table_exists: bool) -> None:
        if not table_exists:
            self._create_table(dim)

    def _row(self, node: BaseNode) -> _Row:
        meta = node_to_metadata_dict(
            node,
            remove_text=False,
            flat_metadata=self.flat_metadata,
        )
        document_id = node.ref_doc_id or node.metadata.get("document_id")
        return _Row(
            chunk_id=node.node_id,
            # document_id is required -- int(None) raises TypeError and
            # int("not-a-number") raises ValueError, both intentional:
            # fail loudly on a malformed/missing document_id rather than
            # silently indexing a chunk with no owning document. modified,
            # below, still uses the str(x or "") sentinel pattern because a
            # missing modified value is legitimate (vec0 no longer even
            # stores it -- see document_meta), whereas document_id must
            # always be present.
            document_id=int(document_id),
            modified=str(node.metadata.get("modified") or ""),
            node_content=json.dumps(meta),
            embedding=_pack(node.get_embedding()),
        )

    def _index_chunks(self, rows: list[_Row]) -> None:
        """Record each row's (chunk_id, document_id) in document_chunks, and
        each row's (document_id, modified) in document_meta -- deduped
        within the batch, since every chunk of a document shares the same
        modified value -- kept in lockstep with every insert into the vec0
        table.
        """
        DocumentChunksTable.insert_many(
            self._conn,
            (ChunkRow(r.chunk_id, r.document_id) for r in rows),
        )
        modified_by_document = {r.document_id: r.modified for r in rows}
        DocumentMetaTable.upsert_many(
            self._conn,
            (
                DocumentMetaRow(doc_id, mod)
                for doc_id, mod in modified_by_document.items()
            ),
        )

    def _delete_chunks_by_document_id(self, document_id: int) -> None:
        """Delete all of a document's chunks via point-deletes on `id`.

        vec0 has no efficient lookup on the document_id metadata column
        outside a KNN query, so a plain `DELETE ... WHERE document_id = ?`
        is a full table scan regardless of index size. Looking the chunk
        ids up in document_chunks first (a real indexed lookup) and
        deleting each by its `id` primary key instead turns that scan into
        a handful of O(1) point deletes.
        """
        chunk_ids = DocumentChunksTable.chunk_ids_for_document(
            self._conn,
            document_id,
        )
        self._conn.executemany(
            "DELETE FROM " + DEFAULT_TABLE_NAME + " WHERE id = ?",
            [(chunk_id,) for chunk_id in chunk_ids],
        )
        DocumentChunksTable.delete_for_document(self._conn, document_id)
        DocumentMetaTable.delete_for_document(self._conn, document_id)

    def _increment_total_inserts(self, count: int) -> None:
        """Increment the cumulative insert counter stored in index_meta.

        This counter never decreases (DELETEs do not decrement it) and is
        used by compact() to estimate the bloat ratio: when total_inserts /
        live_rows exceeds COMPACT_BLOAT_RATIO the table has accumulated
        enough deleted-but-not-freed rows to warrant a rebuild.
        """
        IndexMetaTable.increment_total_inserts(self._conn, count)

    def add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
        if not nodes:
            return []
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            self._ensure_table(
                len(nodes[0].get_embedding()),
                table_exists=self.table_exists(),
            )
            self._conn.executemany(_INSERT, _vec0_params(rows))
            self._index_chunks(rows)
            self._increment_total_inserts(len(rows))
        return [node.node_id for node in nodes]

    def upsert_document(
        self,
        document_id: int | str,
        nodes: list[BaseNode],
    ) -> list[str]:
        """Atomically replace all stored chunks of ``document_id`` with ``nodes``.

        One transaction deletes the document's existing rows and inserts the
        new set (vec0's INSERT OR REPLACE is broken upstream, so delete+insert
        it is). WAL readers in other processes see either the old or the new
        chunk set, never a partial state.
        """
        doc_id = int(document_id)
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            table_exists = self.table_exists()
            if nodes and not table_exists:
                self._ensure_table(
                    len(nodes[0].get_embedding()),
                    table_exists=False,
                )
                table_exists = True
            if table_exists:
                self._delete_chunks_by_document_id(doc_id)
            if rows:
                self._conn.executemany(_INSERT, _vec0_params(rows))
                self._index_chunks(rows)
                self._increment_total_inserts(len(rows))
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: int | str, **delete_kwargs: Any) -> None:
        if self.table_exists():
            with self._transaction():
                self._delete_chunks_by_document_id(int(ref_doc_id))

    def _rows_to_nodes(self, rows: list[sqlite3.Row]) -> list[BaseNode]:
        nodes: list[BaseNode] = []
        for row in rows:
            node = metadata_dict_to_node(json.loads(row["node_content"]))
            node.embedding = _unpack(row["embedding"])
            nodes.append(node)
        return nodes

    def get_nodes(
        self,
        node_ids: list[str] | None = None,
        filters: MetadataFilters | None = None,
        **kwargs: Any,
    ) -> list[BaseNode]:
        if node_ids is not None:  # pragma: no cover
            # node_ids lookup is not implemented; see class docstring.
            raise NotImplementedError(
                "PaperlessSqliteVecVectorStore does not support node_ids lookup",
            )
        if not self.table_exists():
            return []
        where, params = _build_where(self._conn, filters)
        sql = "SELECT node_content, embedding FROM " + DEFAULT_TABLE_NAME
        if where:
            sql += " WHERE " + where
        return self._rows_to_nodes(self._conn.execute(sql, params).fetchall())

    def query(
        self,
        query: VectorStoreQuery,
        **kwargs: Any,
    ) -> VectorStoreQueryResult:
        if not self.table_exists():
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        if query.query_embedding is None:  # pragma: no cover
            return VectorStoreQueryResult(nodes=[], similarities=[], ids=[])
        top_k = query.similarity_top_k if query.similarity_top_k is not None else 10
        where, params = _build_where(self._conn, query.filters)
        sql = (
            "SELECT id, node_content, embedding, distance FROM "
            + DEFAULT_TABLE_NAME
            + " WHERE embedding MATCH ? AND k = ?"
        )
        if where:
            sql += " AND " + where
        rows = self._conn.execute(
            sql,
            [_pack(query.query_embedding), top_k, *params],
        ).fetchall()
        # vec0 returns rows distance-sorted ascending; slice defensively in
        # case future schema changes alter k semantics (e.g. partition keys
        # return k rows per partition).
        rows = rows[:top_k]
        nodes = self._rows_to_nodes(rows)
        # Cosine distance in [0, 2]; map to a descending similarity.
        # vec0 returns None distance when the query embedding is the zero vector
        # (no meaningful cosine angle); treat that as maximum distance (1.0) so
        # the row is included but ranked last.
        sims = [
            1.0 - float(row["distance"] if row["distance"] is not None else 1.0)
            for row in rows
        ]
        ids = [row["id"] for row in rows]
        return VectorStoreQueryResult(nodes=nodes, similarities=sims, ids=ids)

    def get_modified_times(self) -> dict[str, str]:
        """Return {document_id: stored_modified_isoformat} for all indexed documents.

        document_meta already has exactly one row per document (not per
        chunk, unlike the vec0 table), so no dedup is needed here.
        """
        if not self.table_exists():
            return {}
        return DocumentMetaTable.all_modified_times(self._conn)

    @property
    def _db_path(self) -> str:
        return str(Path(self._uri) / DB_FILENAME)

    @contextmanager
    def _rebuild_file(self) -> Iterator[sqlite3.Connection]:
        """Open a fresh temp database file for a file-swap rebuild (compact
        or structural migration), yielding its connection for the caller to
        populate.

        On success, swaps the temp file in as the live database (closing
        this store's current connection first -- see _swap_in_compact()).
        On any exception, discards the temp file, including its -wal/-shm,
        instead, and this store's own connection is left untouched.
        """
        compact_path = self._db_path + ".compact"
        new_conn = self._open_connection(compact_path)
        try:
            yield new_conn
        except BaseException:
            new_conn.close()
            for suffix in ["", "-wal", "-shm"]:
                Path(compact_path + suffix).unlink(missing_ok=True)
            raise
        else:
            new_conn.close()
            self._swap_in_compact(compact_path, self._db_path)

    def compact(self, *, force: bool = False) -> None:
        """Rebuild the database file to reclaim space left behind by DELETEs.

        vec0 DELETE only invalidates rows; the vector data stays in the file
        forever, and per-document re-indexing is a delete+insert. The
        cumulative insert counter in ``index_meta`` tracks total rows ever
        written; when that exceeds ``COMPACT_BLOAT_RATIO`` x the live row
        count (or when forced), live rows are copied into a fresh database
        file and swapped in via ``os.replace``.

        Note: ``ALTER TABLE ... RENAME TO`` on vec0 virtual tables does NOT
        rename the shadow tables (sqlite-vec upstream limitation), so an
        in-place rename-based rebuild is not safe. The file-swap approach is
        the maintainer-endorsed workaround.
        """
        if not self.table_exists():
            return
        if self.has_pending_migration():
            logger.warning(
                "Skipping compact: store has a pending schema migration; "
                "run check_and_run_migrations() first",
            )
            return
        live = DocumentChunksTable.count(self._conn)
        total = IndexMetaTable.get_total_inserts(self._conn) or live
        if not force and total <= max(live, 1) * COMPACT_BLOAT_RATIO:
            return
        dim = self.vector_dim()
        if dim is None:  # pragma: no cover - dim is written at creation
            logger.warning("Skipping compact: no stored vector dimension")
            return
        logger.info(
            "Compacting LLM index (%d live rows, %d cumulative inserts)",
            live,
            total,
        )
        with self._rebuild_file() as new_conn:
            self._rebuild_into(self._conn, new_conn, dim)

    @staticmethod
    def _rebuild_into(
        src_conn: sqlite3.Connection,
        dst_conn: sqlite3.Connection,
        dim: int,
    ) -> None:
        """Create the vec0 table in ``dst_conn``, copy dim/embed_model from
        ``src_conn``, and stream every live vec0 row, document_chunks row,
        and document_meta row across. Used by compact() only --
        m0001_v1_to_v2 freezes its own copy loop instead of calling this,
        since this always reflects the *current* schema (see the migration
        DDL-freezing rule in the spec).
        """
        PaperlessSqliteVecVectorStore._create_vec_table(dst_conn, dim)
        dim_value = IndexMetaTable.get_dim(src_conn)
        if dim_value is not None:
            IndexMetaTable.set_dim(dst_conn, dim_value)
        embed_model = IndexMetaTable.get_embed_model(src_conn)
        if embed_model is not None:
            IndexMetaTable.set_embed_model(dst_conn, embed_model)
        schema_version = IndexMetaTable.get_schema_version(src_conn)
        if schema_version is not None:
            IndexMetaTable.set_schema_version(dst_conn, schema_version)

        dst_conn.execute("BEGIN IMMEDIATE")
        src_cursor = src_conn.execute(
            "SELECT id, document_id, node_content, embedding FROM "
            + DEFAULT_TABLE_NAME,
        )
        copied = 0
        while batch := src_cursor.fetchmany(BATCH_SIZE):
            dst_conn.executemany(
                _INSERT,
                [
                    (
                        r["id"],
                        r["document_id"],
                        r["node_content"],
                        bytes(r["embedding"]),
                    )
                    for r in batch
                ],
            )
            DocumentChunksTable.insert_many(
                dst_conn,
                (ChunkRow(r["id"], r["document_id"]) for r in batch),
            )
            copied += len(batch)
        DocumentMetaTable.copy_all(src_conn, dst_conn, BATCH_SIZE)
        # Reset the cumulative counter: after a rebuild, total_inserts == live.
        IndexMetaTable.reset_total_inserts(dst_conn, copied)
        dst_conn.execute("COMMIT")

    def _swap_in_compact(self, compact_path: str, db_path: str) -> None:
        """Atomically replace the live database with the compacted copy."""
        self._conn.close()
        for suffix in ["-wal", "-shm"]:
            stale = Path(compact_path + suffix)
            if stale.exists():  # pragma: no cover
                stale.unlink()
        Path(compact_path).replace(db_path)
        self._conn = self._open_connection(db_path)

    def _stored_schema_version(self) -> int | None:
        """The schema_version recorded in index_meta, or None if no table
        exists. A missing key (a store predating version tracking) is
        treated as SCHEMA_VERSION -- i.e. already current -- since no
        migration in MIGRATIONS targets a version before tracking began.
        """
        if not self.table_exists():
            return None
        raw_version = IndexMetaTable.get_schema_version(self._conn)
        return raw_version if raw_version is not None else SCHEMA_VERSION

    def has_pending_migration(self) -> bool:
        """Cheaply check whether a migration is pending, with no exclusive
        access needed -- just a metadata read under the connection callers
        already hold via the write FileLock.

        Callers should only pay for check_and_run_migrations()'s exclusive
        access (a structural migration's file swap must not run while
        readers are active) when this returns True, so that the common
        case -- already at SCHEMA_VERSION -- never contends with readers
        or a concurrent compaction.
        """
        current = self._stored_schema_version()
        return current is not None and current < SCHEMA_VERSION

    def check_and_run_migrations(self) -> bool:
        """Apply any pending schema migrations to the store.

        Structural migrations copy live rows into a new-schema file with no
        re-embedding.  Re-embed migrations cannot be applied automatically;
        this method returns True when one is encountered so the caller can
        force a full rebuild (which recreates the table at SCHEMA_VERSION).

        Must be called under the write FileLock, with readers excluded (see
        has_pending_migration() for a cheap pre-check that avoids paying for
        that exclusion in the common case).  No-op when the table does not
        exist or is already at SCHEMA_VERSION.
        """
        current = self._stored_schema_version()
        if current is None or current >= SCHEMA_VERSION:
            return False

        pending = sorted(
            [m for m in MIGRATIONS if current <= m.from_version < SCHEMA_VERSION],
            key=lambda m: m.from_version,
        )

        for migration in pending:
            if migration.kind == "re-embed":
                logger.warning(
                    "LLM index schema v%d -> v%d requires re-embedding (%s); "
                    "the caller must force a rebuild.",
                    migration.from_version,
                    migration.to_version,
                    migration.description,
                )
                return True
            logger.info(
                "Running structural LLM index migration v%d -> v%d: %s",
                migration.from_version,
                migration.to_version,
                migration.description,
            )
            self._run_structural_migration(migration)

        return False

    def _run_structural_migration(self, migration: Migration) -> None:
        """Execute a structural migration using the same file-swap as compact()."""
        assert migration.apply is not None, "structural migration must have apply()"
        dim = self.vector_dim()
        if dim is None:  # pragma: no cover
            raise RuntimeError("Cannot migrate: no stored vector dimension")
        with self._rebuild_file() as new_conn:
            migration.apply(self._conn, new_conn, dim)
            IndexMetaTable.set_schema_version(new_conn, migration.to_version)


# Registers m0001_v1_to_v2 into MIGRATIONS; must be at the bottom (needs
# PaperlessSqliteVecVectorStore fully defined) -- see
# paperless_ai/migrations/__init__.py for the full procedure.
from paperless_ai.migrations import m0001_v1_to_v2  # noqa: E402, F401
