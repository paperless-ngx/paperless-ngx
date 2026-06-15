import json
import logging
import sqlite3
import struct
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from types import TracebackType
from typing import Any
from typing import Literal

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

logger = logging.getLogger("paperless_ai.vector_store")

DB_FILENAME = "llmindex.db"
DEFAULT_TABLE_NAME = "documents"

# Current schema version. Written to index_meta at table creation and bumped
# whenever a Migration is added to MIGRATIONS. check_and_run_migrations() uses
# this to decide which migrations to run on an existing store.
SCHEMA_VERSION = 1

# compact(): rebuild when the cumulative rowid count exceeds this multiple of
# the live row count. DELETEs on vec0 tables never reclaim space (upstream
# asg017/sqlite-vec#54), so per-document re-index churn grows the file until
# a rebuild copies the live rows into a fresh table.
COMPACT_BLOAT_RATIO = 2.0

# compact(): number of rows copied per executemany() when rebuilding the file.
# Rows are streamed from the source cursor in batches of this size rather than
# materialized all at once, keeping memory bounded regardless of index size.
COMPACT_BATCH_SIZE = 500

# Filterable vec0 metadata columns. _build_where() only ever receives filter
# keys we construct ourselves, but allowlisting keeps SQL identifiers safe by
# construction.
_FILTER_COLUMNS = frozenset({"document_id", "modified"})


@dataclass
class Migration:
    """A schema migration for the sqlite-vec vector store.

    kind="structural": rows are copied into a new-schema file with no
    re-embedding needed.  Supply ``apply(src_conn, dst_conn, dim)`` which
    must create the vec0 table in ``dst_conn``, copy all rows from
    ``src_conn``, and write ``dim`` / ``embed_model`` / ``total_inserts`` to
    ``dst_conn``'s ``index_meta``.  ``schema_version`` is written by the
    migration runner after ``apply`` returns.

    kind="re-embed": the new schema requires fresh embeddings.
    ``check_and_run_migrations()`` returns True when it encounters one of
    these so the caller can force a full rebuild (which recreates the table
    at the current SCHEMA_VERSION).
    """

    from_version: int
    to_version: int
    kind: Literal["structural", "re-embed"]
    description: str
    apply: Callable[[sqlite3.Connection, sqlite3.Connection, int], None] | None = field(
        default=None,
        repr=False,
    )


# Registry of all schema migrations in order. Empty at v1 -- this is the
# baseline. Add entries here (and bump SCHEMA_VERSION) when the schema changes.
MIGRATIONS: list[Migration] = []


def _pack(embedding: Sequence[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack(blob: bytes) -> list[float]:
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def _build_where(filters: MetadataFilters | None) -> tuple[str, list[str]]:
    """Translate the EQ / IN filters we use into a parameterized SQL clause
    on vec0 metadata columns. Returns ("", []) when there is nothing to filter.
    """
    if filters is None or not filters.filters:
        return "", []
    clauses: list[str] = []
    params: list[str] = []
    for f in filters.filters:
        # filters.filters is Union[MetadataFilter, ExactMatchFilter, MetadataFilters];
        # we only build MetadataFilter entries, so skip anything else at runtime.
        if not isinstance(f, MetadataFilter):
            continue
        if f.key not in _FILTER_COLUMNS:  # pragma: no cover - we build the keys
            raise NotImplementedError(f"Unsupported filter column: {f.key}")
        if f.operator == FilterOperator.IN:
            values = [str(v) for v in f.value]  # type: ignore[union-attr]  # value is list when operator is IN
            if not values:  # pragma: no cover
                clauses.append("1 = 0")
                continue
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{f.key} IN ({placeholders})")
            params.extend(values)
        elif f.operator == FilterOperator.EQ:
            clauses.append(f"{f.key} = ?")
            params.append(str(f.value))
        else:  # pragma: no cover - we only ever build EQ/IN filters
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
        conn.execute(
            "CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)",
        )
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

    def _meta_get(self, key: str) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM index_meta WHERE key = ?",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    @staticmethod
    def _meta_set_on(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def _meta_set(self, key: str, value: str) -> None:
        self._meta_set_on(self._conn, key, value)

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
        value = self._meta_get("dim")
        return int(value) if value else None

    def drop_table(self) -> None:
        self._conn.execute("DROP TABLE IF EXISTS " + DEFAULT_TABLE_NAME)
        self._conn.execute("DELETE FROM index_meta")

    def stored_model_name(self) -> str | None:
        """Return the embedding model name recorded at table creation, or None."""
        if not self.table_exists():
            return None
        return self._meta_get("embed_model")

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
        # global top-k.
        conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
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

    def _create_table(self, dim: int) -> None:
        self._create_vec_table(self._conn, dim)
        self._meta_set("dim", str(dim))
        self._meta_set("schema_version", str(SCHEMA_VERSION))
        if self._embed_model_name:
            self._meta_set("embed_model", self._embed_model_name)

    def _ensure_table(self, dim: int) -> None:
        if not self.table_exists():
            self._create_table(dim)

    def _row(self, node: BaseNode) -> tuple[str, str, str, str, bytes]:
        meta = node_to_metadata_dict(
            node,
            remove_text=False,
            flat_metadata=self.flat_metadata,
        )
        # vec0 metadata columns reject NULL (asg017/sqlite-vec#141): coerce
        # every value to a string, with "" as the absent sentinel.
        document_id = node.ref_doc_id or node.metadata.get("document_id")
        return (
            node.node_id,
            str(document_id or ""),
            str(node.metadata.get("modified") or ""),
            json.dumps(meta),
            _pack(node.get_embedding()),
        )

    _INSERT = (
        "INSERT INTO "
        + DEFAULT_TABLE_NAME
        + " (id, document_id, modified, node_content, embedding) VALUES (?, ?, ?, ?, ?)"
    )

    def _increment_total_inserts(self, count: int) -> None:
        """Increment the cumulative insert counter stored in index_meta.

        This counter never decreases (DELETEs do not decrement it) and is
        used by compact() to estimate the bloat ratio: when total_inserts /
        live_rows exceeds COMPACT_BLOAT_RATIO the table has accumulated
        enough deleted-but-not-freed rows to warrant a rebuild.
        """
        current = int(self._meta_get("total_inserts") or "0")
        self._meta_set("total_inserts", str(current + count))

    def add(self, nodes: Sequence[BaseNode], **add_kwargs: Any) -> list[str]:
        if not nodes:
            return []
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            self._ensure_table(len(nodes[0].get_embedding()))
            self._conn.executemany(self._INSERT, rows)
            self._increment_total_inserts(len(rows))
        return [node.node_id for node in nodes]

    def upsert_document(self, document_id: str, nodes: list[BaseNode]) -> list[str]:
        """Atomically replace all stored chunks of ``document_id`` with ``nodes``.

        One transaction deletes the document's existing rows and inserts the
        new set (vec0's INSERT OR REPLACE is broken upstream, #259, so
        delete+insert it is). WAL readers in other processes see either the
        old or the new chunk set, never a partial state.
        """
        rows = [self._row(node) for node in nodes]
        with self._transaction():
            if nodes:
                self._ensure_table(len(nodes[0].get_embedding()))
            if self.table_exists():
                self._conn.execute(
                    "DELETE FROM " + DEFAULT_TABLE_NAME + " WHERE document_id = ?",
                    (str(document_id),),
                )
            if rows:
                self._conn.executemany(self._INSERT, rows)
                self._increment_total_inserts(len(rows))
        return [node.node_id for node in nodes]

    def delete(self, ref_doc_id: str, **delete_kwargs: Any) -> None:
        if self.table_exists():
            with self._transaction():
                self._conn.execute(
                    "DELETE FROM " + DEFAULT_TABLE_NAME + " WHERE document_id = ?",
                    (str(ref_doc_id),),
                )

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
        where, params = _build_where(filters)
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
        where, params = _build_where(query.filters)
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

        All chunks of a document share the same ``modified`` value, so the
        first row seen per document is sufficient.
        """
        if not self.table_exists():
            return {}
        result: dict[str, str] = {}
        for row in self._conn.execute(
            "SELECT document_id, modified FROM " + DEFAULT_TABLE_NAME,
        ):
            doc_id = str(row["document_id"])
            if doc_id not in result:
                result[doc_id] = str(row["modified"] or "")
        return result

    def compact(self, *, force: bool = False) -> None:
        """Rebuild the database file to reclaim space left behind by DELETEs.

        vec0 DELETE only invalidates rows; the vector data stays in the file
        forever (asg017/sqlite-vec#54), and per-document re-indexing is a
        delete+insert. The cumulative insert counter in ``index_meta`` tracks
        total rows ever written; when that exceeds ``COMPACT_BLOAT_RATIO`` x
        the live row count (or when forced), live rows are copied into a fresh
        database file and swapped in via ``os.replace``.

        Note: ``ALTER TABLE ... RENAME TO`` on vec0 virtual tables does NOT
        rename the shadow tables (sqlite-vec upstream limitation), so
        an in-place rename-based rebuild is not safe.  The file-swap approach
        is the maintainer-endorsed workaround (asg017/sqlite-vec#205).
        """
        if not self.table_exists():
            return
        live = self._conn.execute(
            "SELECT count(*) FROM " + DEFAULT_TABLE_NAME,
        ).fetchone()[0]
        total = int(self._meta_get("total_inserts") or str(live))
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
        db_path = str(Path(self._uri) / DB_FILENAME)
        compact_path = db_path + ".compact"

        # Copy all live rows into a fresh database file.
        new_conn = self._open_connection(compact_path)
        try:
            self._create_vec_table(new_conn, dim)
            self._meta_set_on(new_conn, "dim", str(dim))
            for key in ("embed_model", "schema_version"):
                value = self._meta_get(key)
                if value is not None:
                    self._meta_set_on(new_conn, key, value)
            src_cursor = self._conn.execute(
                "SELECT id, document_id, modified, node_content, embedding "
                "FROM " + DEFAULT_TABLE_NAME,
            )
            new_conn.execute("BEGIN IMMEDIATE")
            # Stream rows from the source cursor in batches instead of
            # materializing the whole table in memory, so a large index does
            # not cause an OOM during routine maintenance compactions.
            while batch := src_cursor.fetchmany(COMPACT_BATCH_SIZE):
                new_conn.executemany(
                    self._INSERT,
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
            # Reset the cumulative counter: after compact, total_inserts == live.
            self._meta_set_on(new_conn, "total_inserts", str(live))
            new_conn.execute("COMMIT")
        except BaseException:
            new_conn.close()
            for p in [compact_path, compact_path + "-wal", compact_path + "-shm"]:
                Path(p).unlink(missing_ok=True)
            raise
        new_conn.close()
        self._swap_in_compact(compact_path, db_path)

    def _swap_in_compact(self, compact_path: str, db_path: str) -> None:
        """Atomically replace the live database with the compacted copy."""
        self._conn.close()
        for suffix in ["-wal", "-shm"]:
            stale = Path(compact_path + suffix)
            if stale.exists():  # pragma: no cover
                stale.unlink()
        Path(compact_path).replace(db_path)
        self._conn = self._open_connection(db_path)

    def check_and_run_migrations(self) -> bool:
        """Apply any pending schema migrations to the store.

        Structural migrations copy live rows into a new-schema file with no
        re-embedding.  Re-embed migrations cannot be applied automatically;
        this method returns True when one is encountered so the caller can
        force a full rebuild (which recreates the table at SCHEMA_VERSION).

        Must be called under the write FileLock.  No-op when the table does
        not exist or is already at SCHEMA_VERSION.
        """
        if not self.table_exists():
            return False

        raw = self._meta_get("schema_version")
        current = int(raw) if raw is not None else SCHEMA_VERSION
        if current >= SCHEMA_VERSION:
            return False

        pending = sorted(
            [m for m in MIGRATIONS if current <= m.from_version < SCHEMA_VERSION],
            key=lambda m: m.from_version,
        )

        for migration in pending:
            if migration.kind == "re-embed":
                logger.warning(
                    "LLM index schema v%d -> v%d requires re-embedding (%s); "
                    "forcing full rebuild.",
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
        db_path = str(Path(self._uri) / DB_FILENAME)
        compact_path = db_path + ".compact"
        new_conn = self._open_connection(compact_path)
        try:
            migration.apply(self._conn, new_conn, dim)
            self._meta_set_on(new_conn, "schema_version", str(migration.to_version))
        except BaseException:  # pragma: no cover
            new_conn.close()
            for p in [compact_path, compact_path + "-wal", compact_path + "-shm"]:
                Path(p).unlink(missing_ok=True)
            raise
        new_conn.close()
        self._swap_in_compact(compact_path, db_path)
