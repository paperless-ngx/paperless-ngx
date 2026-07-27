import sqlite3
from collections.abc import Generator
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery

from paperless_ai import vector_store as vs_mod
from paperless_ai.vector_store import DB_FILENAME
from paperless_ai.vector_store import DEFAULT_TABLE_NAME
from paperless_ai.vector_store import MIGRATIONS
from paperless_ai.vector_store import SCHEMA_VERSION
from paperless_ai.vector_store import Migration
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore
from paperless_ai.vector_store import _build_where

DIM = 16


def make_node(
    node_id: str,
    document_id: str,
    *,
    modified: str = "2026-06-10T00:00:00",
    seed: float = 0.0,
    text: str = "some text",
) -> TextNode:
    node = TextNode(
        id_=node_id,
        text=text,
        metadata={"document_id": document_id, "modified": modified},
    )
    node.relationships = {}
    node.embedding = [seed + i / 100 for i in range(DIM)]
    return node


@pytest.fixture
def store(tmp_path: Path) -> Generator[PaperlessSqliteVecVectorStore, None, None]:
    with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:
        yield store


def _query(
    store: PaperlessSqliteVecVectorStore,
    embedding: list[float],
    top_k: int = 5,
    filters=None,
):
    return store.query(
        VectorStoreQuery(
            query_embedding=embedding,
            similarity_top_k=top_k,
            filters=filters,
        ),
    )


def _eq_filter(key: str, value: str):
    return MetadataFilters(
        filters=[MetadataFilter(key=key, operator=FilterOperator.EQ, value=value)],
    )


def _in_filter(document_ids: list[str]):
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.IN,
                value=document_ids,
            ),
        ],
    )


def _ne_filter(document_id: str):
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.NE,
                value=document_id,
            ),
        ],
    )


def _chunk_index_rows(
    store: PaperlessSqliteVecVectorStore,
    document_id: str | None = None,
) -> list[tuple[str, str]]:
    """The document_chunks side table, as (chunk_id, document_id) pairs."""
    sql = "SELECT chunk_id, document_id FROM document_chunks"
    params: list[str] = []
    if document_id is not None:
        sql += " WHERE document_id = ?"
        params.append(document_id)
    rows = store.client.execute(sql + " ORDER BY chunk_id", params).fetchall()
    return [(r["chunk_id"], r["document_id"]) for r in rows]


@contextmanager
def _pending_migrations(*migrations: Migration, schema_version: int) -> Iterator[None]:
    """Register ``migrations`` and raise the module's SCHEMA_VERSION for the
    duration of the block, so check_and_run_migrations() sees them as pending.
    """
    original = vs_mod.SCHEMA_VERSION
    MIGRATIONS.extend(migrations)
    vs_mod.SCHEMA_VERSION = schema_version
    try:
        yield
    finally:
        for migration in migrations:
            MIGRATIONS.remove(migration)
        vs_mod.SCHEMA_VERSION = original


def _copying_apply(src: sqlite3.Connection, dst: sqlite3.Connection, dim: int) -> None:
    """A structural migration apply() that just copies every row across.

    Deliberately spells its SQL out rather than reusing the production
    helpers, so these tests exercise the migration machinery against a
    realistic third-party apply() instead of co-drifting with it.
    """
    dst.execute(  # nosemgrep
        f"CREATE VIRTUAL TABLE {DEFAULT_TABLE_NAME} USING vec0("
        "id TEXT PRIMARY KEY, document_id TEXT, modified TEXT,"
        f" +node_content TEXT, embedding float[{dim}] distance_metric=cosine"
        ")",
    )
    dst.execute(
        "INSERT INTO index_meta (key, value) VALUES ('dim', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(dim),),
    )
    rows = src.execute(
        "SELECT id, document_id, modified, node_content, embedding "
        f"FROM {DEFAULT_TABLE_NAME}",
    ).fetchall()
    dst.execute("BEGIN IMMEDIATE")
    dst.executemany(
        f"INSERT INTO {DEFAULT_TABLE_NAME} "
        "(id, document_id, modified, node_content, embedding) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (
                r["id"],
                r["document_id"],
                r["modified"],
                r["node_content"],
                bytes(r["embedding"]),
            )
            for r in rows
        ],
    )
    dst.execute(
        "INSERT INTO index_meta (key, value) VALUES ('total_inserts', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(len(rows)),),
    )
    dst.execute("COMMIT")


class TestCrud:
    def test_add_then_query_returns_node(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        node = make_node("n1", "1")
        assert store.add([node]) == ["n1"]
        result = _query(store, node.embedding, top_k=1)
        assert result.ids == ["n1"]
        assert result.nodes[0].metadata["document_id"] == "1"
        # cosine distance of the identical vector is 0 -> similarity 1
        assert result.similarities[0] == pytest.approx(1.0)

    def test_query_empty_store_returns_empty_no_raise(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        result = _query(store, [0.0] * DIM)
        assert result.ids == [] and result.nodes == [] and result.similarities == []

    def test_add_empty_list_is_noop(self, store: PaperlessSqliteVecVectorStore) -> None:
        assert store.add([]) == []
        assert not store.table_exists()

    def test_delete_removes_all_chunks_of_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        store.delete("1")
        result = _query(store, [0.0] * DIM, top_k=10)
        assert result.ids == ["b1"]

    def test_query_with_in_filter_scopes_results(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add(
            [
                make_node("a1", "1", seed=0.0),
                make_node("b1", "2", seed=1.0),
                make_node("c1", "3", seed=2.0),
            ],
        )
        result = _query(store, [0.0] * DIM, top_k=10, filters=_in_filter(["2", "3"]))
        assert sorted(result.ids) == ["b1", "c1"]

    def test_query_respects_top_k_with_filter(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        # k semantics: global top-k even with IN filters (document_id is a
        # metadata column, not a partition key -- see design doc).
        store.add(
            [make_node(f"n{i}", str(i % 4), seed=float(i)) for i in range(12)],
        )
        result = _query(
            store,
            [0.0] * DIM,
            top_k=3,
            filters=_in_filter(["0", "1", "2", "3"]),
        )
        assert len(result.ids) == 3
        assert result.similarities == sorted(result.similarities, reverse=True)

    def test_get_nodes_filter_and_empty_paths(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        assert store.get_nodes(filters=_in_filter(["1"])) == []  # no table yet
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        nodes = store.get_nodes(filters=_in_filter(["1"]))
        assert [n.node_id for n in nodes] == ["a1"]
        assert nodes[0].embedding is not None
        assert store.get_nodes(filters=_in_filter(["999"])) == []

    def test_query_with_eq_filter_scopes_results(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add(
            [
                make_node("a1", "1", seed=0.0),
                make_node("b1", "2", seed=1.0),
                make_node("c1", "3", seed=2.0),
            ],
        )
        result = _query(
            store,
            [0.0] * DIM,
            top_k=10,
            filters=_eq_filter("document_id", "2"),
        )
        assert result.ids == ["b1"]

    def test_get_nodes_node_ids_not_implemented(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        with pytest.raises(NotImplementedError):
            store.get_nodes(node_ids=["x"])

    def test_fresh_instance_sees_existing_table(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        store.add([make_node("a1", "1")])
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.table_exists()
            assert reopened.vector_dim() == DIM
            assert _query(reopened, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_table_exists_and_drop(self, store: PaperlessSqliteVecVectorStore) -> None:
        assert not store.table_exists()
        store.add([make_node("a1", "1")])
        assert store.table_exists()
        store.drop_table()
        assert not store.table_exists()
        assert store.vector_dim() is None


class TestBuildWhere:
    def test_ne_filter_translates_to_not_equal_clause(self) -> None:
        where, params = _build_where(_ne_filter("1"))
        assert where == "(document_id != ?)"
        assert params == ["1"]

    def test_query_with_ne_filter_excludes_matching_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        assert sorted(
            _query(store, [0.0] * DIM, top_k=5, filters=_ne_filter("1")).ids,
        ) == [
            "b1",
        ]

    def test_fails_closed_when_no_filter_is_translatable(self) -> None:
        # A nested MetadataFilters is not a MetadataFilter, so it is skipped.
        # With no translatable clauses, the function must fail closed rather
        # than emit "()" (invalid SQL) and never widen document access.
        nested = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    operator=FilterOperator.EQ,
                    value="1",
                ),
            ],
        )
        where, params = _build_where(MetadataFilters(filters=[nested]))
        assert where == "1 = 0"
        assert params == []

    def test_query_with_untranslatable_filter_returns_no_rows(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        nested = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    operator=FilterOperator.EQ,
                    value="1",
                ),
            ],
        )
        filters = MetadataFilters(filters=[nested])
        # Must not raise (no "WHERE ()") and must return nothing (fail closed).
        assert _query(store, [0.0] * DIM, top_k=5, filters=filters).ids == []
        assert store.get_nodes(filters=filters) == []


class TestUpsert:
    def test_upsert_replaces_and_prunes_stale_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add(
            [make_node("d1c1", "1"), make_node("d1c2", "1"), make_node("d2c1", "2")],
        )
        store.upsert_document("1", [make_node("d1new", "1")])
        result = _query(store, [0.0] * DIM, top_k=10)
        assert sorted(result.ids) == ["d1new", "d2c1"]

    def test_upsert_creates_table_when_missing(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.upsert_document("1", [make_node("a1", "1")])
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_upsert_empty_nodes_removes_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [])
        assert _query(store, [0.0] * DIM, top_k=10).ids == ["b1"]

    def test_upsert_is_atomic_for_concurrent_readers(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """A second connection must never observe document 1 half-replaced."""
        store.add([make_node("a1", "1"), make_node("a2", "1")])
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reader:
            store.upsert_document("1", [make_node("a3", "1")])
            ids = [n.node_id for n in reader.get_nodes(filters=_in_filter(["1"]))]
            assert ids == ["a3"]


class TestDocumentChunksIndex:
    """document_chunks lets delete()/upsert_document() find a document's chunk
    ids without a vec0 full table scan on document_id -- see
    PaperlessSqliteVecVectorStore._delete_chunks_by_document_id."""

    def test_add_populates_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        assert _chunk_index_rows(store) == [
            ("a1", "1"),
            ("a2", "1"),
            ("b1", "2"),
        ]

    def test_delete_clears_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        store.delete("1")
        assert _chunk_index_rows(store) == [("b1", "2")]

    def test_upsert_replaces_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [make_node("a2", "1")])
        assert _chunk_index_rows(store) == [("a2", "1"), ("b1", "2")]

    def test_drop_table_clears_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        store.drop_table()
        assert _chunk_index_rows(store) == []


class TestMetadataCoercion:
    def test_none_metadata_values_become_empty_strings(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        node = make_node("a1", "1")
        node.metadata["modified"] = None
        store.add([node])  # must not raise (vec0 rejects NULL metadata)
        assert store.get_modified_times() == {"1": ""}


class TestModelNameTracking:
    def test_stored_model_name_none_without_table(self, tmp_path: Path) -> None:
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            assert store.stored_model_name() is None

    def test_model_name_stored_after_add_and_persists(self, tmp_path: Path) -> None:
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            store.add([make_node("a1", "1")])
            assert store.stored_model_name() == "model-a"
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.stored_model_name() == "model-a"

    def test_config_mismatch_semantics(self, tmp_path: Path) -> None:
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            assert not store.config_mismatch("anything")  # no table yet
            store.add([make_node("a1", "1")])
            assert not store.config_mismatch("model-a")
            assert store.config_mismatch("model-b")

    def test_config_mismatch_false_when_table_predates_tracking(
        self,
        tmp_path: Path,
    ) -> None:
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:  # no model name
            store.add([make_node("a1", "1")])
            assert not store.config_mismatch("model-a")


class TestGetModifiedTimes:
    def test_empty_store_returns_empty_dict(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        assert store.get_modified_times() == {}

    def test_returns_one_entry_per_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add(
            [
                make_node("a1", "1", modified="2026-01-01T00:00:00"),
                make_node("a2", "1", modified="2026-01-01T00:00:00"),
                make_node("b1", "2", modified="2026-02-02T00:00:00"),
            ],
        )
        assert store.get_modified_times() == {
            "1": "2026-01-01T00:00:00",
            "2": "2026-02-02T00:00:00",
        }


class TestCompact:
    def _bloat_ratio(self, store: PaperlessSqliteVecVectorStore) -> float:
        live = store.client.execute(
            "SELECT count(*) FROM documents",
        ).fetchone()[0]
        # vec0 0.1.9 does not accumulate deleted rows in the _rowids shadow
        # table, so we track cumulative inserts in index_meta instead.
        row = store.client.execute(
            "SELECT value FROM index_meta WHERE key = 'total_inserts'",
        ).fetchone()
        total = int(row["value"]) if row else live
        return total / max(live, 1)

    def _churn(self, store: PaperlessSqliteVecVectorStore, cycles: int) -> None:
        for i in range(cycles):
            store.upsert_document(
                "1",
                [make_node(f"gen{i}-{j}", "1", seed=float(j)) for j in range(20)],
            )

    def test_compact_noop_below_threshold(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        store.compact()
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_force_compact_preserves_rows_and_metadata(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2", seed=3.0)])
        self._churn(store, 5)
        before = {
            n.node_id: n.metadata
            for n in store.get_nodes(filters=_in_filter(["1", "2"]))
        }
        store.compact(force=True)
        after = {
            n.node_id: n.metadata
            for n in store.get_nodes(filters=_in_filter(["1", "2"]))
        }
        assert after == before
        assert self._bloat_ratio(store) == pytest.approx(1.0)
        # store remains fully usable after the rebuild; use a seed far from all
        # existing nodes (gen4-0..gen4-19 have seeds 0..19) so cosine KNN is
        # unambiguous at top_k=1.
        store.upsert_document("3", [make_node("c1", "3", seed=100.0)])
        assert "c1" in _query(store, [100.0] * DIM, top_k=1).ids

    def test_auto_compact_triggers_on_churn(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node(f"s{j}", "1", seed=float(j)) for j in range(20)])
        self._churn(store, 5)
        assert self._bloat_ratio(store) > 2
        store.compact()
        assert self._bloat_ratio(store) == pytest.approx(1.0)

    def test_compact_on_missing_table_is_noop(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.compact()
        store.compact(force=True)

    def test_compact_preserves_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """document_chunks must survive the file-swap rebuild, or delete()
        would silently stop finding chunk ids for anything indexed before a
        compaction ran."""
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        self._churn(store, 5)
        store.compact(force=True)

        assert _chunk_index_rows(store, "2") == [("b1", "2")]

        store.delete("2")
        assert "b1" not in _query(store, [0.0] * DIM, top_k=10).ids

    def test_failed_compact_removes_temp_wal_and_shm(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A compact() that raises mid-rebuild must leave no .compact* files.

        Normally the sole connection's close() checkpoints the temp WAL away,
        but a concurrent reader keeps -wal/-shm alive, so the cleanup must
        unlink them explicitly (as the structural-migration path does).
        """
        store.add([make_node("a1", "1")])
        compact_path = str(tmp_path / DB_FILENAME) + ".compact"
        held: list[sqlite3.Connection] = []

        def boom(conn: sqlite3.Connection, dim: int) -> None:
            # Hold an extra connection so close() of the rebuild connection is
            # not the last one -> the temp -wal/-shm survive the checkpoint.
            extra = sqlite3.connect(compact_path)
            extra.execute("SELECT 1").fetchall()
            held.append(extra)
            raise RuntimeError("boom")

        monkeypatch.setattr(
            PaperlessSqliteVecVectorStore,
            "_create_vec_table",
            staticmethod(boom),
        )
        try:
            with pytest.raises(RuntimeError):
                store.compact(force=True)
            assert sorted(p.name for p in tmp_path.glob("*.compact*")) == []
        finally:
            for c in held:
                c.close()

    def test_force_compact_streams_rows_across_batches(
        self,
        store: PaperlessSqliteVecVectorStore,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Rebuild must preserve every row when rows span multiple batches.

        A tiny batch size forces several fetchmany()/executemany() cycles so a
        regression in the streaming loop (dropped tail, off-by-one) surfaces.
        """
        monkeypatch.setattr("paperless_ai.vector_store.COMPACT_BATCH_SIZE", 3)
        store.add([make_node(f"n{i}", "1", seed=float(i)) for i in range(10)])
        store.compact(force=True)
        ids = {n.node_id for n in store.get_nodes(filters=_in_filter(["1"]))}
        assert ids == {f"n{i}" for i in range(10)}
        assert self._bloat_ratio(store) == pytest.approx(1.0)


class TestDbFile:
    def test_single_db_file_in_index_dir(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        store.add([make_node("a1", "1")])
        assert (tmp_path / DB_FILENAME).exists()

    def test_wal_mode_enabled(self, store: PaperlessSqliteVecVectorStore) -> None:
        assert (
            store.client.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        )


class TestMigrations:
    """Tests for the schema migration machinery."""

    def _schema_version(self, store: PaperlessSqliteVecVectorStore) -> int | None:
        row = store.client.execute(
            "SELECT value FROM index_meta WHERE key = 'schema_version'",
        ).fetchone()
        return int(row[0]) if row else None

    def test_new_table_records_schema_version(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_check_migrations_no_table_returns_false(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        assert store.check_and_run_migrations() is False

    def test_check_migrations_current_version_returns_false(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        assert store.check_and_run_migrations() is False

    def test_reembed_migration_returns_true(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        # store was just created at the real (current) SCHEMA_VERSION, so the
        # simulated pending migration must target one version past that --
        # not a hardcoded 1 -> 2, which would collide with the real
        # document_chunks migration already registered in MIGRATIONS.
        migration = Migration(
            from_version=SCHEMA_VERSION,
            to_version=SCHEMA_VERSION + 1,
            kind="re-embed",
            description="test re-embed",
        )
        with _pending_migrations(migration, schema_version=SCHEMA_VERSION + 1):
            assert store.check_and_run_migrations() is True

    def test_structural_migration_copies_rows_and_updates_version(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        migration = Migration(
            from_version=SCHEMA_VERSION,
            to_version=SCHEMA_VERSION + 1,
            kind="structural",
            description="test structural",
            apply=_copying_apply,
        )
        with _pending_migrations(migration, schema_version=SCHEMA_VERSION + 1):
            assert store.check_and_run_migrations() is False

        assert self._schema_version(store) == SCHEMA_VERSION + 1
        ids = {n.node_id for n in store.get_nodes()}
        assert ids == {"a1", "b1"}

    def test_compact_preserves_schema_version(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        store.add([make_node("a1", "1")])
        assert self._schema_version(store) == SCHEMA_VERSION
        store.compact(force=True)
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_v1_to_v2_migration_backfills_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """The real v1 -> v2 migration (registered in MIGRATIONS) must
        backfill document_chunks for rows written before it existed, or
        delete()/upsert_document() would find zero chunk ids for them and
        leave their vec0 rows orphaned forever."""
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        # Simulate a pre-migration (schema v1) store: rows exist in the vec0
        # table, but document_chunks (added by the v1 -> v2 migration) has no
        # entries for them, mirroring a real on-disk index created before
        # this migration existed.
        store.client.execute("DELETE FROM document_chunks")
        store.client.execute(
            "UPDATE index_meta SET value = '1' WHERE key = 'schema_version'",
        )

        assert store.check_and_run_migrations() is False  # structural, not re-embed
        assert self._schema_version(store) == SCHEMA_VERSION

        assert _chunk_index_rows(store) == [
            ("a1", "1"),
            ("a2", "1"),
            ("b1", "2"),
        ]

        # And delete() now actually removes rows for a document that
        # predates the migration, instead of silently no-op'ing.
        store.delete("1")
        assert sorted(_query(store, [0.0] * DIM, top_k=10).ids) == ["b1"]

    def test_stop_at_reembed_boundary(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        # Registry, relative to the store's current (real) SCHEMA_VERSION N:
        # structural N+1, re-embed N+2, structural N+3. Only N+1 should apply;
        # the re-embed boundary must stop execution before N+3 runs, and the
        # stored version must stay at N+1.
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        migrations = [
            Migration(
                from_version=SCHEMA_VERSION,
                to_version=SCHEMA_VERSION + 1,
                kind="structural",
                description="structural",
                apply=_copying_apply,
            ),
            Migration(
                from_version=SCHEMA_VERSION + 1,
                to_version=SCHEMA_VERSION + 2,
                kind="re-embed",
                description="re-embed boundary",
            ),
            Migration(
                from_version=SCHEMA_VERSION + 2,
                to_version=SCHEMA_VERSION + 3,
                kind="structural",
                description="structural - must not run",
                apply=_copying_apply,
            ),
        ]
        with _pending_migrations(*migrations, schema_version=SCHEMA_VERSION + 3):
            assert store.check_and_run_migrations() is True

        assert self._schema_version(store) == SCHEMA_VERSION + 1
