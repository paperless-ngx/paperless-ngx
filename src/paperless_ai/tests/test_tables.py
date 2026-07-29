import sqlite3
from collections.abc import Generator

import pytest

from paperless_ai.tables import ChunkRow
from paperless_ai.tables import DocumentChunksTable
from paperless_ai.tables import DocumentMetaRow
from paperless_ai.tables import DocumentMetaTable
from paperless_ai.tables import IndexMetaTable


@pytest.fixture
def conn() -> Generator[sqlite3.Connection, None, None]:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


class TestDocumentChunksTable:
    def test_create_is_idempotent(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - A bare sqlite3 connection
        WHEN:
            - create() is called twice
        THEN:
            - No error is raised and the table exists
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.create(conn)
        assert DocumentChunksTable.count(conn) == 0

    def test_insert_many_then_lookup_by_document_id(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - An empty document_chunks table
        WHEN:
            - Two chunks for document 1 and one for document 2 are inserted
        THEN:
            - chunk_ids_for_document returns exactly the matching chunk ids
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.insert_many(
            conn,
            [ChunkRow("c1", 1), ChunkRow("c2", 1), ChunkRow("c3", 2)],
        )
        assert sorted(DocumentChunksTable.chunk_ids_for_document(conn, 1)) == [
            "c1",
            "c2",
        ]
        assert DocumentChunksTable.chunk_ids_for_document(conn, 2) == ["c3"]
        assert DocumentChunksTable.chunk_ids_for_document(conn, 999) == []

    def test_delete_for_document_removes_only_that_document(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - Chunks for two different documents
        WHEN:
            - delete_for_document() is called for one of them
        THEN:
            - Only that document's chunks are removed
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.insert_many(
            conn,
            [ChunkRow("c1", 1), ChunkRow("c2", 2)],
        )
        DocumentChunksTable.delete_for_document(conn, 1)
        assert DocumentChunksTable.chunk_ids_for_document(conn, 1) == []
        assert DocumentChunksTable.chunk_ids_for_document(conn, 2) == ["c2"]

    def test_delete_all_clears_every_row(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - Chunks for multiple documents
        WHEN:
            - delete_all() is called
        THEN:
            - count() returns 0
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.insert_many(
            conn,
            [ChunkRow("c1", 1), ChunkRow("c2", 2)],
        )
        DocumentChunksTable.delete_all(conn)
        assert DocumentChunksTable.count(conn) == 0

    def test_count_reflects_live_rows(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - An empty document_chunks table
        WHEN:
            - Rows are inserted then one document's rows are deleted
        THEN:
            - count() reflects the remaining row count
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.insert_many(
            conn,
            [ChunkRow("c1", 1), ChunkRow("c2", 1), ChunkRow("c3", 2)],
        )
        assert DocumentChunksTable.count(conn) == 3
        DocumentChunksTable.delete_for_document(conn, 1)
        assert DocumentChunksTable.count(conn) == 1


class TestDocumentMetaTable:
    def test_upsert_many_then_all_modified_times(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - An empty document_meta table
        WHEN:
            - Two documents' modified timestamps are upserted
        THEN:
            - all_modified_times() returns both, keyed by str(document_id)
        """
        DocumentMetaTable.create(conn)
        DocumentMetaTable.upsert_many(
            conn,
            [
                DocumentMetaRow(1, "2026-01-01T00:00:00"),
                DocumentMetaRow(2, "2026-02-02T00:00:00"),
            ],
        )
        assert DocumentMetaTable.all_modified_times(conn) == {
            "1": "2026-01-01T00:00:00",
            "2": "2026-02-02T00:00:00",
        }

    def test_upsert_many_overwrites_existing_value(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - A document_meta row for document 1
        WHEN:
            - upsert_many() is called again with a new modified value for
              the same document_id
        THEN:
            - The stored value is replaced, not duplicated
        """
        DocumentMetaTable.create(conn)
        DocumentMetaTable.upsert_many(conn, [DocumentMetaRow(1, "old")])
        DocumentMetaTable.upsert_many(conn, [DocumentMetaRow(1, "new")])
        assert DocumentMetaTable.all_modified_times(conn) == {"1": "new"}

    def test_delete_for_document_removes_only_that_row(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - document_meta rows for two documents
        WHEN:
            - delete_for_document() is called for one of them
        THEN:
            - Only that document's row is removed
        """
        DocumentMetaTable.create(conn)
        DocumentMetaTable.upsert_many(
            conn,
            [DocumentMetaRow(1, "a"), DocumentMetaRow(2, "b")],
        )
        DocumentMetaTable.delete_for_document(conn, 1)
        assert DocumentMetaTable.all_modified_times(conn) == {"2": "b"}

    def test_delete_all_clears_every_row(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - document_meta rows for multiple documents
        WHEN:
            - delete_all() is called
        THEN:
            - all_modified_times() returns an empty dict
        """
        DocumentMetaTable.create(conn)
        DocumentMetaTable.upsert_many(
            conn,
            [DocumentMetaRow(1, "a"), DocumentMetaRow(2, "b")],
        )
        DocumentMetaTable.delete_all(conn)
        assert DocumentMetaTable.all_modified_times(conn) == {}

    def test_copy_all_streams_every_row_to_destination(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - A source connection with document_meta rows for 5 documents
            - A separate, empty destination connection
        WHEN:
            - copy_all() is called with a batch size smaller than the row
              count, forcing multiple fetchmany() cycles
        THEN:
            - Every row is present on the destination connection
        """
        DocumentMetaTable.create(conn)
        DocumentMetaTable.upsert_many(
            conn,
            [DocumentMetaRow(i, f"modified-{i}") for i in range(5)],
        )
        dst_conn = sqlite3.connect(":memory:")
        dst_conn.row_factory = sqlite3.Row
        try:
            DocumentMetaTable.create(dst_conn)
            DocumentMetaTable.copy_all(conn, dst_conn, batch_size=2)
            assert DocumentMetaTable.all_modified_times(dst_conn) == {
                str(i): f"modified-{i}" for i in range(5)
            }
        finally:
            dst_conn.close()


class TestIndexMetaTable:
    def test_dim_roundtrip(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - set_dim() is called then get_dim() is read back
        THEN:
            - The same int value is returned
        """
        IndexMetaTable.create(conn)
        assert IndexMetaTable.get_dim(conn) is None
        IndexMetaTable.set_dim(conn, 384)
        assert IndexMetaTable.get_dim(conn) == 384

    def test_embed_model_roundtrip(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - set_embed_model() is called then get_embed_model() is read back
        THEN:
            - The same string value is returned
        """
        IndexMetaTable.create(conn)
        assert IndexMetaTable.get_embed_model(conn) is None
        IndexMetaTable.set_embed_model(conn, "model-a")
        assert IndexMetaTable.get_embed_model(conn) == "model-a"

    def test_schema_version_roundtrip(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - set_schema_version() is called then get_schema_version() is
              read back
        THEN:
            - The same int value is returned
        """
        IndexMetaTable.create(conn)
        assert IndexMetaTable.get_schema_version(conn) is None
        IndexMetaTable.set_schema_version(conn, 2)
        assert IndexMetaTable.get_schema_version(conn) == 2

    def test_total_inserts_starts_at_zero(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - get_total_inserts() is read before anything is set
        THEN:
            - 0 is returned
        """
        IndexMetaTable.create(conn)
        assert IndexMetaTable.get_total_inserts(conn) == 0

    def test_increment_total_inserts_accumulates(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - increment_total_inserts() is called twice
        THEN:
            - get_total_inserts() returns the running sum
        """
        IndexMetaTable.create(conn)
        IndexMetaTable.increment_total_inserts(conn, 5)
        IndexMetaTable.increment_total_inserts(conn, 3)
        assert IndexMetaTable.get_total_inserts(conn) == 8

    def test_reset_total_inserts_sets_absolute_value(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - A total_inserts counter already at a high value
        WHEN:
            - reset_total_inserts() is called with a lower value
        THEN:
            - get_total_inserts() returns exactly that value, not a sum
        """
        IndexMetaTable.create(conn)
        IndexMetaTable.increment_total_inserts(conn, 100)
        IndexMetaTable.reset_total_inserts(conn, 7)
        assert IndexMetaTable.get_total_inserts(conn) == 7
