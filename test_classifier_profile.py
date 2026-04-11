# ruff: noqa: T201
"""
cProfile + tracemalloc classifier profiling test.

Run with:
    uv run pytest ../test_classifier_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Corpus: 5 000 documents, 40 correspondents (25 AUTO), 25 doc types (15 AUTO),
        50 tags (30 AUTO), 20 storage paths (12 AUTO).

Document content is generated with Faker for realistic base text, with a
per-label fingerprint injected so the MLP has a real learning signal.

Scenarios:
  - train()         full corpus — memory and CPU profiles
  - second train()  no-op path — shows cost of the skip check
  - save()/load()   round-trip — model file size and memory cost
  - _update_data_vectorizer_hash()   isolated hash overhead
  - predict_*()     four independent calls per document — the 4x redundant
                    vectorization path used by the signal handlers
  - _vectorize()    cache-miss vs cache-hit breakdown

Memory: tracemalloc (delta + peak + top-20 allocation sites).
CPU:    cProfile sorted by cumulative time (top 30).
"""

from __future__ import annotations

import random
import time
from typing import TYPE_CHECKING

import pytest
from django.test import override_settings
from faker import Faker
from profiling import measure_memory
from profiling import profile_cpu

from documents.classifier import DocumentClassifier
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

# ---------------------------------------------------------------------------
# Corpus parameters
# ---------------------------------------------------------------------------

NUM_DOCS = 5_000
NUM_CORRESPONDENTS = 40  # first 25 are MATCH_AUTO
NUM_DOC_TYPES = 25  # first 15 are MATCH_AUTO
NUM_TAGS = 50  # first 30 are MATCH_AUTO
NUM_STORAGE_PATHS = 20  # first 12 are MATCH_AUTO

NUM_AUTO_CORRESPONDENTS = 25
NUM_AUTO_DOC_TYPES = 15
NUM_AUTO_TAGS = 30
NUM_AUTO_STORAGE_PATHS = 12

SEED = 42


# ---------------------------------------------------------------------------
# Content generation
# ---------------------------------------------------------------------------


def _make_label_fingerprint(
    fake: Faker,
    label_seed: int,
    n_words: int = 6,
) -> list[str]:
    """
    Generate a small set of unique-looking words to use as the learning
    fingerprint for a label.  Each label gets its own seeded Faker so the
    fingerprints are distinct and reproducible.
    """
    per_label_fake = Faker()
    per_label_fake.seed_instance(label_seed)
    # Mix word() and last_name() to get varied, pronounceable tokens
    words: list[str] = []
    while len(words) < n_words:
        w = per_label_fake.word().lower()
        if w not in words:
            words.append(w)
    return words


def _build_fingerprints(
    num_correspondents: int,
    num_doc_types: int,
    num_tags: int,
    num_paths: int,
) -> tuple[list[list[str]], list[list[str]], list[list[str]], list[list[str]]]:
    """Pre-generate per-label fingerprints.  Expensive once, free to reuse."""
    fake = Faker()
    # Use deterministic seeds offset by type so fingerprints don't collide
    corr_fps = [
        _make_label_fingerprint(fake, 1_000 + i) for i in range(num_correspondents)
    ]
    dtype_fps = [_make_label_fingerprint(fake, 2_000 + i) for i in range(num_doc_types)]
    tag_fps = [_make_label_fingerprint(fake, 3_000 + i) for i in range(num_tags)]
    path_fps = [_make_label_fingerprint(fake, 4_000 + i) for i in range(num_paths)]
    return corr_fps, dtype_fps, tag_fps, path_fps


def _build_content(
    fake: Faker,
    corr_fp: list[str] | None,
    dtype_fp: list[str] | None,
    tag_fps: list[list[str]],
    path_fp: list[str] | None,
) -> str:
    """
    Combine a Faker paragraph (realistic base text) with per-label
    fingerprint words so the classifier has a genuine learning signal.
    """
    # 3-sentence paragraph provides realistic vocabulary
    base = fake.paragraph(nb_sentences=3)

    extras: list[str] = []
    if corr_fp:
        extras.extend(corr_fp)
    if dtype_fp:
        extras.extend(dtype_fp)
    for fp in tag_fps:
        extras.extend(fp)
    if path_fp:
        extras.extend(path_fp)

    if extras:
        return base + " " + " ".join(extras)
    return base


# ---------------------------------------------------------------------------
# Module-scoped corpus fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    """Unlock the DB for the whole module (module-scoped)."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def classifier_corpus(tmp_path_factory, module_db):
    """
    Build the full 5 000-document corpus once for all profiling tests.

    Label objects are created individually (small number), documents are
    bulk-inserted, and tag M2M rows go through the through-table.

    Yields a dict with the model path and a sample content string for
    prediction tests.  All rows are deleted on teardown.
    """
    model_path: Path = tmp_path_factory.mktemp("cls_profile") / "model.pickle"

    with override_settings(MODEL_FILE=model_path):
        fake = Faker()
        Faker.seed(SEED)
        rng = random.Random(SEED)

        # Pre-generate fingerprints for all labels
        print("\n[setup] Generating label fingerprints...")
        corr_fps, dtype_fps, tag_fps, path_fps = _build_fingerprints(
            NUM_CORRESPONDENTS,
            NUM_DOC_TYPES,
            NUM_TAGS,
            NUM_STORAGE_PATHS,
        )

        # -----------------------------------------------------------------
        # 1. Create label objects
        # -----------------------------------------------------------------
        print(f"[setup] Creating {NUM_CORRESPONDENTS} correspondents...")
        correspondents: list[Correspondent] = []
        for i in range(NUM_CORRESPONDENTS):
            algo = (
                MatchingModel.MATCH_AUTO
                if i < NUM_AUTO_CORRESPONDENTS
                else MatchingModel.MATCH_NONE
            )
            correspondents.append(
                Correspondent.objects.create(
                    name=fake.company(),
                    matching_algorithm=algo,
                ),
            )

        print(f"[setup] Creating {NUM_DOC_TYPES} document types...")
        doc_types: list[DocumentType] = []
        for i in range(NUM_DOC_TYPES):
            algo = (
                MatchingModel.MATCH_AUTO
                if i < NUM_AUTO_DOC_TYPES
                else MatchingModel.MATCH_NONE
            )
            doc_types.append(
                DocumentType.objects.create(
                    name=fake.bs()[:64],
                    matching_algorithm=algo,
                ),
            )

        print(f"[setup] Creating {NUM_TAGS} tags...")
        tags: list[Tag] = []
        for i in range(NUM_TAGS):
            algo = (
                MatchingModel.MATCH_AUTO
                if i < NUM_AUTO_TAGS
                else MatchingModel.MATCH_NONE
            )
            tags.append(
                Tag.objects.create(
                    name=f"{fake.word()} {i}",
                    matching_algorithm=algo,
                    is_inbox_tag=False,
                ),
            )

        print(f"[setup] Creating {NUM_STORAGE_PATHS} storage paths...")
        storage_paths: list[StoragePath] = []
        for i in range(NUM_STORAGE_PATHS):
            algo = (
                MatchingModel.MATCH_AUTO
                if i < NUM_AUTO_STORAGE_PATHS
                else MatchingModel.MATCH_NONE
            )
            storage_paths.append(
                StoragePath.objects.create(
                    name=fake.word(),
                    path=f"{fake.word()}/{fake.word()}/{{title}}",
                    matching_algorithm=algo,
                ),
            )

        # -----------------------------------------------------------------
        # 2. Build document rows and M2M assignments
        # -----------------------------------------------------------------
        print(f"[setup] Building {NUM_DOCS} document rows...")
        doc_rows: list[Document] = []
        doc_tag_map: list[tuple[int, int]] = []  # (doc_position, tag_index)

        for i in range(NUM_DOCS):
            corr_idx = (
                rng.randrange(NUM_CORRESPONDENTS) if rng.random() < 0.80 else None
            )
            dt_idx = rng.randrange(NUM_DOC_TYPES) if rng.random() < 0.80 else None
            sp_idx = rng.randrange(NUM_STORAGE_PATHS) if rng.random() < 0.70 else None

            # 1-4 tags; most documents get at least one
            n_tags = rng.randint(1, 4) if rng.random() < 0.85 else 0
            assigned_tag_indices = rng.sample(range(NUM_TAGS), min(n_tags, NUM_TAGS))

            content = _build_content(
                fake,
                corr_fp=corr_fps[corr_idx] if corr_idx is not None else None,
                dtype_fp=dtype_fps[dt_idx] if dt_idx is not None else None,
                tag_fps=[tag_fps[ti] for ti in assigned_tag_indices],
                path_fp=path_fps[sp_idx] if sp_idx is not None else None,
            )

            doc_rows.append(
                Document(
                    title=fake.sentence(nb_words=5),
                    content=content,
                    checksum=f"{i:064x}",
                    correspondent=correspondents[corr_idx]
                    if corr_idx is not None
                    else None,
                    document_type=doc_types[dt_idx] if dt_idx is not None else None,
                    storage_path=storage_paths[sp_idx] if sp_idx is not None else None,
                ),
            )
            for ti in assigned_tag_indices:
                doc_tag_map.append((i, ti))

        t0 = time.perf_counter()
        Document.objects.bulk_create(doc_rows, batch_size=500)
        print(
            f"[setup] bulk_create {NUM_DOCS} documents: {time.perf_counter() - t0:.2f}s",
        )

        # -----------------------------------------------------------------
        # 3. Bulk-create M2M through-table rows
        # -----------------------------------------------------------------
        created_docs = list(Document.objects.order_by("pk"))
        through_rows = [
            Document.tags.through(
                document_id=created_docs[pos].pk,
                tag_id=tags[ti].pk,
            )
            for pos, ti in doc_tag_map
            if pos < len(created_docs)
        ]
        t0 = time.perf_counter()
        Document.tags.through.objects.bulk_create(
            through_rows,
            batch_size=1_000,
            ignore_conflicts=True,
        )
        print(
            f"[setup] bulk_create {len(through_rows)} tag M2M rows: "
            f"{time.perf_counter() - t0:.2f}s",
        )

        # Sample content for prediction tests
        sample_content = _build_content(
            fake,
            corr_fp=corr_fps[0],
            dtype_fp=dtype_fps[0],
            tag_fps=[tag_fps[0], tag_fps[1], tag_fps[5]],
            path_fp=path_fps[0],
        )

        yield {
            "model_path": model_path,
            "sample_content": sample_content,
        }

        # Teardown
        print("\n[teardown] Removing corpus...")
        Document.objects.all().delete()
        Correspondent.objects.all().delete()
        DocumentType.objects.all().delete()
        Tag.objects.all().delete()
        StoragePath.objects.all().delete()


# ---------------------------------------------------------------------------
# Training profiles
# ---------------------------------------------------------------------------


class TestClassifierTrainingProfile:
    """Profile DocumentClassifier.train() on the full corpus."""

    def test_train_memory(self, classifier_corpus, tmp_path):
        """
        Peak memory allocated during train().
        tracemalloc reports the delta and top allocation sites.
        """
        model_path = tmp_path / "model.pickle"
        with override_settings(MODEL_FILE=model_path):
            classifier = DocumentClassifier()

            result, _, _ = measure_memory(
                classifier.train,
                label=(
                    f"train()  [{NUM_DOCS} docs | "
                    f"{NUM_CORRESPONDENTS} correspondents ({NUM_AUTO_CORRESPONDENTS} AUTO) | "
                    f"{NUM_DOC_TYPES} doc types ({NUM_AUTO_DOC_TYPES} AUTO) | "
                    f"{NUM_TAGS} tags ({NUM_AUTO_TAGS} AUTO) | "
                    f"{NUM_STORAGE_PATHS} paths ({NUM_AUTO_STORAGE_PATHS} AUTO)]"
                ),
            )
            assert result is True, "train() must return True on first run"

            print("\n  Classifiers trained:")
            print(
                f"    tags_classifier:           {classifier.tags_classifier is not None}",
            )
            print(
                f"    correspondent_classifier:  {classifier.correspondent_classifier is not None}",
            )
            print(
                f"    document_type_classifier:  {classifier.document_type_classifier is not None}",
            )
            print(
                f"    storage_path_classifier:   {classifier.storage_path_classifier is not None}",
            )
            if classifier.data_vectorizer is not None:
                vocab_size = len(classifier.data_vectorizer.vocabulary_)
                print(f"    vocabulary size:           {vocab_size} terms")

    def test_train_cpu(self, classifier_corpus, tmp_path):
        """
        CPU profile of train() — shows time spent in DB queries,
        CountVectorizer.fit_transform(), and four MLPClassifier.fit() calls.
        """
        model_path = tmp_path / "model_cpu.pickle"
        with override_settings(MODEL_FILE=model_path):
            classifier = DocumentClassifier()
            profile_cpu(
                classifier.train,
                label=f"train()  [{NUM_DOCS} docs]",
                top=30,
            )

    def test_train_second_call_noop(self, classifier_corpus, tmp_path):
        """
        No-op path: second train() on unchanged data should return False.
        Still queries the DB to build the hash — shown here as the remaining cost.
        """
        model_path = tmp_path / "model_noop.pickle"
        with override_settings(MODEL_FILE=model_path):
            classifier = DocumentClassifier()

            t0 = time.perf_counter()
            classifier.train()
            first_ms = (time.perf_counter() - t0) * 1000

            result, second_elapsed = profile_cpu(
                classifier.train,
                label="train() second call (no-op — same data unchanged)",
                top=20,
            )
            assert result is False, "second train() should skip and return False"

            print(f"\n  First train:  {first_ms:.1f} ms  (full fit)")
            print(f"  Second train: {second_elapsed * 1000:.1f} ms  (skip)")
            print(f"  Speedup:      {first_ms / (second_elapsed * 1000):.1f}x")

    def test_vectorizer_hash_cost(self, classifier_corpus, tmp_path):
        """
        Isolate _update_data_vectorizer_hash() — pickles the entire
        CountVectorizer just to SHA256 it.  Called at both save and load.
        """
        import pickle

        model_path = tmp_path / "model_hash.pickle"
        with override_settings(MODEL_FILE=model_path):
            classifier = DocumentClassifier()
            classifier.train()

            profile_cpu(
                classifier._update_data_vectorizer_hash,
                label="_update_data_vectorizer_hash()  [pickle.dumps vectorizer + sha256]",
                top=10,
            )

            pickled_size = len(pickle.dumps(classifier.data_vectorizer))
            vocab_size = len(classifier.data_vectorizer.vocabulary_)
            print(f"\n  Vocabulary size:       {vocab_size} terms")
            print(f"  Pickled vectorizer:    {pickled_size / 1024:.1f} KiB")

    def test_save_load_roundtrip(self, classifier_corpus, tmp_path):
        """
        Profile save() and load() — model file size directly reflects how
        much memory the classifier occupies on disk (and roughly in RAM).
        """
        model_path = tmp_path / "model_saveload.pickle"
        with override_settings(MODEL_FILE=model_path):
            classifier = DocumentClassifier()
            classifier.train()

            _, save_peak, _ = measure_memory(
                classifier.save,
                label="save()  [pickle.dumps + HMAC + atomic rename]",
            )

            file_size_kib = model_path.stat().st_size / 1024
            print(f"\n  Model file size: {file_size_kib:.1f} KiB")

            classifier2 = DocumentClassifier()
            _, load_peak, _ = measure_memory(
                classifier2.load,
                label="load()  [read file + verify HMAC + pickle.loads]",
            )

            print("\n  Summary:")
            print(f"    Model file size:  {file_size_kib:.1f} KiB")
            print(f"    Save peak memory: {save_peak:.1f} KiB")
            print(f"    Load peak memory: {load_peak:.1f} KiB")


# ---------------------------------------------------------------------------
# Prediction profiles
# ---------------------------------------------------------------------------


class TestClassifierPredictionProfile:
    """
    Profile the four predict_*() methods — specifically the redundant
    per-call vectorization overhead from the signal handler pattern.
    """

    @pytest.fixture(autouse=True)
    def trained_classifier(self, classifier_corpus, tmp_path):
        model_path = tmp_path / "model_pred.pickle"
        self._ctx = override_settings(MODEL_FILE=model_path)
        self._ctx.enable()
        self.classifier = DocumentClassifier()
        self.classifier.train()
        self.content = classifier_corpus["sample_content"]
        yield
        self._ctx.disable()

    def test_predict_all_four_separately_cpu(self):
        """
        Profile all four predict_*() calls in the order the signal handlers
        fire them.  Call 1 is a cache miss; calls 2-4 hit the locmem cache
        but still pay sha256 + pickle.loads each time.
        """
        from django.core.cache import caches

        caches["read-cache"].clear()

        content = self.content
        print(f"\n  Content length: {len(content)} chars")

        calls = [
            ("predict_correspondent", self.classifier.predict_correspondent),
            ("predict_document_type", self.classifier.predict_document_type),
            ("predict_tags", self.classifier.predict_tags),
            ("predict_storage_path", self.classifier.predict_storage_path),
        ]

        timings: list[tuple[str, float]] = []
        for name, fn in calls:
            _, elapsed = profile_cpu(
                lambda f=fn: f(content),
                label=f"{name}()  [call {len(timings) + 1}/4]",
                top=15,
            )
            timings.append((name, elapsed * 1000))

        print("\n  Per-call timings (sequential, locmem cache):")
        for name, ms in timings:
            print(f"    {name:<32s}  {ms:8.3f} ms")
        print(f"    {'TOTAL':<32s}  {sum(t for _, t in timings):8.3f} ms")

    def test_predict_all_four_memory(self):
        """
        Memory allocated for the full four-prediction sequence, both cold
        and warm, to show pickle serialization allocation per call.
        """
        from django.core.cache import caches

        content = self.content
        calls = [
            self.classifier.predict_correspondent,
            self.classifier.predict_document_type,
            self.classifier.predict_tags,
            self.classifier.predict_storage_path,
        ]

        caches["read-cache"].clear()
        measure_memory(
            lambda: [fn(content) for fn in calls],
            label="all four predict_*()  [cache COLD — first call misses]",
        )

        measure_memory(
            lambda: [fn(content) for fn in calls],
            label="all four predict_*()  [cache WARM — all calls hit]",
        )

    def test_vectorize_cache_miss_vs_hit(self):
        """
        Isolate the cost of a cache miss (sha256 + transform + pickle.dumps)
        vs a cache hit (sha256 + pickle.loads).
        """
        from django.core.cache import caches

        read_cache = caches["read-cache"]
        content = self.content

        read_cache.clear()
        _, miss_elapsed = profile_cpu(
            lambda: self.classifier._vectorize(content),
            label="_vectorize()  [MISS: sha256 + transform + pickle.dumps]",
            top=15,
        )

        _, hit_elapsed = profile_cpu(
            lambda: self.classifier._vectorize(content),
            label="_vectorize()  [HIT:  sha256 + pickle.loads]",
            top=15,
        )

        print(f"\n  Cache miss: {miss_elapsed * 1000:.3f} ms")
        print(f"  Cache hit:  {hit_elapsed * 1000:.3f} ms")
        print(f"  Hit is {miss_elapsed / hit_elapsed:.1f}x faster than miss")

    def test_content_hash_overhead(self):
        """
        Micro-benchmark the sha256 of the content string — paid on every
        _vectorize() call regardless of cache state, including x4 per doc.
        """
        import hashlib

        content = self.content
        encoded = content.encode()
        runs = 5_000

        t0 = time.perf_counter()
        for _ in range(runs):
            hashlib.sha256(encoded).hexdigest()
        us_per_call = (time.perf_counter() - t0) / runs * 1_000_000

        print(f"\n  Content: {len(content)} chars / {len(encoded)} bytes")
        print(f"  sha256 cost per call:   {us_per_call:.2f} us  (avg over {runs} runs)")
        print(f"  x4 calls per document:  {us_per_call * 4:.2f} us  total overhead")
