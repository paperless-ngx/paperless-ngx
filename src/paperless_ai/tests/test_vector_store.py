import inspect
import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest
import sqlite_vec
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery
from pytest_mock import MockerFixture

from paperless_ai.migrations import MIGRATIONS
from paperless_ai.migrations import Migration
from paperless_ai.migrations import m0001_v1_to_v2
from paperless_ai.tables import DocumentChunksTable
from paperless_ai.tables import DocumentMetaTable
from paperless_ai.vector_store import _MAX_IN_VALUES
from paperless_ai.vector_store import DB_FILENAME
from paperless_ai.vector_store import DEFAULT_TABLE_NAME
from paperless_ai.vector_store import SCHEMA_VERSION
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore
from paperless_ai.vector_store import _build_where
from paperless_ai.vector_store import _pack

DIM = 16


def make_node(
    node_id: str,
    document_id: int,
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


def _eq_filter(key: str, value: int):
    return MetadataFilters(
        filters=[MetadataFilter(key=key, operator=FilterOperator.EQ, value=value)],
    )


def _in_filter(document_ids: list[int]):
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.IN,
                value=document_ids,
            ),
        ],
    )


def _ne_filter(document_id: int):
    return MetadataFilters(
        filters=[
            MetadataFilter(
                key="document_id",
                operator=FilterOperator.NE,
                value=document_id,
            ),
        ],
    )


class TestCrud:
    def test_add_then_query_returns_node(self, store) -> None:
        node = make_node("n1", 1)
        assert store.add([node]) == ["n1"]
        result = _query(store, node.embedding, top_k=1)
        assert result.ids == ["n1"]
        assert result.nodes[0].metadata["document_id"] == 1
        # cosine distance of the identical vector is 0 -> similarity 1
        assert result.similarities[0] == pytest.approx(1.0)

    def test_query_empty_store_returns_empty_no_raise(self, store) -> None:
        result = _query(store, [0.0] * DIM)
        assert result.ids == [] and result.nodes == [] and result.similarities == []

    def test_add_empty_list_is_noop(self, store) -> None:
        assert store.add([]) == []
        assert not store.table_exists()

    def test_delete_removes_all_chunks_of_document(self, store) -> None:
        store.add([make_node("a1", 1), make_node("a2", 1), make_node("b1", 2)])
        store.delete(1)
        result = _query(store, [0.0] * DIM, top_k=10)
        assert result.ids == ["b1"]

    def test_query_with_in_filter_scopes_results(self, store) -> None:
        store.add(
            [
                make_node("a1", 1, seed=0.0),
                make_node("b1", 2, seed=1.0),
                make_node("c1", 3, seed=2.0),
            ],
        )
        result = _query(store, [0.0] * DIM, top_k=10, filters=_in_filter([2, 3]))
        assert sorted(result.ids) == ["b1", "c1"]

    def test_query_respects_top_k_with_filter(self, store) -> None:
        # k semantics: global top-k even with IN filters (document_id is a
        # metadata column, not a partition key -- see design doc).
        store.add(
            [make_node(f"n{i}", i % 4, seed=float(i)) for i in range(12)],
        )
        result = _query(
            store,
            [0.0] * DIM,
            top_k=3,
            filters=_in_filter([0, 1, 2, 3]),
        )
        assert len(result.ids) == 3
        assert result.similarities == sorted(result.similarities, reverse=True)

    def test_get_nodes_filter_and_empty_paths(self, store) -> None:
        assert store.get_nodes(filters=_in_filter([1])) == []  # no table yet
        store.add([make_node("a1", 1), make_node("b1", 2)])
        nodes = store.get_nodes(filters=_in_filter([1]))
        assert [n.node_id for n in nodes] == ["a1"]
        assert nodes[0].embedding is not None
        assert store.get_nodes(filters=_in_filter([999])) == []

    def test_query_with_eq_filter_scopes_results(self, store) -> None:
        store.add(
            [
                make_node("a1", 1, seed=0.0),
                make_node("b1", 2, seed=1.0),
                make_node("c1", 3, seed=2.0),
            ],
        )
        result = _query(
            store,
            [0.0] * DIM,
            top_k=10,
            filters=_eq_filter("document_id", 2),
        )
        assert result.ids == ["b1"]

    def test_get_nodes_node_ids_not_implemented(self, store) -> None:
        with pytest.raises(NotImplementedError):
            store.get_nodes(node_ids=["x"])

    def test_fresh_instance_sees_existing_table(self, store, tmp_path: Path) -> None:
        store.add([make_node("a1", 1)])
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.table_exists()
            assert reopened.vector_dim() == DIM
            assert _query(reopened, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_table_exists_and_drop(self, store) -> None:
        assert not store.table_exists()
        store.add([make_node("a1", 1)])
        assert store.table_exists()
        store.drop_table()
        assert not store.table_exists()
        assert store.vector_dim() is None

    def test_document_id_stored_as_integer_in_vec0(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - An empty vector store
        WHEN:
            - A node is added with an int document_id
        THEN:
            - vec0's own document_id column holds an INTEGER, not TEXT
        """
        store.add([make_node("a1", 1)])
        row = store.client.execute(
            "SELECT document_id FROM documents WHERE id = 'a1'",
        ).fetchone()
        assert isinstance(row["document_id"], int)

    def test_drop_table_clears_modified_times(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with a tracked document's modified time
        WHEN:
            - drop_table() is called
        THEN:
            - document_meta and document_chunks are both cleared directly
              (asserted against the tables themselves, not via
              get_modified_times()/table_exists() -- those short-circuit on
              the vec0 table being gone, which drop_table() does first, so
              they would pass even if DocumentMetaTable.delete_all()/
              DocumentChunksTable.delete_all() were never called)
        """
        store.add([make_node("a1", 1)])
        store.drop_table()
        assert (
            store.client.execute(
                "SELECT count(*) FROM document_meta",
            ).fetchone()[0]
            == 0
        )
        assert (
            store.client.execute(
                "SELECT count(*) FROM document_chunks",
            ).fetchone()[0]
            == 0
        )

    def test_upsert_document_checks_table_exists_once(
        self,
        store: PaperlessSqliteVecVectorStore,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An existing store with one document already indexed
        WHEN:
            - upsert_document() replaces that document's chunks
        THEN:
            - table_exists() is queried at most once per call, not twice
              (previously: once via _ensure_table(), once via the separate
              `if self.table_exists():` delete-chunks guard)
        """
        store.add([make_node("a1", 1)])
        # store is a pydantic model, whose __setattr__/__delattr__ reject
        # arbitrary instance attributes ("object has no attribute
        # 'table_exists'"), so mocker.spy(store, "table_exists") can't
        # shadow the method on the instance. Spying on the class works
        # (bound method lookup on the instance still resolves through it).
        exists_spy = mocker.spy(PaperlessSqliteVecVectorStore, "table_exists")
        store.upsert_document(1, [make_node("a2", 1)])
        assert exists_spy.call_count == 1


class TestBuildWhere:
    def test_ne_filter_translates_to_not_equal_clause(self) -> None:
        where, params = _build_where(_ne_filter(1))
        assert where == "(document_id != ?)"
        assert params == [1]

    def test_query_with_ne_filter_excludes_matching_document(self, store) -> None:
        store.add([make_node("a1", 1), make_node("b1", 2)])
        assert sorted(
            _query(store, [0.0] * DIM, top_k=5, filters=_ne_filter(1)).ids,
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
                    value=1,
                ),
            ],
        )
        where, params = _build_where(MetadataFilters(filters=[nested]))
        assert where == "1 = 0"
        assert params == []

    def test_fails_closed_when_in_filter_exceeds_max_values(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - An IN filter with more values than _MAX_IN_VALUES (SQLite's
              own bound-parameter limit is 32766; this guard sits below
              that with headroom for the query's other bound parameters)
        WHEN:
            - _build_where() translates it to SQL
        THEN:
            - It fails closed ("1 = 0", no params) instead of building an
              IN clause SQLite would reject, and logs a warning -- this
              filter scopes document access, so refusing to build it must
              never widen the scope to "everything" by accident
        """
        oversized = _in_filter([str(i) for i in range(_MAX_IN_VALUES + 1)])

        with caplog.at_level("WARNING"):
            where, params = _build_where(oversized)

        assert where == "(1 = 0)"
        assert params == []
        assert "document_id" in caplog.text

    def test_query_with_untranslatable_filter_returns_no_rows(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1 and 2
        WHEN:
            - A query and a get_nodes() call are issued with a filter whose
              only clause is an untranslatable nested MetadataFilters
        THEN:
            - Neither call raises, and both fail closed by returning no rows
              (rather than emitting invalid or unfiltered SQL)
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        nested = MetadataFilters(
            filters=[
                MetadataFilter(
                    key="document_id",
                    operator=FilterOperator.EQ,
                    value=1,
                ),
            ],
        )
        filters = MetadataFilters(filters=[nested])
        # Must not raise (no "WHERE ()") and must return nothing (fail closed).
        assert _query(store, [0.0] * DIM, top_k=5, filters=filters).ids == []
        assert store.get_nodes(filters=filters) == []


class TestUpsert:
    def test_upsert_replaces_and_prunes_stale_chunks(self, store) -> None:
        store.add(
            [make_node("d1c1", 1), make_node("d1c2", 1), make_node("d2c1", 2)],
        )
        store.upsert_document(1, [make_node("d1new", 1)])
        result = _query(store, [0.0] * DIM, top_k=10)
        assert sorted(result.ids) == ["d1new", "d2c1"]

    def test_upsert_creates_table_when_missing(self, store) -> None:
        store.upsert_document(1, [make_node("a1", 1)])
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_upsert_empty_nodes_removes_document(self, store) -> None:
        store.add([make_node("a1", 1), make_node("b1", 2)])
        store.upsert_document(1, [])
        assert _query(store, [0.0] * DIM, top_k=10).ids == ["b1"]

    def test_upsert_is_atomic_for_concurrent_readers(
        self,
        store,
        tmp_path: Path,
    ) -> None:
        """A second connection must never observe document 1 half-replaced."""
        store.add([make_node("a1", 1), make_node("a2", 1)])
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reader:
            store.upsert_document(1, [make_node("a3", 1)])
            ids = [n.node_id for n in reader.get_nodes(filters=_in_filter([1]))]
            assert ids == ["a3"]


class TestMetadataCoercion:
    def test_none_metadata_values_become_empty_strings(self, store) -> None:
        node = make_node("a1", 1)
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
            store.add([make_node("a1", 1)])
            assert store.stored_model_name() == "model-a"
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.stored_model_name() == "model-a"

    def test_config_mismatch_semantics(self, tmp_path: Path) -> None:
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            assert not store.config_mismatch("anything")  # no table yet
            store.add([make_node("a1", 1)])
            assert not store.config_mismatch("model-a")
            assert store.config_mismatch("model-b")

    def test_config_mismatch_false_when_table_predates_tracking(
        self,
        tmp_path: Path,
    ) -> None:
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:  # no model name
            store.add([make_node("a1", 1)])
            assert not store.config_mismatch("model-a")


class TestGetModifiedTimes:
    def test_empty_store_returns_empty_dict(self, store) -> None:
        assert store.get_modified_times() == {}

    def test_returns_one_entry_per_document(self, store) -> None:
        store.add(
            [
                make_node("a1", 1, modified="2026-01-01T00:00:00"),
                make_node("a2", 1, modified="2026-01-01T00:00:00"),
                make_node("b1", 2, modified="2026-02-02T00:00:00"),
            ],
        )
        assert store.get_modified_times() == {
            "1": "2026-01-01T00:00:00",
            "2": "2026-02-02T00:00:00",
        }


class TestCompact:
    def _bloat_ratio(self, store) -> float:
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

    def _churn(self, store, cycles: int) -> None:
        for i in range(cycles):
            store.upsert_document(
                1,
                [make_node(f"gen{i}-{j}", 1, seed=float(j)) for j in range(20)],
            )

    def test_compact_noop_below_threshold(self, store) -> None:
        store.add([make_node("a1", 1)])
        store.compact()
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_force_compact_preserves_rows_and_metadata(self, store) -> None:
        store.add([make_node("a1", 1), make_node("b1", 2, seed=3.0)])
        self._churn(store, 5)
        before = {
            n.node_id: n.metadata for n in store.get_nodes(filters=_in_filter([1, 2]))
        }
        store.compact(force=True)
        after = {
            n.node_id: n.metadata for n in store.get_nodes(filters=_in_filter([1, 2]))
        }
        assert after == before
        assert self._bloat_ratio(store) == pytest.approx(1.0)
        # store remains fully usable after the rebuild; use a seed far from all
        # existing nodes (gen4-0..gen4-19 have seeds 0..19) so cosine KNN is
        # unambiguous at top_k=1.
        store.upsert_document(3, [make_node("c1", 3, seed=100.0)])
        assert "c1" in _query(store, [100.0] * DIM, top_k=1).ids

    def test_auto_compact_triggers_on_churn(self, store) -> None:
        store.add([make_node(f"s{j}", 1, seed=float(j)) for j in range(20)])
        self._churn(store, 5)
        assert self._bloat_ratio(store) > 2
        store.compact()
        assert self._bloat_ratio(store) == pytest.approx(1.0)

    def test_compact_on_missing_table_is_noop(self, store) -> None:
        store.compact()
        store.compact(force=True)

    def test_failed_compact_removes_temp_wal_and_shm(
        self,
        store,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """A compact() that raises mid-rebuild must leave no .compact* files.

        Normally the sole connection's close() checkpoints the temp WAL away,
        but a concurrent reader keeps -wal/-shm alive, so the cleanup must
        unlink them explicitly (as the structural-migration path does).
        """
        store.add([make_node("a1", 1)])
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
        store,
        monkeypatch,
    ) -> None:
        """Rebuild must preserve every row when rows span multiple batches.

        A tiny batch size forces several fetchmany()/executemany() cycles so a
        regression in the streaming loop (dropped tail, off-by-one) surfaces.
        """
        monkeypatch.setattr("paperless_ai.vector_store.BATCH_SIZE", 3)
        store.add([make_node(f"n{i}", 1, seed=float(i)) for i in range(10)])
        store.compact(force=True)
        ids = {n.node_id for n in store.get_nodes(filters=_in_filter([1]))}
        assert ids == {f"n{i}" for i in range(10)}
        assert self._bloat_ratio(store) == pytest.approx(1.0)

    def test_force_compact_preserves_modified_times(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with documents whose modified times are tracked
        WHEN:
            - compact(force=True) rebuilds the database file
        THEN:
            - get_modified_times() still returns every document's value
              (document_meta must be copied across the file-swap, not just
              the vec0 rows)
        """
        store.add(
            [
                make_node("a1", 1, modified="2026-01-01T00:00:00"),
                make_node("b1", 2, modified="2026-02-02T00:00:00"),
            ],
        )
        before = store.get_modified_times()
        store.compact(force=True)
        assert store.get_modified_times() == before

    def test_compact_on_unmigrated_store_is_noop(
        self,
        store: PaperlessSqliteVecVectorStore,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A store whose schema_version has been forced behind
              SCHEMA_VERSION (has_pending_migration() is True)
        WHEN:
            - compact(force=True) is called directly, without the caller
              having run check_and_run_migrations() first
        THEN:
            - compact() is a safe no-op: no file-swap rebuild is attempted
              at all (asserted via a spy on _rebuild_into, since schema_version
              alone is not a reliable signal -- a rebuild would otherwise
              copy the stale schema_version across unchanged, making a
              before/after equality check pass even when a rebuild *did*
              happen). Rebuilding an unmigrated store would silently lose
              document_meta and leave the swapped-in file claiming the old
              schema_version -- see the class docstring rationale.
        """
        store.add([make_node("a1", 1)])
        store.client.execute(
            "UPDATE index_meta SET value = '0' WHERE key = 'schema_version'",
        )
        assert store.has_pending_migration() is True
        rebuild_spy = mocker.spy(PaperlessSqliteVecVectorStore, "_rebuild_into")
        store.compact(force=True)
        rebuild_spy.assert_not_called()
        row = store.client.execute(
            "SELECT value FROM index_meta WHERE key = 'schema_version'",
        ).fetchone()
        assert int(row["value"]) == 0


class TestDbFile:
    def test_single_db_file_in_index_dir(self, store, tmp_path: Path) -> None:
        store.add([make_node("a1", 1)])
        assert (tmp_path / DB_FILENAME).exists()

    def test_wal_mode_enabled(self, store) -> None:
        assert (
            store.client.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        )


class TestMigrations:
    """Tests for the schema migration machinery.

    These tests exercise check_and_run_migrations()'s generic dispatch logic
    (structural vs. re-embed, version-boundary stopping) using ad hoc test
    migrations layered on top of SCHEMA_VERSION -- distinct from
    TestV1ToV2Migration, which exercises the real, frozen m0001_v1_to_v2
    migration. Test migrations use version numbers starting at
    SCHEMA_VERSION (2) and above so they never collide with the real
    from_version=1/to_version=2 migration already registered in MIGRATIONS.

    The fake structural migrations' apply() fixtures (see
    test_structural_migration_copies_rows_and_updates_version and
    test_stop_at_reembed_boundary below) only populate the rebuilt vec0
    table itself -- they never insert into document_chunks/document_meta on
    the destination connection. That's fine here: these tests exist to
    verify the generic dispatch mechanism (version bookkeeping, structural-
    vs-reembed branching), not full schema correctness of a rebuilt store;
    the real migration's data completeness is covered separately by
    TestV1ToV2Migration.
    """

    def _schema_version(self, store: PaperlessSqliteVecVectorStore) -> int | None:
        row = store.client.execute(
            "SELECT value FROM index_meta WHERE key = 'schema_version'",
        ).fetchone()
        return int(row[0]) if row else None

    def test_new_table_records_schema_version(self, store) -> None:
        store.add([make_node("a1", 1)])
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_check_migrations_no_table_returns_false(self, store) -> None:
        assert store.check_and_run_migrations() is False

    def test_check_migrations_current_version_returns_false(self, store) -> None:
        store.add([make_node("a1", 1)])
        assert store.check_and_run_migrations() is False

    def test_reembed_migration_returns_true(self, store, tmp_path: Path) -> None:
        store.add([make_node("a1", 1)])
        migration = Migration(
            from_version=SCHEMA_VERSION,
            to_version=SCHEMA_VERSION + 1,
            kind="re-embed",
            description="test re-embed",
        )
        MIGRATIONS.append(migration)
        try:
            from paperless_ai import vector_store as vs_mod

            original = vs_mod.SCHEMA_VERSION
            vs_mod.SCHEMA_VERSION = SCHEMA_VERSION + 1
            result = store.check_and_run_migrations()
        finally:
            MIGRATIONS.remove(migration)
            vs_mod.SCHEMA_VERSION = original
        assert result is True

    def test_structural_migration_copies_rows_and_updates_version(
        self,
        store,
        tmp_path: Path,
    ) -> None:
        store.add([make_node("a1", 1), make_node("b1", 2)])

        def apply(
            src: sqlite3.Connection,
            dst: sqlite3.Connection,
            dim: int,
        ) -> None:
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
                "SELECT id, document_id, node_content, embedding "
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
                        str(r["document_id"]),
                        "",
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

        migration = Migration(
            from_version=SCHEMA_VERSION,
            to_version=SCHEMA_VERSION + 1,
            kind="structural",
            description="test structural",
            apply=apply,
        )
        MIGRATIONS.append(migration)
        try:
            from paperless_ai import vector_store as vs_mod

            original = vs_mod.SCHEMA_VERSION
            vs_mod.SCHEMA_VERSION = SCHEMA_VERSION + 1
            result = store.check_and_run_migrations()
        finally:
            MIGRATIONS.remove(migration)
            vs_mod.SCHEMA_VERSION = original

        assert result is False
        assert self._schema_version(store) == SCHEMA_VERSION + 1
        ids = {n.node_id for n in store.get_nodes()}
        assert ids == {"a1", "b1"}

    def test_compact_preserves_schema_version(self, store) -> None:
        store.add([make_node("a1", 1)])
        assert self._schema_version(store) == SCHEMA_VERSION
        store.compact(force=True)
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_stop_at_reembed_boundary(self, store) -> None:
        # Registry: structural v(N+1), re-embed v(N+2), structural v(N+3),
        # where N = SCHEMA_VERSION. Only v(N+1) should apply; the re-embed
        # boundary must stop execution before v(N+3) runs, and the stored
        # version must stay at N+1.
        store.add([make_node("a1", 1), make_node("b1", 2)])

        def copy_apply(
            src: sqlite3.Connection,
            dst: sqlite3.Connection,
            dim: int,
        ) -> None:
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
                "SELECT id, document_id, node_content, embedding "
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
                        str(r["document_id"]),
                        "",
                        r["node_content"],
                        bytes(r["embedding"]),
                    )
                    for r in rows
                ],
            )
            dst.execute("COMMIT")

        migrations = [
            Migration(
                from_version=SCHEMA_VERSION,
                to_version=SCHEMA_VERSION + 1,
                kind="structural",
                description="v(N+1) structural",
                apply=copy_apply,
            ),
            Migration(
                from_version=SCHEMA_VERSION + 1,
                to_version=SCHEMA_VERSION + 2,
                kind="re-embed",
                description="v(N+2) re-embed boundary",
            ),
            Migration(
                from_version=SCHEMA_VERSION + 2,
                to_version=SCHEMA_VERSION + 3,
                kind="structural",
                description="v(N+3) structural - must not run",
                apply=copy_apply,
            ),
        ]
        MIGRATIONS.extend(migrations)
        try:
            from paperless_ai import vector_store as vs_mod

            original = vs_mod.SCHEMA_VERSION
            vs_mod.SCHEMA_VERSION = SCHEMA_VERSION + 3
            result = store.check_and_run_migrations()
        finally:
            for m in migrations:
                MIGRATIONS.remove(m)
            vs_mod.SCHEMA_VERSION = original

        assert result is True
        assert self._schema_version(store) == SCHEMA_VERSION + 1

    def test_has_pending_migration_false_when_no_table(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A vector store with no table created yet
        WHEN:
            - has_pending_migration() is checked
        THEN:
            - False is returned (nothing to migrate before anything exists)
        """
        assert store.has_pending_migration() is False

    def test_has_pending_migration_false_at_current_version(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store at the current SCHEMA_VERSION
        WHEN:
            - has_pending_migration() is checked
        THEN:
            - False is returned
        """
        store.add([make_node("a1", 1)])
        assert store.has_pending_migration() is False

    def test_has_pending_migration_true_when_behind(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store whose schema_version has been forced behind SCHEMA_VERSION
        WHEN:
            - has_pending_migration() is checked
        THEN:
            - True is returned
        """
        store.add([make_node("a1", 1)])
        store.client.execute(
            "UPDATE index_meta SET value = '0' WHERE key = 'schema_version'",
        )
        assert store.has_pending_migration() is True


class TestV1ToV2Migration:
    """m0001_v1_to_v2 migrates a real, historically-shaped v1 store. The
    fixture below is a literal, hardcoded v1 DDL string -- NOT derived from
    any current code -- so this test keeps testing the actual historical
    shape even if vector_store.py's "current" schema changes again later.
    """

    def _build_v1_store(self, db_path: str, dim: int) -> None:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.enable_load_extension(True)  # noqa: FBT003
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)  # noqa: FBT003
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS index_meta (key TEXT PRIMARY KEY, value TEXT)",
        )
        conn.execute(  # nosemgrep
            "CREATE VIRTUAL TABLE documents USING vec0("
            "id TEXT PRIMARY KEY, document_id TEXT, modified TEXT,"
            f" +node_content TEXT, embedding float[{dim}] distance_metric=cosine"
            ")",
        )
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES ('dim', ?)",
            (str(dim),),
        )
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES ('schema_version', '1')",
        )
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES ('embed_model', 'model-a')",
        )
        rows = [
            ("c1", "1", "2026-01-01T00:00:00", '{"text": "a"}', _pack([0.1] * dim)),
            ("c2", "1", "2026-01-01T00:00:00", '{"text": "b"}', _pack([0.2] * dim)),
            ("c3", "2", "2026-02-02T00:00:00", '{"text": "c"}', _pack([0.3] * dim)),
        ]
        conn.executemany(
            "INSERT INTO documents (id, document_id, modified, node_content, embedding)"
            " VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.execute(
            "INSERT INTO index_meta (key, value) VALUES ('total_inserts', '3')",
        )
        conn.commit()
        conn.close()

    def test_migration_converts_v1_store_to_v2(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A real v1-shaped store (TEXT document_id, modified inline in
              vec0, no document_chunks/document_meta) built from a literal,
              hardcoded historical DDL
        WHEN:
            - A PaperlessSqliteVecVectorStore is opened against it
        THEN:
            - schema_version becomes 2, document_id values become int,
              document_chunks/document_meta are backfilled once per chunk/
              document respectively, and dim/embed_model survive
        """
        db_dir = tmp_path
        self._build_v1_store(str(db_dir / DB_FILENAME), dim=16)
        with PaperlessSqliteVecVectorStore(uri=str(db_dir)) as store:
            assert store.check_and_run_migrations() is False
            row = store.client.execute(
                "SELECT value FROM index_meta WHERE key = 'schema_version'",
            ).fetchone()
            assert int(row["value"]) == 2
            doc_id_row = store.client.execute(
                "SELECT document_id FROM documents WHERE id = 'c1'",
            ).fetchone()
            assert isinstance(doc_id_row["document_id"], int)
            assert doc_id_row["document_id"] == 1
            chunk_ids = sorted(
                r["chunk_id"]
                for r in store.client.execute(
                    "SELECT chunk_id FROM document_chunks",
                ).fetchall()
            )
            assert chunk_ids == ["c1", "c2", "c3"]
            assert store.get_modified_times() == {
                "1": "2026-01-01T00:00:00",
                "2": "2026-02-02T00:00:00",
            }
            assert store.stored_model_name() == "model-a"
            assert store.vector_dim() == 16

    def test_migration_raises_on_malformed_document_id(
        self,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - A v1-shaped store with a corrupted, non-integer document_id
              value on one row
        WHEN:
            - The migration runs
        THEN:
            - A ValueError is raised (fail loudly, no silent data loss) --
              this matches the rest of vector_store.py, which has no
              precedent for silently skipping malformed rows
        """
        db_dir = tmp_path
        self._build_v1_store(str(db_dir / DB_FILENAME), dim=16)
        conn = sqlite3.connect(str(db_dir / DB_FILENAME))
        conn.enable_load_extension(True)  # noqa: FBT003
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)  # noqa: FBT003
        conn.execute(
            "UPDATE documents SET document_id = 'not-an-int' WHERE id = 'c1'",
        )
        conn.commit()
        conn.close()
        with (
            pytest.raises(ValueError),
            PaperlessSqliteVecVectorStore(uri=str(db_dir)) as store,
        ):
            store.check_and_run_migrations()

    def test_migration_never_delegates_to_current_schema_helpers(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A real v1-shaped store
        WHEN:
            - The migration runs, with DocumentChunksTable.create/
              DocumentMetaTable.create/_create_vec_table spied on
        THEN:
            - None of those "current schema" helpers are ever called during
              the migration -- it must freeze its own historical DDL, per
              the DDL-freezing rule (see spec), so a future schema bump
              can't silently corrupt this migration's output
        """
        db_dir = tmp_path
        self._build_v1_store(str(db_dir / DB_FILENAME), dim=16)
        chunks_create_spy = mocker.spy(DocumentChunksTable, "create")
        meta_create_spy = mocker.spy(DocumentMetaTable, "create")
        vec_table_spy = mocker.spy(
            PaperlessSqliteVecVectorStore,
            "_create_vec_table",
        )
        with PaperlessSqliteVecVectorStore(uri=str(db_dir)) as store:
            store.check_and_run_migrations()
        # _open_connection() legitimately calls create() three times across
        # a structural migration: once for the store's own live connection
        # (construction), once for the migration's temp rebuild file
        # (_rebuild_file), and once more when _swap_in_compact() reopens the
        # swapped-in file as self._conn. What matters is that
        # m0001_v1_to_v2's apply() itself never calls these directly, which
        # a source-text check alone can't prove (it can't tell "mentioned in
        # a comment" from "actually called", and is trivially evadable by
        # importing a symbol under an alias). Asserting the exact call count
        # instead: exactly 3 calls to each create() (all from
        # _open_connection, never a 4th from inside apply()), and zero calls
        # to _create_vec_table (neither _open_connection nor apply() calls
        # it -- apply() freezes its own literal CREATE VIRTUAL TABLE DDL
        # instead).
        assert chunks_create_spy.call_count == 3
        assert meta_create_spy.call_count == 3
        assert vec_table_spy.call_count == 0
        # Cheap secondary signal, kept alongside the spy assertions above
        # (not in place of them): the migration module's source should never
        # even mention these "current schema" helpers by name.
        source = inspect.getsource(m0001_v1_to_v2)
        assert "DocumentChunksTable.create" not in source
        assert "DocumentMetaTable.create" not in source
        assert "_create_vec_table(" not in source
