# ruff: noqa: T201
"""
cProfile-based search pipeline profiling with a 20k-document dataset.

Run with:
    uv run pytest ../test_backend_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Each scenario prints:
  - Wall time for the operation
  - cProfile stats sorted by cumulative time (top 25 callers)

This is a developer tool, not a correctness test.  Nothing here should
fail unless the code is broken.
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import pytest
from profiling import profile_cpu

from documents.models import Document
from documents.search._backend import TantivyBackend
from documents.search._backend import reset_backend

if TYPE_CHECKING:
    from pathlib import Path

# transaction=False (default): tests roll back, but the module-scoped fixture
# commits its data outside the test transaction so it remains visible throughout.
pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

# ---------------------------------------------------------------------------
# Dataset constants
# ---------------------------------------------------------------------------
NUM_DOCS = 20_000
SEED = 42

# Terms and their approximate match rates across the corpus.
# "rechnung"    -> ~70% of docs  (~14 000)
# "mahnung"     -> ~20% of docs  (~4 000)
# "kontonummer" -> ~5%  of docs  (~1 000)
# "rarewort"    -> ~1%  of docs  (~200)
COMMON_TERM = "rechnung"
MEDIUM_TERM = "mahnung"
RARE_TERM = "kontonummer"
VERY_RARE_TERM = "rarewort"

PAGE_SIZE = 25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILLER_WORDS = [
    "dokument",  # codespell:ignore
    "seite",
    "datum",
    "betrag",
    "nummer",
    "konto",
    "firma",
    "vertrag",
    "lieferant",
    "bestellung",
    "steuer",
    "mwst",
    "leistung",
    "auftrag",
    "zahlung",
]


def _build_content(rng: random.Random) -> str:
    """Return a short paragraph with terms embedded at the desired rates."""
    words = rng.choices(_FILLER_WORDS, k=15)
    if rng.random() < 0.70:
        words.append(COMMON_TERM)
    if rng.random() < 0.20:
        words.append(MEDIUM_TERM)
    if rng.random() < 0.05:
        words.append(RARE_TERM)
    if rng.random() < 0.01:
        words.append(VERY_RARE_TERM)
    rng.shuffle(words)
    return " ".join(words)


def _time(fn, *, label: str, runs: int = 3):
    """Run *fn()* several times and report min/avg/max wall time (no cProfile)."""
    times = []
    result = None
    for _ in range(runs):
        t0 = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - t0)
    mn, avg, mx = min(times), sum(times) / len(times), max(times)
    print(
        f"  {label}: min={mn * 1000:.1f}ms  avg={avg * 1000:.1f}ms  max={mx * 1000:.1f}ms  (n={runs})",
    )
    return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    """Unlock the DB for the whole module (module-scoped)."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def large_backend(tmp_path_factory, module_db) -> TantivyBackend:
    """
    Build a 20 000-document DB + on-disk Tantivy index, shared across all
    profiling scenarios in this module.  Teardown deletes all documents.
    """
    index_path: Path = tmp_path_factory.mktemp("tantivy_profile")

    # ---- 1. Bulk-create Document rows ----------------------------------------
    rng = random.Random(SEED)
    docs = [
        Document(
            title=f"Document {i:05d}",
            content=_build_content(rng),
            checksum=f"{i:064x}",
            pk=i + 1,
        )
        for i in range(NUM_DOCS)
    ]
    t0 = time.perf_counter()
    Document.objects.bulk_create(docs, batch_size=1_000)
    db_time = time.perf_counter() - t0
    print(f"\n[setup] bulk_create {NUM_DOCS} docs: {db_time:.2f}s")

    # ---- 2. Build Tantivy index -----------------------------------------------
    backend = TantivyBackend(path=index_path)
    backend.open()

    t0 = time.perf_counter()
    with backend.batch_update() as batch:
        for doc in Document.objects.iterator(chunk_size=500):
            batch.add_or_update(doc)
    idx_time = time.perf_counter() - t0
    print(f"[setup] index {NUM_DOCS} docs: {idx_time:.2f}s")

    # ---- 3. Report corpus stats -----------------------------------------------
    for term in (COMMON_TERM, MEDIUM_TERM, RARE_TERM, VERY_RARE_TERM):
        count = len(backend.search_ids(term, user=None))
        print(f"[setup]   '{term}' -> {count} hits")

    yield backend

    # ---- Teardown ------------------------------------------------------------
    backend.close()
    reset_backend()
    Document.objects.all().delete()


# ---------------------------------------------------------------------------
# Profiling tests — each scenario is a separate function so pytest can run
# them individually or all together with -m profiling.
# ---------------------------------------------------------------------------


class TestSearchIdsProfile:
    """Profile backend.search_ids() — pure Tantivy, no DB."""

    def test_search_ids_large(self, large_backend: TantivyBackend):
        """~14 000 hits: how long does Tantivy take to collect all IDs?"""
        profile_cpu(
            lambda: large_backend.search_ids(COMMON_TERM, user=None),
            label=f"search_ids('{COMMON_TERM}')  [large result set ~14k]",
        )

    def test_search_ids_medium(self, large_backend: TantivyBackend):
        """~4 000 hits."""
        profile_cpu(
            lambda: large_backend.search_ids(MEDIUM_TERM, user=None),
            label=f"search_ids('{MEDIUM_TERM}')  [medium result set ~4k]",
        )

    def test_search_ids_rare(self, large_backend: TantivyBackend):
        """~1 000 hits."""
        profile_cpu(
            lambda: large_backend.search_ids(RARE_TERM, user=None),
            label=f"search_ids('{RARE_TERM}')  [rare result set ~1k]",
        )


class TestIntersectAndOrderProfile:
    """
    Profile the DB intersection step: filter(pk__in=search_ids).
    This is the 'intersect_and_order' logic from views.py.
    """

    def test_intersect_large(self, large_backend: TantivyBackend):
        """Intersect 14k Tantivy IDs with all 20k ORM-visible docs."""
        all_ids = large_backend.search_ids(COMMON_TERM, user=None)
        qs = Document.objects.all()

        print(f"\n  Tantivy returned {len(all_ids)} IDs")

        profile_cpu(
            lambda: list(qs.filter(pk__in=all_ids).values_list("pk", flat=True)),
            label=f"filter(pk__in={len(all_ids)} ids)  [large, use_tantivy_sort=True path]",
        )

        # Also time it a few times to get stable numbers
        print()
        _time(
            lambda: list(qs.filter(pk__in=all_ids).values_list("pk", flat=True)),
            label=f"filter(pk__in={len(all_ids)}) repeated",
        )

    def test_intersect_rare(self, large_backend: TantivyBackend):
        """Intersect ~1k Tantivy IDs — the happy path."""
        all_ids = large_backend.search_ids(RARE_TERM, user=None)
        qs = Document.objects.all()

        print(f"\n  Tantivy returned {len(all_ids)} IDs")

        profile_cpu(
            lambda: list(qs.filter(pk__in=all_ids).values_list("pk", flat=True)),
            label=f"filter(pk__in={len(all_ids)} ids)  [rare, use_tantivy_sort=True path]",
        )


class TestHighlightHitsProfile:
    """Profile backend.highlight_hits() — per-doc Tantivy lookups with BM25 scoring."""

    def test_highlight_page1(self, large_backend: TantivyBackend):
        """25-doc highlight for page 1 (rank_start=1)."""
        all_ids = large_backend.search_ids(COMMON_TERM, user=None)
        page_ids = all_ids[:PAGE_SIZE]

        profile_cpu(
            lambda: large_backend.highlight_hits(
                COMMON_TERM,
                page_ids,
                rank_start=1,
            ),
            label=f"highlight_hits page 1  (ids {all_ids[0]}..{all_ids[PAGE_SIZE - 1]})",
        )

    def test_highlight_page_middle(self, large_backend: TantivyBackend):
        """25-doc highlight for a mid-corpus page (rank_start=page_offset+1)."""
        all_ids = large_backend.search_ids(COMMON_TERM, user=None)
        mid = len(all_ids) // 2
        page_ids = all_ids[mid : mid + PAGE_SIZE]
        page_offset = mid

        profile_cpu(
            lambda: large_backend.highlight_hits(
                COMMON_TERM,
                page_ids,
                rank_start=page_offset + 1,
            ),
            label=f"highlight_hits page ~{mid // PAGE_SIZE}  (offset {page_offset})",
        )

    def test_highlight_repeated(self, large_backend: TantivyBackend):
        """Multiple runs of page-1 highlight to see variance."""
        all_ids = large_backend.search_ids(COMMON_TERM, user=None)
        page_ids = all_ids[:PAGE_SIZE]

        print()
        _time(
            lambda: large_backend.highlight_hits(COMMON_TERM, page_ids, rank_start=1),
            label="highlight_hits page 1",
            runs=5,
        )


class TestFullPipelineProfile:
    """
    Profile the combined pipeline as it runs in views.py:
      search_ids -> filter(pk__in) -> highlight_hits
    """

    def _run_pipeline(
        self,
        backend: TantivyBackend,
        term: str,
        page: int = 1,
    ):
        all_ids = backend.search_ids(term, user=None)
        qs = Document.objects.all()
        visible_ids = set(qs.filter(pk__in=all_ids).values_list("pk", flat=True))
        ordered_ids = [i for i in all_ids if i in visible_ids]

        page_offset = (page - 1) * PAGE_SIZE
        page_ids = ordered_ids[page_offset : page_offset + PAGE_SIZE]
        hits = backend.highlight_hits(
            term,
            page_ids,
            rank_start=page_offset + 1,
        )
        return ordered_ids, hits

    def test_pipeline_large_page1(self, large_backend: TantivyBackend):
        """Full pipeline: large result set, page 1."""
        ordered_ids, hits = profile_cpu(
            lambda: self._run_pipeline(large_backend, COMMON_TERM, page=1),
            label=f"full pipeline  '{COMMON_TERM}'  page 1",
        )[0]
        print(f"  -> {len(ordered_ids)} total results, {len(hits)} hits on page")

    def test_pipeline_large_page5(self, large_backend: TantivyBackend):
        """Full pipeline: large result set, page 5."""
        ordered_ids, hits = profile_cpu(
            lambda: self._run_pipeline(large_backend, COMMON_TERM, page=5),
            label=f"full pipeline  '{COMMON_TERM}'  page 5",
        )[0]
        print(f"  -> {len(ordered_ids)} total results, {len(hits)} hits on page")

    def test_pipeline_rare(self, large_backend: TantivyBackend):
        """Full pipeline: rare term, page 1 (fast path)."""
        ordered_ids, hits = profile_cpu(
            lambda: self._run_pipeline(large_backend, RARE_TERM, page=1),
            label=f"full pipeline  '{RARE_TERM}'  page 1",
        )[0]
        print(f"  -> {len(ordered_ids)} total results, {len(hits)} hits on page")

    def test_pipeline_repeated(self, large_backend: TantivyBackend):
        """Repeated runs to get stable timing (no cProfile overhead)."""
        print()
        for term, label in [
            (COMMON_TERM, f"'{COMMON_TERM}' (large)"),
            (MEDIUM_TERM, f"'{MEDIUM_TERM}' (medium)"),
            (RARE_TERM, f"'{RARE_TERM}'  (rare)"),
        ]:
            _time(
                lambda t=term: self._run_pipeline(large_backend, t, page=1),
                label=f"full pipeline {label} page 1",
                runs=3,
            )
