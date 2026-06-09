import json
from pathlib import Path
from typing import Any

import pytest
import pytest_mock
from llama_index.core.schema import NodeRelationship
from llama_index.core.schema import RelatedNodeInfo
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import FilterOperator
from llama_index.core.vector_stores.types import MetadataFilter
from llama_index.core.vector_stores.types import MetadataFilters
from llama_index.core.vector_stores.types import VectorStoreQuery

from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION
from paperless_ai.vector_store import PaperlessLanceVectorStore

DIM = 8


@pytest.fixture
def store(tmp_path: Path) -> PaperlessLanceVectorStore:
    return PaperlessLanceVectorStore(uri=str(tmp_path / "idx"))


def _node(node_id: str, document_id: str, text: str, vec: float) -> TextNode:
    node = TextNode(id_=node_id, text=text, metadata={"document_id": document_id})
    node.set_content(text)
    node.embedding = [vec] * DIM
    # Use relationships so ref_doc_id resolves correctly (it's a read-only property)
    node.relationships = {
        NodeRelationship.SOURCE: RelatedNodeInfo(node_id=document_id),
    }
    return node


class TestPaperlessLanceVectorStoreCrud:
    def test_add_then_query_returns_node(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "alpha", 0.1), _node("2-0", "2", "beta", 0.9)])

        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=1),
        )

        assert len(result.nodes) == 1
        assert result.nodes[0].metadata["document_id"] == "1"

    def test_query_empty_table_returns_empty_no_raise(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=5),
        )
        assert result.nodes == []
        assert result.ids == []

    def test_delete_removes_all_chunks_of_document(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1), _node("1-1", "1", "b", 0.2)])
        store.add([_node("2-0", "2", "c", 0.9)])

        store.delete("1")

        assert store.client.open_table("documents").count_rows() == 1

    def test_query_with_in_filter_scopes_results(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1), _node("2-0", "2", "b", 0.1)])

        result = store.query(
            VectorStoreQuery(
                query_embedding=[0.1] * DIM,
                similarity_top_k=5,
                filters=MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="document_id",
                            operator=FilterOperator.IN,
                            value=["2"],
                        ),
                    ],
                ),
            ),
        )

        assert [n.metadata["document_id"] for n in result.nodes] == ["2"]

    def test_get_nodes_filter_returns_empty_cleanly(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1)])
        nodes = store.get_nodes(
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="document_id",
                        operator=FilterOperator.IN,
                        value=["999"],
                    ),
                ],
            ),
        )
        assert nodes == []

    def test_get_nodes_returns_empty_when_no_table(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        result = store.get_nodes(
            filters=MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="document_id",
                        operator=FilterOperator.IN,
                        value=["1"],
                    ),
                ],
            ),
        )
        assert result == []

    def test_fresh_instance_filters_existing_table(
        self,
        tmp_path: Path,
    ) -> None:
        uri = str(tmp_path / "idx")
        PaperlessLanceVectorStore(uri=uri).add(
            [_node("1-0", "1", "a", 0.1), _node("2-0", "2", "b", 0.1)],
        )

        reopened = PaperlessLanceVectorStore(uri=uri)
        result = reopened.query(
            VectorStoreQuery(
                query_embedding=[0.1] * DIM,
                similarity_top_k=5,
                filters=MetadataFilters(
                    filters=[
                        MetadataFilter(
                            key="document_id",
                            operator=FilterOperator.IN,
                            value=["1"],
                        ),
                    ],
                ),
            ),
        )
        assert [n.metadata["document_id"] for n in result.nodes] == ["1"]

    def test_table_exists_and_drop(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        assert store.table_exists() is False
        store.add([_node("1-0", "1", "a", 0.1)])
        assert store.table_exists() is True
        assert store.vector_dim() == DIM
        store.drop_table()
        assert store.table_exists() is False

    def test_build_where_or_condition(self) -> None:
        from llama_index.core.vector_stores.types import FilterCondition

        from paperless_ai.vector_store import _build_where

        where = _build_where(
            MetadataFilters(
                filters=[
                    MetadataFilter(
                        key="document_id",
                        operator=FilterOperator.EQ,
                        value="1",
                    ),
                    MetadataFilter(
                        key="document_id",
                        operator=FilterOperator.EQ,
                        value="2",
                    ),
                ],
                condition=FilterCondition.OR,
            ),
        )
        assert where == "document_id = '1' OR document_id = '2'"


class TestPaperlessLanceVectorStoreUpsert:
    @pytest.fixture
    def filled_store(
        self,
        store: PaperlessLanceVectorStore,
    ) -> PaperlessLanceVectorStore:
        store.add(
            [
                _node("1-0", "1", "old0", 0.1),
                _node("1-1", "1", "old1", 0.2),
                _node("1-2", "1", "old2", 0.3),
                _node("2-0", "2", "keep", 0.9),
            ],
        )
        return store

    def test_upsert_prunes_stale_chunks_and_keeps_others(
        self,
        filled_store: PaperlessLanceVectorStore,
    ) -> None:
        filled_store.upsert_document(
            "1",
            [_node("1-0", "1", "new0", 0.1), _node("1-1", "1", "new1", 0.2)],
        )

        table = filled_store.client.open_table("documents")
        doc1 = sorted(
            r["id"] for r in table.search().where("document_id = '1'").to_list()
        )
        assert doc1 == ["1-0", "1-1"]  # 1-2 pruned
        assert table.count_rows() == 3  # 2 new doc1 + 1 doc2

    def test_upsert_is_single_commit(
        self,
        filled_store: PaperlessLanceVectorStore,
    ) -> None:
        table = filled_store.client.open_table("documents")
        before = table.version
        filled_store.upsert_document("1", [_node("1-0", "1", "new0", 0.1)])
        assert filled_store.client.open_table("documents").version == before + 1

    def test_upsert_empty_nodes_removes_document(
        self,
        filled_store: PaperlessLanceVectorStore,
    ) -> None:
        filled_store.upsert_document("1", [])

        table = filled_store.client.open_table("documents")
        remaining = sorted(r["document_id"] for r in table.search().to_list())
        assert "1" not in remaining
        assert "2" in remaining


class TestPaperlessLanceVectorStoreMaintenance:
    def test_maybe_create_ann_index_noop_below_threshold(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "a", 0.1)])
        # Threshold far above row count -> no index attempted, no error.
        store.maybe_create_ann_index(min_rows=1000)
        # Still queryable.
        result = store.query(
            VectorStoreQuery(query_embedding=[0.1] * DIM, similarity_top_k=1),
        )
        assert len(result.nodes) == 1

    def test_maybe_create_ann_index_non_divisible_dim_falls_back(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        # DIM=8 is not divisible by the PQ default sub-vectors; must not raise
        # and must leave the table queryable (IVF_FLAT fallback or skipped).
        for i in range(40):
            store.add([_node(f"1-{i}", "1", f"t{i}", float(i))])
        store.maybe_create_ann_index(min_rows=10)
        result = store.query(
            VectorStoreQuery(query_embedding=[1.0] * DIM, similarity_top_k=3),
        )
        assert len(result.nodes) == 3

    def test_compact_reduces_to_single_version(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        for i in range(5):
            store.add([_node(f"1-{i}", "1", f"t{i}", float(i))])
        assert len(store.client.open_table("documents").list_versions()) > 1
        store.compact(retention_seconds=0)
        assert len(store.client.open_table("documents").list_versions()) == 1

    def test_upsert_after_optimize_with_scalar_index(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add(
            [
                _node("1-0", "1", "old0", 0.1),
                _node("1-1", "1", "old1", 0.2),
                _node("1-2", "1", "old2", 0.3),
                _node("2-0", "2", "keep", 0.9),
            ],
        )
        store.ensure_document_id_scalar_index()
        store.compact(retention_seconds=0)

        store.upsert_document("1", [_node("1-0", "1", "new0", 0.1)])

        table = store.client.open_table("documents")
        doc1 = sorted(
            r["id"] for r in table.search().where("document_id = '1'").to_list()
        )
        assert doc1 == ["1-0"]
        assert table.count_rows() == 2

    def test_ensure_scalar_index_is_idempotent(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add([_node("1-0", "1", "text", 0.5)])
        store.ensure_document_id_scalar_index()
        # Second call must not raise and must not replace the existing index.
        store.ensure_document_id_scalar_index()
        assert store._has_index_on("document_id")

    def test_ensure_scalar_index_noop_on_empty_store(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.ensure_document_id_scalar_index()  # no table yet — must not raise


class TestConfigMismatch:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def test_stored_model_name_returns_none_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        assert store.stored_model_name() is None

    def test_model_name_stored_in_schema_after_add(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri, embed_model_name="all-MiniLM-L6-v2")
        store.add([_node("1-0", "1", "text", 0.1)])
        assert store.stored_model_name() == "all-MiniLM-L6-v2"

    def test_model_name_stored_in_schema_after_upsert(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri, embed_model_name="nomic-embed")
        store.upsert_document("1", [_node("1-0", "1", "text", 0.1)])
        assert store.stored_model_name() == "nomic-embed"

    def test_model_name_persists_after_reopen(self, uri: str) -> None:
        PaperlessLanceVectorStore(uri=uri, embed_model_name="all-MiniLM-L6-v2").add(
            [_node("1-0", "1", "text", 0.1)],
        )
        reopened = PaperlessLanceVectorStore(uri=uri)
        assert reopened.stored_model_name() == "all-MiniLM-L6-v2"

    def test_config_mismatch_returns_false_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        assert store.config_mismatch("any-model") is False

    def test_config_mismatch_returns_false_when_model_matches(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri, embed_model_name="all-MiniLM-L6-v2")
        store.add([_node("1-0", "1", "text", 0.1)])
        assert store.config_mismatch("all-MiniLM-L6-v2") is False

    def test_config_mismatch_returns_true_when_model_differs(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri, embed_model_name="old-model")
        store.add([_node("1-0", "1", "text", 0.1)])
        assert store.config_mismatch("new-model") is True

    def test_config_mismatch_returns_false_when_no_metadata_stored(
        self,
        uri: str,
    ) -> None:
        # Tables created before model-name tracking was added have no schema metadata.
        # Conservative default: assume compatible rather than force a rebuild.
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        assert store.config_mismatch("any-model") is False


class TestGetModifiedTimes:
    @pytest.fixture
    def store(self, tmp_path: Path) -> PaperlessLanceVectorStore:
        return PaperlessLanceVectorStore(uri=str(tmp_path / "idx"))

    def _node_with_modified(
        self,
        node_id: str,
        doc_id: str,
        modified: str,
    ) -> TextNode:
        node = TextNode(
            id_=node_id,
            text="text",
            metadata={"document_id": doc_id, "modified": modified},
        )
        node.embedding = [0.1] * DIM
        node.relationships = {
            NodeRelationship.SOURCE: RelatedNodeInfo(node_id=doc_id),
        }
        return node

    def test_empty_store_returns_empty_dict(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        assert store.get_modified_times() == {}

    def test_returns_one_entry_per_document(
        self,
        store: PaperlessLanceVectorStore,
    ) -> None:
        store.add(
            [
                self._node_with_modified("1-0", "1", "2024-01-01T00:00:00"),
                self._node_with_modified("1-1", "1", "2024-01-01T00:00:00"),
                self._node_with_modified("2-0", "2", "2024-06-01T00:00:00"),
            ],
        )
        result = store.get_modified_times()
        assert result == {
            "1": "2024-01-01T00:00:00",
            "2": "2024-06-01T00:00:00",
        }


class TestSchemaVersioning:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def test_version_file_written_on_table_creation(self, uri: str) -> None:

        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])

        version_file = Path(uri) / "schema_version.json"
        assert version_file.exists()
        assert json.loads(version_file.read_text())["version"] == CURRENT_SCHEMA_VERSION

    def test_stored_schema_version_returns_current_when_file_missing(
        self,
        uri: str,
    ) -> None:

        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        (Path(uri) / "schema_version.json").unlink()

        reopened = PaperlessLanceVectorStore(uri=uri)
        assert reopened.stored_schema_version() == CURRENT_SCHEMA_VERSION

    def test_stored_schema_version_persists_after_reopen(self, uri: str) -> None:

        PaperlessLanceVectorStore(uri=uri).add([_node("1-0", "1", "text", 0.1)])

        reopened = PaperlessLanceVectorStore(uri=uri)
        assert reopened.stored_schema_version() == CURRENT_SCHEMA_VERSION

    def test_drop_table_removes_version_file(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        assert (Path(uri) / "schema_version.json").exists()

        store.drop_table()
        assert not (Path(uri) / "schema_version.json").exists()

    def test_version_file_written_on_upsert_creation(self, uri: str) -> None:

        store = PaperlessLanceVectorStore(uri=uri)
        store.upsert_document("1", [_node("1-0", "1", "text", 0.1)])

        version_file = Path(uri) / "schema_version.json"
        assert json.loads(version_file.read_text())["version"] == CURRENT_SCHEMA_VERSION


class TestMigrationRegistry:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def _store_at_version(self, uri: str, version: int) -> PaperlessLanceVectorStore:
        """Create a store with a table and then fake its on-disk version."""
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        store._write_schema_version(version)
        return PaperlessLanceVectorStore(uri=uri)  # reopen to pick up written version

    def test_pending_migrations_empty_at_current_version(self, uri: str) -> None:
        from paperless_ai.vector_store import CURRENT_SCHEMA_VERSION
        from paperless_ai.vector_store import Migration  # noqa: F401

        store = self._store_at_version(uri, CURRENT_SCHEMA_VERSION)
        assert store.pending_migrations() == []

    def test_pending_migrations_returns_migrations_above_stored_version(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="add col",
            requires_reembed=False,
            apply=lambda t: None,
        )
        m3 = Migration(
            version=3,
            description="reindex",
            requires_reembed=True,
            apply=lambda t: None,
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 1)
        pending = store.pending_migrations()
        assert pending == [m2, m3]

    def test_pending_migrations_excludes_already_applied(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="add col",
            requires_reembed=False,
            apply=lambda t: None,
        )
        m3 = Migration(
            version=3,
            description="reindex",
            requires_reembed=True,
            apply=lambda t: None,
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 2)
        pending = store.pending_migrations()
        assert pending == [m3]

    def test_pending_migrations_empty_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        assert store.pending_migrations() == []

    def test_requires_reembed_migration_false_when_none_pending(self, uri: str) -> None:
        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is False

    def test_requires_reembed_migration_false_when_only_structural_pending(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="add col",
            requires_reembed=False,
            apply=lambda t: None,
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is False

    def test_requires_reembed_migration_true_when_reembed_migration_pending(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="reindex",
            requires_reembed=True,
            apply=lambda t: None,
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        assert store.requires_reembed_migration() is True


class TestApplyStructuralMigrations:
    @pytest.fixture
    def uri(self, tmp_path: Path) -> str:
        return str(tmp_path / "idx")

    def _store_at_version(self, uri: str, version: int) -> PaperlessLanceVectorStore:
        store = PaperlessLanceVectorStore(uri=uri)
        store.add([_node("1-0", "1", "text", 0.1)])
        store._write_schema_version(version)
        return PaperlessLanceVectorStore(uri=uri)

    def test_apply_structural_adds_column_via_lancedb(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        def _add_extra(table: Any) -> None:
            table.add_columns({"extra": "CAST(NULL AS string)"})

        m2 = Migration(
            version=2,
            description="add extra col",
            requires_reembed=False,
            apply=_add_extra,
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()

        assert len(applied) == 1
        assert applied[0] == m2
        # Column actually present in the table schema after reopen.
        reopened = PaperlessLanceVectorStore(uri=uri)
        field_names = [f.name for f in reopened._table.schema]
        assert "extra" in field_names

    def test_apply_structural_updates_version_file(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="add col",
            requires_reembed=False,
            apply=lambda t: t.add_columns({"c": "CAST(NULL AS string)"}),
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        store.apply_structural_migrations()

        assert store.stored_schema_version() == 2

    def test_apply_structural_skips_reembed_migrations(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        from paperless_ai.vector_store import Migration

        applied_versions: list[int] = []
        m2 = Migration(
            version=2,
            description="structural",
            requires_reembed=False,
            apply=lambda t: (
                applied_versions.append(2)
                or t.add_columns({"c": "CAST(NULL AS string)"})
            ),
        )
        m3 = Migration(
            version=3,
            description="reembed",
            requires_reembed=True,
            apply=lambda t: applied_versions.append(3),
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2, m3])

        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()

        assert [m.version for m in applied] == [2]
        assert 3 not in applied_versions
        # Version advances only to the last structural migration applied.
        assert store.stored_schema_version() == 2

    def test_apply_structural_noop_at_current_version(self, uri: str) -> None:
        store = self._store_at_version(uri, 1)
        applied = store.apply_structural_migrations()
        assert applied == []

    def test_apply_structural_noop_when_no_table(self, uri: str) -> None:
        store = PaperlessLanceVectorStore(uri=uri)
        applied = store.apply_structural_migrations()
        assert applied == []

    def test_apply_structural_refreshes_table_reference(
        self,
        uri: str,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """After add_columns the in-memory table object must reflect the new schema."""
        from paperless_ai.vector_store import Migration

        m2 = Migration(
            version=2,
            description="add col",
            requires_reembed=False,
            apply=lambda t: t.add_columns({"extra": "CAST(NULL AS string)"}),
        )
        mocker.patch("paperless_ai.vector_store.MIGRATIONS", [m2])

        store = self._store_at_version(uri, 1)
        store.apply_structural_migrations()

        # The store's own _table reference (not a re-open) must see the new column.
        field_names = [f.name for f in store._table.schema]
        assert "extra" in field_names
