"""
Matching pipeline profiling.

Run with:
    uv run pytest ../test_matching_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Corpus: 1 document + 50 correspondents, 100 tags, 25 doc types, 20 storage
        paths. Labels are spread across all six matching algorithms
        (NONE, ANY, ALL, LITERAL, REGEX, FUZZY, AUTO).

Classifier is passed as None -- MATCH_AUTO models skip prediction gracefully,
which is correct for isolating the ORM query and Python-side evaluation cost.

Scenarios
---------
TestMatchingPipelineProfile
  - test_match_correspondents   50 correspondents, algorithm mix
  - test_match_tags             100 tags
  - test_match_document_types   25 doc types
  - test_match_storage_paths    20 storage paths
  - test_full_match_sequence    all four in order (cumulative consumption cost)
  - test_algorithm_breakdown    each MATCH_* algorithm in isolation
"""

from __future__ import annotations

import random

import pytest
from faker import Faker
from profiling import profile_block

from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag

pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

NUM_CORRESPONDENTS = 50
NUM_TAGS = 100
NUM_DOC_TYPES = 25
NUM_STORAGE_PATHS = 20
SEED = 42

# Algorithm distribution across labels (cycles through in order)
_ALGORITHMS = [
    MatchingModel.MATCH_NONE,
    MatchingModel.MATCH_ANY,
    MatchingModel.MATCH_ALL,
    MatchingModel.MATCH_LITERAL,
    MatchingModel.MATCH_REGEX,
    MatchingModel.MATCH_FUZZY,
    MatchingModel.MATCH_AUTO,
]


def _algo(i: int) -> int:
    return _ALGORITHMS[i % len(_ALGORITHMS)]


# ---------------------------------------------------------------------------
# Module-scoped corpus fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    """Unlock the DB for the whole module (module-scoped)."""
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def matching_corpus(module_db):
    """
    1 document with realistic content + dense matching model sets.
    Classifier=None so MATCH_AUTO models are simply skipped.
    """
    fake = Faker()
    Faker.seed(SEED)
    random.seed(SEED)

    # ---- matching models ---------------------------------------------------
    print(f"\n[setup] Creating {NUM_CORRESPONDENTS} correspondents...")  # noqa: T201
    correspondents = []
    for i in range(NUM_CORRESPONDENTS):
        algo = _algo(i)
        match_text = (
            fake.word()
            if algo not in (MatchingModel.MATCH_NONE, MatchingModel.MATCH_AUTO)
            else ""
        )
        if algo == MatchingModel.MATCH_REGEX:
            match_text = r"\b" + fake.word() + r"\b"
        correspondents.append(
            Correspondent.objects.create(
                name=f"mcorp-{i}-{fake.company()}"[:128],
                matching_algorithm=algo,
                match=match_text,
            ),
        )

    print(f"[setup] Creating {NUM_TAGS} tags...")  # noqa: T201
    tags = []
    for i in range(NUM_TAGS):
        algo = _algo(i)
        match_text = (
            fake.word()
            if algo not in (MatchingModel.MATCH_NONE, MatchingModel.MATCH_AUTO)
            else ""
        )
        if algo == MatchingModel.MATCH_REGEX:
            match_text = r"\b" + fake.word() + r"\b"
        tags.append(
            Tag.objects.create(
                name=f"mtag-{i}-{fake.word()}"[:100],
                matching_algorithm=algo,
                match=match_text,
            ),
        )

    print(f"[setup] Creating {NUM_DOC_TYPES} doc types...")  # noqa: T201
    doc_types = []
    for i in range(NUM_DOC_TYPES):
        algo = _algo(i)
        match_text = (
            fake.word()
            if algo not in (MatchingModel.MATCH_NONE, MatchingModel.MATCH_AUTO)
            else ""
        )
        if algo == MatchingModel.MATCH_REGEX:
            match_text = r"\b" + fake.word() + r"\b"
        doc_types.append(
            DocumentType.objects.create(
                name=f"mtype-{i}-{fake.word()}"[:128],
                matching_algorithm=algo,
                match=match_text,
            ),
        )

    print(f"[setup] Creating {NUM_STORAGE_PATHS} storage paths...")  # noqa: T201
    storage_paths = []
    for i in range(NUM_STORAGE_PATHS):
        algo = _algo(i)
        match_text = (
            fake.word()
            if algo not in (MatchingModel.MATCH_NONE, MatchingModel.MATCH_AUTO)
            else ""
        )
        if algo == MatchingModel.MATCH_REGEX:
            match_text = r"\b" + fake.word() + r"\b"
        storage_paths.append(
            StoragePath.objects.create(
                name=f"mpath-{i}-{fake.word()}",
                path=f"{fake.word()}/{{title}}",
                matching_algorithm=algo,
                match=match_text,
            ),
        )

    # ---- document with diverse content ------------------------------------
    doc = Document.objects.create(
        title="quarterly invoice payment tax financial statement",
        content=" ".join(fake.paragraph(nb_sentences=5) for _ in range(3)),
        checksum="MATCHPROF0001",
    )

    print(f"[setup] Document pk={doc.pk}, content length={len(doc.content)} chars")  # noqa: T201
    print(  # noqa: T201
        f"  Correspondents: {NUM_CORRESPONDENTS} "
        f"({sum(1 for c in correspondents if c.matching_algorithm == MatchingModel.MATCH_AUTO)} AUTO)",
    )
    print(  # noqa: T201
        f"  Tags: {NUM_TAGS} "
        f"({sum(1 for t in tags if t.matching_algorithm == MatchingModel.MATCH_AUTO)} AUTO)",
    )

    yield {"doc": doc}

    # Teardown
    print("\n[teardown] Removing matching corpus...")  # noqa: T201
    Document.objects.all().delete()
    Correspondent.objects.all().delete()
    Tag.objects.all().delete()
    DocumentType.objects.all().delete()
    StoragePath.objects.all().delete()


# ---------------------------------------------------------------------------
# TestMatchingPipelineProfile
# ---------------------------------------------------------------------------


class TestMatchingPipelineProfile:
    """Profile the matching functions called per document during consumption."""

    @pytest.fixture(autouse=True)
    def _setup(self, matching_corpus):
        self.doc = matching_corpus["doc"]

    def test_match_correspondents(self):
        """50 correspondents, algorithm mix. Query count + time."""
        with profile_block(
            f"match_correspondents()  [{NUM_CORRESPONDENTS} correspondents, mixed algorithms]",
        ):
            result = match_correspondents(self.doc, classifier=None)
        print(f"  -> {len(result)} matched")  # noqa: T201

    def test_match_tags(self):
        """100 tags -- densest set in real installs."""
        with profile_block(f"match_tags()  [{NUM_TAGS} tags, mixed algorithms]"):
            result = match_tags(self.doc, classifier=None)
        print(f"  -> {len(result)} matched")  # noqa: T201

    def test_match_document_types(self):
        """25 doc types."""
        with profile_block(
            f"match_document_types()  [{NUM_DOC_TYPES} types, mixed algorithms]",
        ):
            result = match_document_types(self.doc, classifier=None)
        print(f"  -> {len(result)} matched")  # noqa: T201

    def test_match_storage_paths(self):
        """20 storage paths."""
        with profile_block(
            f"match_storage_paths()  [{NUM_STORAGE_PATHS} paths, mixed algorithms]",
        ):
            result = match_storage_paths(self.doc, classifier=None)
        print(f"  -> {len(result)} matched")  # noqa: T201

    def test_full_match_sequence(self):
        """All four match_*() calls in order -- cumulative cost per document consumed."""
        with profile_block(
            "full match sequence: correspondents + doc_types + tags + storage_paths",
        ):
            match_correspondents(self.doc, classifier=None)
            match_document_types(self.doc, classifier=None)
            match_tags(self.doc, classifier=None)
            match_storage_paths(self.doc, classifier=None)

    def test_algorithm_breakdown(self):
        """Create one correspondent per algorithm and time each independently."""
        import time

        from documents.matching import matches

        fake = Faker()
        algo_names = {
            MatchingModel.MATCH_NONE: "MATCH_NONE",
            MatchingModel.MATCH_ANY: "MATCH_ANY",
            MatchingModel.MATCH_ALL: "MATCH_ALL",
            MatchingModel.MATCH_LITERAL: "MATCH_LITERAL",
            MatchingModel.MATCH_REGEX: "MATCH_REGEX",
            MatchingModel.MATCH_FUZZY: "MATCH_FUZZY",
        }
        doc = self.doc
        print()  # noqa: T201

        for algo, name in algo_names.items():
            match_text = fake.word() if algo != MatchingModel.MATCH_NONE else ""
            if algo == MatchingModel.MATCH_REGEX:
                match_text = r"\b" + fake.word() + r"\b"
            model = Correspondent(
                name=f"algo-test-{name}",
                matching_algorithm=algo,
                match=match_text,
            )
            # Time 1000 iterations to get stable microsecond readings
            runs = 1_000
            t0 = time.perf_counter()
            for _ in range(runs):
                matches(model, doc)
            us_per_call = (time.perf_counter() - t0) / runs * 1_000_000
            print(  # noqa: T201
                f"  {name:<20s}  {us_per_call:8.2f} us/call  (match={match_text[:20]!r})",
            )
