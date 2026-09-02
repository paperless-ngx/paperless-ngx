import sqlite3
from collections.abc import Generator

import pytest
from pytest_mock import MockerFixture

from paperless_ai.tables import ChunkRow
from paperless_ai.tables import DocumentChunksTable
from paperless_ai.tables import DocumentMetaRow
from paperless_ai.tables import DocumentMetaTable
from paperless_ai.tables import IndexMetaTable
from paperless_ai.tables import PermittedIdsTable


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
            - create() is called, a row is inserted, then create() is called again
        THEN:
            - No error is raised and the row survives uncorrupted
        """
        DocumentChunksTable.create(conn)
        DocumentChunksTable.insert_many(conn, [ChunkRow("c1", 1)])
        DocumentChunksTable.create(conn)
        assert DocumentChunksTable.chunk_ids_for_document(conn, 1) == ["c1"]

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
    @pytest.mark.parametrize(
        ("setter_name", "getter_name", "value"),
        [
            ("set_dim", "get_dim", 384),
            ("set_embed_model", "get_embed_model", "model-a"),
            ("set_schema_version", "get_schema_version", 2),
        ],
    )
    def test_typed_accessor_roundtrip(
        self,
        conn: sqlite3.Connection,
        setter_name: str,
        getter_name: str,
        value: int | str,
    ) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - A typed accessor's setter is called then the getter is read back
        THEN:
            - The same value is returned, correctly typed (int or str)
        """
        IndexMetaTable.create(conn)
        getter = getattr(IndexMetaTable, getter_name)
        setter = getattr(IndexMetaTable, setter_name)
        assert getter(conn) is None
        setter(conn, value)
        assert getter(conn) == value

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

    def test_increment_total_inserts_is_a_single_statement(
        self,
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - An empty index_meta table
        WHEN:
            - increment_total_inserts() is called
        THEN:
            - Exactly one conn.execute() call is made (a single INSERT ...
              ON CONFLICT DO UPDATE, not a separate read then write)
        """

        # sqlite3.Connection is an immutable C extension type with no
        # instance __dict__, so mocker.spy(conn, "execute") can't shadow
        # "execute" on a plain connection ("attribute 'execute' is
        # read-only"). A trivial Python subclass gets a normal instance
        # __dict__, making the instance spyable while still being a real,
        # usable sqlite3.Connection.
        class _SpyableConnection(sqlite3.Connection):
            pass

        conn = sqlite3.connect(":memory:", factory=_SpyableConnection)
        try:
            conn.row_factory = sqlite3.Row
            IndexMetaTable.create(conn)
            execute_spy = mocker.spy(conn, "execute")
            IndexMetaTable.increment_total_inserts(conn, 5)
            assert execute_spy.call_count == 1
        finally:
            conn.close()

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


class TestPermittedIdsTable:
    def _loaded_ids(self, conn: sqlite3.Connection) -> list[int]:
        return [
            row["id"]
            for row in conn.execute(
                f"SELECT id FROM {PermittedIdsTable.TABLE_NAME} ORDER BY id",
            )
        ]

    def test_load_then_read_back_all_ids(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - A bare sqlite3 connection
        WHEN:
            - load() is called with a set of ids
        THEN:
            - Every id is present in the TEMP TABLE, and only those ids
        """
        PermittedIdsTable.load(conn, [3, 1, 2])
        assert self._loaded_ids(conn) == [1, 2, 3]

    def test_load_replaces_previous_contents(self, conn: sqlite3.Connection) -> None:
        """
        GIVEN:
            - A connection whose PermittedIdsTable already holds one id set
        WHEN:
            - load() is called again with a different id set
        THEN:
            - Only the new ids are present -- a connection reused across
              multiple queries in one request never leaks a stale filter
        """
        PermittedIdsTable.load(conn, [1, 2, 3])
        PermittedIdsTable.load(conn, [4, 5])
        assert self._loaded_ids(conn) == [4, 5]

    def test_load_is_connection_private(self) -> None:
        """
        GIVEN:
            - Two separate connections
        WHEN:
            - Each loads PermittedIdsTable with a different id set, under
              the identical TABLE_NAME
        THEN:
            - Each connection sees only its own ids -- TEMP TABLE is
              connection-private, so concurrent requests never collide or
              cross-contaminate despite sharing the same table name (the
              vector store opens one connection per request; see
              PaperlessSqliteVecVectorStore)
        """
        conn_a = sqlite3.connect(":memory:")
        conn_a.row_factory = sqlite3.Row
        conn_b = sqlite3.connect(":memory:")
        conn_b.row_factory = sqlite3.Row
        try:
            PermittedIdsTable.load(conn_a, [1, 2, 3])
            PermittedIdsTable.load(conn_b, [4, 5, 6])
            assert self._loaded_ids(conn_a) == [1, 2, 3]
            assert self._loaded_ids(conn_b) == [4, 5, 6]
        finally:
            conn_a.close()
            conn_b.close()

    def test_load_handles_more_ids_than_a_bound_parameter_list_could(
        self,
        conn: sqlite3.Connection,
    ) -> None:
        """
        GIVEN:
            - An id count over SQLite's own bound-parameter limit
              (SQLITE_MAX_VARIABLE_NUMBER, 32766 by default) -- more than a
              literal IN(?,?,...) list could ever bind in one statement
        WHEN:
            - load() is called with that many ids
        THEN:
            - Every id is loaded without error, since executemany() binds
              one row at a time rather than one statement with N parameters
        """
        ids = list(range(40_000))
        PermittedIdsTable.load(conn, ids)
        assert self._loaded_ids(conn) == ids
