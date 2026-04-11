"""
Sanity checker profiling.

Run with:
    uv run pytest ../test_sanity_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Corpus: 2 000 documents with stub files (original + archive + thumbnail)
        created in a temp MEDIA_ROOT.

Scenarios
---------
TestSanityCheckerProfile
  - test_sanity_full_corpus    full check_sanity() -- cProfile + tracemalloc
  - test_sanity_query_pattern  profile_block summary: query count + time
"""

from __future__ import annotations

import hashlib
import time

import pytest
from django.test import override_settings
from profiling import measure_memory
from profiling import profile_block
from profiling import profile_cpu

from documents.models import Document
from documents.sanity_checker import check_sanity

pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

NUM_DOCS = 2_000
SEED = 42


# ---------------------------------------------------------------------------
# Module-scoped fixture: temp directories + corpus
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    """Unlock the DB for the whole module (module-scoped)."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def sanity_corpus(tmp_path_factory, module_db):
    """
    Build a 2 000-document corpus.  For each document create stub files
    (1-byte placeholders) in ORIGINALS_DIR, ARCHIVE_DIR, and THUMBNAIL_DIR
    so the sanity checker's file-existence and checksum checks have real targets.
    """
    media = tmp_path_factory.mktemp("sanity_media")
    originals_dir = media / "documents" / "originals"
    archive_dir = media / "documents" / "archive"
    thumb_dir = media / "documents" / "thumbnails"
    for d in (originals_dir, archive_dir, thumb_dir):
        d.mkdir(parents=True)

    # Use override_settings as a context manager for the whole fixture lifetime
    settings_ctx = override_settings(
        MEDIA_ROOT=media,
        ORIGINALS_DIR=originals_dir,
        ARCHIVE_DIR=archive_dir,
        THUMBNAIL_DIR=thumb_dir,
        MEDIA_LOCK=media / "media.lock",
    )
    settings_ctx.enable()

    print(f"\n[setup] Creating {NUM_DOCS} documents with stub files...")  # noqa: T201
    t0 = time.perf_counter()
    docs = []
    for i in range(NUM_DOCS):
        content = f"document content for doc {i}"
        checksum = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()

        orig_filename = f"{i:07d}.pdf"
        arch_filename = f"{i:07d}.pdf"

        orig_path = originals_dir / orig_filename
        arch_path = archive_dir / arch_filename

        orig_path.write_bytes(content.encode())
        arch_path.write_bytes(content.encode())

        docs.append(
            Document(
                title=f"Document {i:05d}",
                content=content,
                checksum=checksum,
                archive_checksum=checksum,
                filename=orig_filename,
                archive_filename=arch_filename,
                mime_type="application/pdf",
            ),
        )

    created = Document.objects.bulk_create(docs, batch_size=500)

    # Thumbnails use doc.pk, so create them after bulk_create assigns pks
    for doc in created:
        thumb_path = thumb_dir / f"{doc.pk:07d}.webp"
        thumb_path.write_bytes(b"\x00")  # minimal thumbnail stub

    print(  # noqa: T201
        f"[setup] bulk_create + file creation: {time.perf_counter() - t0:.2f}s",
    )

    yield {"media": media}

    # Teardown
    print("\n[teardown] Removing sanity corpus...")  # noqa: T201
    Document.objects.all().delete()
    settings_ctx.disable()


# ---------------------------------------------------------------------------
# TestSanityCheckerProfile
# ---------------------------------------------------------------------------


class TestSanityCheckerProfile:
    """Profile check_sanity() on a realistic corpus with real files."""

    @pytest.fixture(autouse=True)
    def _setup(self, sanity_corpus):
        self.media = sanity_corpus["media"]

    def test_sanity_full_corpus(self):
        """Full check_sanity() -- cProfile surfaces hot frames, tracemalloc shows peak."""
        _, elapsed = profile_cpu(
            lambda: check_sanity(scheduled=False),
            label=f"check_sanity()  [{NUM_DOCS} docs, real files]",
            top=25,
        )

        _, peak_kib, delta_kib = measure_memory(
            lambda: check_sanity(scheduled=False),
            label=f"check_sanity()  [{NUM_DOCS} docs] -- memory",
        )

        print("\n  Summary:")  # noqa: T201
        print(f"    Wall time (CPU profile run): {elapsed * 1000:.1f} ms")  # noqa: T201
        print(f"    Peak memory (second run):    {peak_kib:.1f} KiB")  # noqa: T201
        print(f"    Memory delta:                {delta_kib:+.1f} KiB")  # noqa: T201

    def test_sanity_query_pattern(self):
        """profile_block view: query count + query time + wall time in one summary."""
        with profile_block(f"check_sanity()  [{NUM_DOCS} docs] -- query count"):
            check_sanity(scheduled=False)
