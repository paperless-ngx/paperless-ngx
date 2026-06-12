from pathlib import Path

import pytest
from django.utils import timezone

from documents.models import Document
from paperless_ai import indexing
from paperless_ai.tests.conftest import FakeEmbedding


@pytest.fixture
def legacy_lance_dir(temp_llm_index_dir: Path) -> Path:
    """Simulate leftovers of a pre-sqlite-vec LanceDB index."""
    lance_table = temp_llm_index_dir / "documents.lance"
    (lance_table / "data").mkdir(parents=True)
    (lance_table / "data" / "0000.lance").write_bytes(b"not a real lance file")
    (temp_llm_index_dir / "meta.json").write_text("{}")
    return lance_table


@pytest.mark.django_db
class TestLegacyLanceCleanup:
    def test_update_removes_legacy_dir_and_forces_rebuild(
        self,
        legacy_lance_dir: Path,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When a LanceDB directory is present, update_llm_index must delete it,
        log a rebuild warning, and produce a valid (empty) sqlite-vec store."""
        Document.objects.create(
            title="Test Document",
            content="Some content for legacy lance cleanup test.",
            added=timezone.now(),
        )

        indexing.update_llm_index(rebuild=False)

        assert not legacy_lance_dir.exists()
        assert not (temp_llm_index_dir / "meta.json").exists()
        assert "forcing a full rebuild" in caplog.text
        store = indexing.get_vector_store()
        assert store.table_exists()

    def test_update_without_legacy_dir_does_not_force_rebuild(
        self,
        temp_llm_index_dir: Path,
        mock_embed_model: FakeEmbedding,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When no LanceDB leftovers exist, incremental update must not log a
        forced-rebuild warning on a second call."""
        Document.objects.create(
            title="Test Document",
            content="Some content without legacy lance.",
            added=timezone.now(),
        )

        # First call builds the index cleanly (no legacy lance present).
        indexing.update_llm_index(rebuild=True)

        caplog.clear()

        # Second incremental call must not mention a forced rebuild.
        indexing.update_llm_index(rebuild=False)

        assert "forcing a full rebuild" not in caplog.text

    def test_cleanup_helper_reports_absence(self, temp_llm_index_dir: Path) -> None:
        """_cleanup_legacy_lance_index must return False when no lance dir exists."""
        assert indexing._cleanup_legacy_lance_index() is False  # noqa: SLF001

    def test_cleanup_helper_reports_presence(
        self,
        legacy_lance_dir: Path,
        temp_llm_index_dir: Path,
    ) -> None:
        """_cleanup_legacy_lance_index must return True and remove the directory."""
        result = indexing._cleanup_legacy_lance_index()  # noqa: SLF001

        assert result is True
        assert not legacy_lance_dir.exists()
        assert not (temp_llm_index_dir / "meta.json").exists()

    def test_cleanup_helper_removes_only_lance_not_other_files(
        self,
        legacy_lance_dir: Path,
        temp_llm_index_dir: Path,
    ) -> None:
        """_cleanup_legacy_lance_index must not touch files other than the lance dir
        and meta.json."""
        other_file = temp_llm_index_dir / "index.db"
        other_file.write_bytes(b"sqlite data")

        indexing._cleanup_legacy_lance_index()  # noqa: SLF001

        assert other_file.exists(), (
            "unrelated files in LLM_INDEX_DIR must be left intact after cleanup"
        )
