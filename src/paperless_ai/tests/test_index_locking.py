import logging
import sqlite3
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.conf import settings
from filelock import ReadWriteLock
from llama_index.core.schema import TextNode
from pytest_django.fixtures import SettingsWrapper

from paperless_ai import indexing
from paperless_ai.vector_store import PaperlessSqliteVecVectorStore

DIM = 8


def _node(node_id: str, document_id: str, *, seed: float = 0.0) -> TextNode:
    node = TextNode(
        id_=node_id,
        text="chunk",
        metadata={"document_id": document_id, "modified": "2026-06-01T00:00:00"},
    )
    node.relationships = {}
    node.embedding = [seed + i / 100 for i in range(DIM)]
    return node


def _seed_bloated_index(index_dir: Path) -> None:
    """Create an index whose cumulative inserts far exceed live rows."""
    store = PaperlessSqliteVecVectorStore(uri=str(index_dir))
    store.add([_node(f"d{j}", str(j), seed=float(j)) for j in range(20)])
    for cycle in range(6):
        for j in range(20):
            store.upsert_document(
                str(j),
                [_node(f"d{j}-c{cycle}", str(j), seed=float(j))],
            )
    store.client.close()


def _bloat_ratio(index_dir: Path) -> float:
    store = PaperlessSqliteVecVectorStore(uri=str(index_dir))
    live = store.client.execute("SELECT count(*) FROM documents").fetchone()[0]
    row = store.client.execute(
        "SELECT value FROM index_meta WHERE key = 'total_inserts'",
    ).fetchone()
    total = int(row["value"]) if row else live
    store.client.close()
    return total / max(live, 1)


def _integrity_ok(index_dir: Path) -> bool:
    store = PaperlessSqliteVecVectorStore(uri=str(index_dir))
    result = store.client.execute("PRAGMA integrity_check").fetchone()[0]
    rows = store.client.execute("SELECT count(*) FROM documents").fetchone()[0]
    store.client.close()
    return result == "ok" and rows == 20


def _reader_lock() -> ReadWriteLock:
    # A distinct instance simulates a reader in another process: it coordinates
    # with the production lock purely through SQLite, never reentrant upgrade.
    return ReadWriteLock(str(settings.LLM_INDEX_RWLOCK), is_singleton=False)


class TestCompactionLock:
    def test_compaction_skips_when_a_reader_holds_the_lock(
        self,
        temp_llm_index_dir: Path,
        settings: SettingsWrapper,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        _seed_bloated_index(temp_llm_index_dir)
        settings.LLM_INDEX_COMPACTION_LOCK_TIMEOUT = 0.3

        lock = _reader_lock()
        with lock.read_lock(), caplog.at_level(logging.INFO):
            indexing.llm_index_compact()  # must not raise
        lock.close()

        # Swap was skipped: bloat remains, nothing corrupted, data intact.
        assert _integrity_ok(temp_llm_index_dir)
        assert _bloat_ratio(temp_llm_index_dir) > 2
        assert "Skipping LLM index compaction" in caplog.text

    def test_compaction_runs_when_no_reader_holds_the_lock(
        self,
        temp_llm_index_dir: Path,
    ) -> None:
        _seed_bloated_index(temp_llm_index_dir)
        assert _bloat_ratio(temp_llm_index_dir) > 2

        indexing.llm_index_compact()

        assert _bloat_ratio(temp_llm_index_dir) == pytest.approx(1.0)
        assert _integrity_ok(temp_llm_index_dir)

    def test_normal_write_is_not_gated_by_the_compaction_lock(
        self,
        temp_llm_index_dir: Path,
    ) -> None:
        """A held exclusive lock must not block ordinary writes (WAL handles them)."""
        _seed_bloated_index(temp_llm_index_dir)
        done = threading.Event()

        def remove() -> None:
            indexing.llm_index_remove_document(MagicMock(id=999))
            done.set()

        holder = _reader_lock()
        with holder.write_lock():
            t = threading.Thread(target=remove)
            t.start()
            finished = done.wait(timeout=5)
        t.join(timeout=2)
        holder.close()
        assert finished, "a normal write blocked on the compaction lock"


class TestReadStore:
    def test_closes_connection_on_exit(self, temp_llm_index_dir: Path) -> None:
        with indexing.read_store() as store:
            conn = store.client
            assert conn.execute("SELECT 1").fetchone()[0] == 1
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_concurrent_readers_do_not_block(self, temp_llm_index_dir: Path) -> None:
        _seed_bloated_index(temp_llm_index_dir)
        with indexing.read_store() as a, indexing.read_store() as b:
            assert a.table_exists()
            assert b.table_exists()
