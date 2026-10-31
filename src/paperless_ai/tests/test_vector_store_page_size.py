import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest
from llama_index.core.schema import TextNode

from paperless_ai.tables import DocumentChunksTable
from paperless_ai.vector_store import DB_FILENAME
from paperless_ai.vector_store import DB_PAGE_SIZE
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DIM = 16
LEGACY_PAGE_SIZE = 4096


def make_node(node_id: str, document_id: int) -> TextNode:
    node = TextNode(
        id_=node_id,
        text="some text",
        metadata={"document_id": document_id, "modified": "2026-06-10T00:00:00"},
    )
    node.relationships = {}
    node.embedding = [document_id + i / 100 for i in range(DIM)]
    return node


def page_size_of(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("PRAGMA page_size").fetchone()[0]
    finally:
        conn.close()


@pytest.fixture
def legacy_page_size_db(tmp_path: Path) -> Path:
    """An existing index file created before the page size was set."""
    db_path = tmp_path / DB_FILENAME
    conn = sqlite3.connect(db_path)
    conn.execute(f"PRAGMA page_size={LEGACY_PAGE_SIZE}")
    conn.execute("CREATE TABLE _seed(x)")
    conn.execute("DROP TABLE _seed")
    conn.close()
    assert page_size_of(db_path) == LEGACY_PAGE_SIZE
    return db_path


@pytest.fixture
def store(tmp_path: Path) -> Generator[PaperlessSqliteVecVectorStore, None, None]:
    with PaperlessSqliteVecVectorStore(uri=str(tmp_path)) as store:
        yield store


class TestIndexPageSize:
    def test_new_index_file_uses_configured_page_size(
        self,
        store: PaperlessSqliteVecVectorStore,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN no existing index file
        WHEN a store is opened and a document is indexed
        THEN the database file uses the configured page size
        """
        store.upsert_document(1, [make_node("1-a", 1)])

        assert page_size_of(tmp_path / DB_FILENAME) == DB_PAGE_SIZE

    def test_compact_moves_legacy_file_to_configured_page_size(
        self,
        legacy_page_size_db: Path,
    ) -> None:
        """
        GIVEN an existing index file created with a different page size
        WHEN the index is compacted
        THEN the rebuilt file uses the configured page size
        AND no indexed chunks are lost
        """
        with PaperlessSqliteVecVectorStore(
            uri=str(legacy_page_size_db.parent),
        ) as store:
            store.upsert_document(1, [make_node("1-a", 1), make_node("1-b", 1)])
            assert page_size_of(legacy_page_size_db) == LEGACY_PAGE_SIZE

            store.compact(force=True)

            assert page_size_of(legacy_page_size_db) == DB_PAGE_SIZE
            assert DocumentChunksTable.count(store.client) == 2
