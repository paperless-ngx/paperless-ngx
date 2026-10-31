import sqlite3
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest
from llama_index.core.schema import TextNode

from paperless_ai.tables import DocumentChunksTable
from paperless_ai.vector_store import DB_FILENAME
from paperless_ai.vector_store import DEFAULT_TABLE_NAME
from paperless_ai.vector_store import VEC0_CHUNK_SIZE
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DIM = 16


def make_node(node_id: str, document_id: int) -> TextNode:
    node = TextNode(
        id_=node_id,
        text="some text",
        metadata={"document_id": document_id, "modified": "2026-06-10T00:00:00"},
    )
    node.relationships = {}
    node.embedding = [document_id + i / 100 for i in range(DIM)]
    return node


def vec_table_sql(db_path: Path) -> str:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(
            "SELECT sql FROM sqlite_master WHERE name = ?",
            (DEFAULT_TABLE_NAME,),
        ).fetchone()[0]
    finally:
        conn.close()


def create_legacy_vec_table(conn: sqlite3.Connection, dim: int) -> None:
    """The table definition from before chunk_size was set explicitly."""
    conn.execute(
        f"CREATE VIRTUAL TABLE {DEFAULT_TABLE_NAME} USING vec0("
        "id TEXT PRIMARY KEY, document_id INTEGER, +node_content TEXT, "
        f"embedding float[{dim}] distance_metric=cosine)",
    )


@pytest.fixture
def store(tmp_path: Path) -> Generator[PaperlessSqliteVecVectorStore, None, None]:
    with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:
        yield store


class TestVecChunkSize:
    def test_new_table_uses_configured_chunk_size(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN an empty store
        WHEN the first document is indexed and the vec0 table is created
        THEN the table definition carries the configured chunk size
        """
        store.upsert_document(1, [make_node("1-a", 1)])

        assert f"chunk_size={VEC0_CHUNK_SIZE}" in vec_table_sql(tmp_path / DB_FILENAME)

    def test_compact_moves_legacy_table_to_configured_chunk_size(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN an index whose vec0 table was created with the default chunk size
        WHEN the index is compacted
        THEN the rebuilt table uses the configured chunk size
        AND no indexed chunks are lost
        """
        with patch.object(
            PaperlessSqliteVecVectorStore,
            "_create_vec_table",
            staticmethod(create_legacy_vec_table),
        ):
            store.upsert_document(1, [make_node("1-a", 1), make_node("1-b", 1)])
            store.upsert_document(2, [make_node("2-a", 2)])
        assert "chunk_size" not in vec_table_sql(tmp_path / DB_FILENAME)

        store.compact(force=True)

        assert f"chunk_size={VEC0_CHUNK_SIZE}" in vec_table_sql(tmp_path / DB_FILENAME)
        assert DocumentChunksTable.count(store.client) == 3
