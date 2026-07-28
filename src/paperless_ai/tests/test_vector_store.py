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
    return [(r["chunk_id"], str(r["document_id"])) for r in rows]


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
        """
        GIVEN:
            - An empty vector store
        WHEN:
            - A single node is added and then queried with its own embedding
        THEN:
            - The node id, metadata, and a cosine similarity of 1.0 are returned
        """
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
        """
        GIVEN:
            - A vector store with no table created yet
        WHEN:
            - A query is issued
        THEN:
            - Empty ids, nodes, and similarities are returned without raising
        """
        result = _query(store, [0.0] * DIM)
        assert result.ids == [] and result.nodes == [] and result.similarities == []

    def test_add_empty_list_is_noop(self, store: PaperlessSqliteVecVectorStore) -> None:
        """
        GIVEN:
            - A vector store with no table created yet
        WHEN:
            - add() is called with an empty list of nodes
        THEN:
            - No ids are returned and the table is not created
        """
        assert store.add([]) == []
        assert not store.table_exists()

    def test_delete_removes_all_chunks_of_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with two chunks for document 1 and one chunk for document 2
        WHEN:
            - delete() is called for document 1
        THEN:
            - Only document 2's chunk remains queryable
        """
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        store.delete("1")
        result = _query(store, [0.0] * DIM, top_k=10)
        assert result.ids == ["b1"]

    def test_query_with_in_filter_scopes_results(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1, 2, and 3
        WHEN:
            - A query is issued with an IN filter on documents 2 and 3
        THEN:
            - Only chunks belonging to documents 2 and 3 are returned
        """
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
        """
        GIVEN:
            - A store with 12 chunks spread across 4 documents
        WHEN:
            - A query is issued with top_k=3 and an IN filter covering all 4
              documents
        THEN:
            - Exactly 3 results are returned, ranked by similarity (global
              top-k even under an IN filter, since document_id is a metadata
              column, not a partition key)
        """
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
        """
        GIVEN:
            - A store that starts with no table, then has chunks for
              documents 1 and 2 added
        WHEN:
            - get_nodes() is called before the table exists, filtered to
              document 1, and filtered to a document id that doesn't exist
        THEN:
            - Each call returns the expected embedding-bearing nodes or an
              empty list, without raising
        """
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
        """
        GIVEN:
            - A store with one chunk each for documents 1, 2, and 3
        WHEN:
            - A query is issued with an EQ filter on document 2
        THEN:
            - Only document 2's chunk is returned
        """
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
        """
        GIVEN:
            - A vector store
        WHEN:
            - get_nodes() is called with node_ids (an unsupported lookup mode)
        THEN:
            - NotImplementedError is raised
        """
        with pytest.raises(NotImplementedError):
            store.get_nodes(node_ids=["x"])

    def test_fresh_instance_sees_existing_table(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk already written to disk
        WHEN:
            - A new PaperlessSqliteVecVectorStore instance is opened against
              the same directory
        THEN:
            - The new instance sees the existing table, dimension, and node
        """
        store.add([make_node("a1", "1")])
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.table_exists()
            assert reopened.vector_dim() == DIM
            assert _query(reopened, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_table_exists_and_drop(self, store: PaperlessSqliteVecVectorStore) -> None:
        """
        GIVEN:
            - A fresh store with no table
        WHEN:
            - A node is added, then drop_table() is called
        THEN:
            - table_exists() and vector_dim() reflect the table's creation and
              subsequent removal
        """
        assert not store.table_exists()
        store.add([make_node("a1", "1")])
        assert store.table_exists()
        store.drop_table()
        assert not store.table_exists()
        assert store.vector_dim() is None


class TestBuildWhere:
    def test_ne_filter_translates_to_not_equal_clause(self) -> None:
        """
        GIVEN:
            - A NE MetadataFilter on document_id
        WHEN:
            - _build_where() translates it to SQL
        THEN:
            - A parameterized "!=" clause is produced
        """
        where, params = _build_where(_ne_filter("1"))
        assert where == "(document_id != ?)"
        assert params == ["1"]

    def test_query_with_ne_filter_excludes_matching_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1 and 2
        WHEN:
            - A query is issued with a NE filter on document 1
        THEN:
            - Only document 2's chunk is returned
        """
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
        """
        GIVEN:
            - A store with two chunks for document 1 and one for document 2
        WHEN:
            - upsert_document() replaces document 1's chunks with a single new
              chunk
        THEN:
            - Querying returns only the new chunk for document 1 and the
              untouched chunk for document 2; the stale chunks are gone
        """
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
        """
        GIVEN:
            - A store with no table yet
        WHEN:
            - upsert_document() is called for a document with one node
        THEN:
            - The table is created and the node is queryable
        """
        store.upsert_document("1", [make_node("a1", "1")])
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_upsert_empty_nodes_removes_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1 and 2
        WHEN:
            - upsert_document() is called for document 1 with an empty node
              list
        THEN:
            - Document 1's chunk is removed and only document 2's remains
              queryable
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [])
        assert _query(store, [0.0] * DIM, top_k=10).ids == ["b1"]

    def test_upsert_is_atomic_for_concurrent_readers(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """A second connection must never observe document 1 half-replaced.

        GIVEN:
            - A store with two chunks for document 1, and a second reader
              connection open against the same database
        WHEN:
            - upsert_document() replaces document 1's chunks on the writer
              connection
        THEN:
            - The reader connection only ever observes the fully-replaced
              state, never a partial mix of old and new chunks
        """
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
        """
        GIVEN:
            - An empty store
        WHEN:
            - add() writes chunks for documents 1 and 2
        THEN:
            - document_chunks records a (chunk_id, document_id) row for every
              chunk written
        """
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
        """
        GIVEN:
            - A store with two chunks for document 1 and one for document 2
        WHEN:
            - delete() removes document 1
        THEN:
            - document_chunks no longer has rows for document 1, but retains
              document 2's row
        """
        store.add([make_node("a1", "1"), make_node("a2", "1"), make_node("b1", "2")])
        store.delete("1")
        assert _chunk_index_rows(store) == [("b1", "2")]

    def test_upsert_replaces_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1 and 2
        WHEN:
            - upsert_document() replaces document 1's chunk with a new one
        THEN:
            - document_chunks reflects only the new chunk for document 1,
              alongside the untouched row for document 2
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [make_node("a2", "1")])
        assert _chunk_index_rows(store) == [("a2", "1"), ("b1", "2")]

    def test_drop_table_clears_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk indexed
        WHEN:
            - drop_table() is called
        THEN:
            - document_chunks is emptied along with the vec0 table
        """
        store.add([make_node("a1", "1")])
        store.drop_table()
        assert _chunk_index_rows(store) == []

    def test_delete_never_indexed_document_is_noop(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with chunks for documents 1 and 2, but none for a
              document id that was never indexed
        WHEN:
            - delete() is called for that never-indexed document id
        THEN:
            - document_chunks is unchanged; no error is raised and no other
              document's rows are touched
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.delete("never-indexed")
        assert _chunk_index_rows(store) == [("a1", "1"), ("b1", "2")]

    def test_upsert_empty_nodes_clears_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with one chunk each for documents 1 and 2
        WHEN:
            - upsert_document() is called for document 1 with an empty node
              list
        THEN:
            - document_chunks no longer has rows for document 1, but retains
              document 2's row
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        store.upsert_document("1", [])
        assert _chunk_index_rows(store) == [("b1", "2")]


class TestMetadataCoercion:
    def test_none_metadata_values_become_empty_strings(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A node whose "modified" metadata value is None
        WHEN:
            - The node is added
        THEN:
            - No error is raised (vec0 rejects NULL metadata) and the stored
              modified time is an empty string
        """
        node = make_node("a1", "1")
        node.metadata["modified"] = None
        store.add([node])  # must not raise (vec0 rejects NULL metadata)
        assert store.get_modified_times() == {"1": ""}


class TestModelNameTracking:
    def test_stored_model_name_none_without_table(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A store configured with an embed_model_name but no table
              created yet
        WHEN:
            - stored_model_name() is called
        THEN:
            - None is returned, since nothing has been persisted
        """
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            assert store.stored_model_name() is None

    def test_model_name_stored_after_add_and_persists(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A store configured with an embed_model_name
        WHEN:
            - A node is added, and the store is later reopened against the
              same directory without specifying a model name
        THEN:
            - stored_model_name() returns the original model name in both
              cases
        """
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            store.add([make_node("a1", "1")])
            assert store.stored_model_name() == "model-a"
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as reopened:
            assert reopened.stored_model_name() == "model-a"

    def test_config_mismatch_semantics(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A store configured with embed_model_name "model-a"
        WHEN:
            - config_mismatch() is checked before the table exists, then
              after adding a node, against both the matching and a different
              model name
        THEN:
            - No mismatch is reported before the table exists or against the
              matching name; a mismatch is reported against the different name
        """
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
        """
        GIVEN:
            - A store created without an embed_model_name (as if the table
              predates model-name tracking)
        WHEN:
            - config_mismatch() is checked against a model name after adding
              a node
        THEN:
            - No mismatch is reported, since there is no recorded model name
              to compare against
        """
        with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:  # no model name
            store.add([make_node("a1", "1")])
            assert not store.config_mismatch("model-a")


class TestGetModifiedTimes:
    def test_empty_store_returns_empty_dict(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - An empty store
        WHEN:
            - get_modified_times() is called
        THEN:
            - An empty dict is returned
        """
        assert store.get_modified_times() == {}

    def test_returns_one_entry_per_document(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with two chunks for document 1 (same modified time) and
              one chunk for document 2 (a different modified time)
        WHEN:
            - get_modified_times() is called
        THEN:
            - One entry per document id is returned, each with its modified
              time
        """
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
        """
        GIVEN:
            - A store with a single chunk, far below the compaction threshold
        WHEN:
            - compact() is called
        THEN:
            - The store is left usable and the chunk remains queryable
        """
        store.add([make_node("a1", "1")])
        store.compact()
        assert _query(store, [0.0] * DIM, top_k=1).ids == ["a1"]

    def test_force_compact_preserves_rows_and_metadata(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with chunks for two documents, one of which has been
              churned through several upsert generations
        WHEN:
            - compact(force=True) rebuilds the index
        THEN:
            - Every live node and its metadata survive unchanged, the bloat
              ratio drops back to 1.0, and the store remains usable for
              further writes and queries afterward
        """
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
        """
        GIVEN:
            - A store churned through enough upsert generations that its
              bloat ratio exceeds the auto-compact threshold
        WHEN:
            - compact() is called without force=True
        THEN:
            - The store compacts automatically, dropping the bloat ratio back
              to 1.0
        """
        store.add([make_node(f"s{j}", "1", seed=float(j)) for j in range(20)])
        self._churn(store, 5)
        assert self._bloat_ratio(store) > 2
        store.compact()
        assert self._bloat_ratio(store) == pytest.approx(1.0)

    def test_compact_on_missing_table_is_noop(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with no table created yet
        WHEN:
            - compact() and compact(force=True) are both called
        THEN:
            - Neither call raises
        """
        store.compact()
        store.compact(force=True)

    def test_compact_preserves_document_chunks(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """document_chunks must survive the file-swap rebuild, or delete()
        would silently stop finding chunk ids for anything indexed before a
        compaction ran.

        GIVEN:
            - A store with an untouched chunk for document 2 and a chunk for
              document 1 that has been churned through 5 upsert generations
        WHEN:
            - compact(force=True) rebuilds the index
        THEN:
            - document_chunks still has document 2's row, and document 1's
              rows match only its final upsert generation (no stale ids from
              earlier generations); delete() still works afterward
        """
        store.add([make_node("a1", "1"), make_node("b1", "2")])
        self._churn(store, 5)
        store.compact(force=True)

        assert _chunk_index_rows(store, "2") == [("b1", "2")]

        # document "1" was upserted 5x before compaction (gen0..gen4); only
        # its final generation's chunk ids should remain in document_chunks,
        # not stale ids from earlier upsert generations.
        assert _chunk_index_rows(store, "1") == sorted(
            (f"gen4-{j}", "1") for j in range(20)
        )

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

        GIVEN:
            - A store with one chunk, and a rebuild step patched to raise
              after opening an extra connection to the temp compact file
              (keeping its -wal/-shm alive past the raising connection's
              close())
        WHEN:
            - compact(force=True) is called
        THEN:
            - RuntimeError propagates, and no .compact/.compact-wal/.compact-shm
              files remain in the index directory
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

        GIVEN:
            - A store with 10 chunks and a COMPACT_BATCH_SIZE small enough
              that the rebuild must stream several fetchmany()/executemany()
              batches
        WHEN:
            - compact(force=True) is called
        THEN:
            - Every row survives the rebuild and the bloat ratio settles at
              1.0
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
        """
        GIVEN:
            - A fresh store directory
        WHEN:
            - A node is added
        THEN:
            - The expected single db file exists in the index directory
        """
        store.add([make_node("a1", "1")])
        assert (tmp_path / DB_FILENAME).exists()

    def test_wal_mode_enabled(self, store: PaperlessSqliteVecVectorStore) -> None:
        """
        GIVEN:
            - A freshly opened store
        WHEN:
            - The connection's journal_mode pragma is checked
        THEN:
            - WAL mode is enabled
        """
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
        """
        GIVEN:
            - A store with no table yet
        WHEN:
            - A node is added, creating the table
        THEN:
            - The store's schema_version is recorded as the current
              SCHEMA_VERSION
        """
        store.add([make_node("a1", "1")])
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_check_migrations_no_table_returns_false(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store with no table yet
        WHEN:
            - check_and_run_migrations() is called
        THEN:
            - False is returned (nothing to migrate)
        """
        assert store.check_and_run_migrations() is False

    def test_check_migrations_current_version_returns_false(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store already at the current SCHEMA_VERSION
        WHEN:
            - check_and_run_migrations() is called
        THEN:
            - False is returned (no pending migration)
        """
        store.add([make_node("a1", "1")])
        assert store.check_and_run_migrations() is False

    def test_reembed_migration_returns_true(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store at the current SCHEMA_VERSION with a pending re-embed
              migration registered one version ahead
        WHEN:
            - check_and_run_migrations() is called
        THEN:
            - True is returned, signaling the caller must force a full
              rebuild
        """
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
        """
        GIVEN:
            - A store at the current SCHEMA_VERSION with two chunks, and a
              pending structural migration registered one version ahead
        WHEN:
            - check_and_run_migrations() is called
        THEN:
            - False is returned (no rebuild needed by the caller), the
              schema_version advances, and every row survives the migration
        """
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
        """
        GIVEN:
            - A store at the current SCHEMA_VERSION with one chunk
        WHEN:
            - compact(force=True) rebuilds the index
        THEN:
            - schema_version is unchanged after the rebuild
        """
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
        leave their vec0 rows orphaned forever.

        GIVEN:
            - A store simulating a pre-migration (schema v1) index: rows
              exist in the vec0 table, but document_chunks is empty and
              schema_version is forced back to 1
        WHEN:
            - check_and_run_migrations() is called, then delete() removes one
              of the pre-migration documents, then
              check_and_run_migrations() is called again
        THEN:
            - The first call backfills document_chunks for every
              pre-migration row and advances schema_version to current;
              delete() correctly removes the pre-migration document's rows
              instead of silently no-op'ing; the second call is a no-op that
              leaves schema_version unchanged
        """
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

        # Running the check again post-migration must be a no-op: the store
        # is already at SCHEMA_VERSION, so this just hits the
        # current-version early return, not the migration logic a second
        # time.
        assert store.check_and_run_migrations() is False
        assert self._schema_version(store) == SCHEMA_VERSION

    def test_v1_to_v2_migration_preserves_embed_model_name(
        self,
        tmp_path: Path,
    ) -> None:
        """embed_model tracking (see TestModelNameTracking) predates the v1 ->
        v2 migration and must survive it, or a migrated store would silently
        stop detecting embedding-model config changes.

        GIVEN:
            - A store configured with an embed_model_name, simulated as a
              pre-migration (schema v1) index with document_chunks emptied
              and schema_version forced back to 1
        WHEN:
            - check_and_run_migrations() runs the v1 -> v2 migration
        THEN:
            - schema_version advances to current and stored_model_name()
              still returns the original embed_model_name
        """
        with PaperlessSqliteVecVectorStore(
            uri=str(tmp_path),
            embed_model_name="model-a",
        ) as store:
            store.add([make_node("a1", "1")])
            store.client.execute("DELETE FROM document_chunks")
            store.client.execute(
                "UPDATE index_meta SET value = '1' WHERE key = 'schema_version'",
            )

            assert store.check_and_run_migrations() is False
            assert self._schema_version(store) == SCHEMA_VERSION
            assert store.stored_model_name() == "model-a"

    def test_stop_at_reembed_boundary(
        self,
        store: PaperlessSqliteVecVectorStore,
    ) -> None:
        """
        GIVEN:
            - A store at the current SCHEMA_VERSION N with three pending
              migrations registered: structural N+1, re-embed N+2, structural
              N+3
        WHEN:
            - check_and_run_migrations() is called
        THEN:
            - True is returned (re-embed needed), only the N+1 structural
              migration actually runs, and schema_version stops at N+1 --
              the N+3 migration must not run before the caller has forced a
              rebuild for the re-embed boundary
        """
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
