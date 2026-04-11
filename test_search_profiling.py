"""
Search performance profiling tests.

Run explicitly — excluded from the normal test suite:

    uv run pytest -m profiling -s -p no:xdist --override-ini="addopts=" -v

The ``-s`` flag is required to see profile_block() output.
The ``-p no:xdist`` flag disables parallel execution for accurate measurements.

Corpus: 5 000 documents generated deterministically from a fixed Faker seed,
with realistic variety: 30 correspondents, 15 document types, 50 tags, ~500
notes spread across ~10 % of documents.
"""

from __future__ import annotations

import random

import pytest
from django.contrib.auth.models import User
from faker import Faker
from profiling import profile_block
from rest_framework.test import APIClient

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import Tag
from documents.search import get_backend
from documents.search import reset_backend
from documents.search._backend import SearchMode

pytestmark = [pytest.mark.profiling, pytest.mark.search, pytest.mark.django_db]

# ---------------------------------------------------------------------------
# Corpus parameters
# ---------------------------------------------------------------------------

DOC_COUNT = 5_000
SEED = 42
NUM_CORRESPONDENTS = 30
NUM_DOC_TYPES = 15
NUM_TAGS = 50
NOTE_FRACTION = 0.10  # ~500 documents get a note
PAGE_SIZE = 25


def _build_corpus(rng: random.Random, fake: Faker) -> None:
    """
    Insert the full corpus into the database and index it.

    Uses bulk_create for the Document rows (fast) then handles the M2M tag
    relationships and notes individually.  Indexes the full corpus with a
    single backend.rebuild() call.
    """
    import datetime

    # ---- lookup objects -------------------------------------------------
    correspondents = [
        Correspondent.objects.create(name=f"profcorp-{i}-{fake.company()}"[:128])
        for i in range(NUM_CORRESPONDENTS)
    ]
    doc_types = [
        DocumentType.objects.create(name=f"proftype-{i}-{fake.word()}"[:128])
        for i in range(NUM_DOC_TYPES)
    ]
    tags = [
        Tag.objects.create(name=f"proftag-{i}-{fake.word()}"[:100])
        for i in range(NUM_TAGS)
    ]
    note_user = User.objects.create_user(username="profnoteuser", password="x")

    # ---- bulk-create documents ------------------------------------------
    base_date = datetime.date(2018, 1, 1)
    raw_docs = []
    for i in range(DOC_COUNT):
        day_offset = rng.randint(0, 6 * 365)
        created = base_date + datetime.timedelta(days=day_offset)
        raw_docs.append(
            Document(
                title=fake.sentence(nb_words=rng.randint(3, 9)).rstrip("."),
                content="\n\n".join(
                    fake.paragraph(nb_sentences=rng.randint(3, 7))
                    for _ in range(rng.randint(2, 5))
                ),
                checksum=f"PROF{i:07d}",
                correspondent=rng.choice(correspondents + [None] * 8),
                document_type=rng.choice(doc_types + [None] * 4),
                created=created,
            ),
        )
    documents = Document.objects.bulk_create(raw_docs)

    # ---- tags (M2M, post-bulk) ------------------------------------------
    for doc in documents:
        k = rng.randint(0, 5)
        if k:
            doc.tags.add(*rng.sample(tags, k))

    # ---- notes on ~10 % of docs -----------------------------------------
    note_docs = rng.sample(documents, int(DOC_COUNT * NOTE_FRACTION))
    for doc in note_docs:
        Note.objects.create(
            document=doc,
            note=fake.sentence(nb_words=rng.randint(6, 20)),
            user=note_user,
        )

    # ---- build Tantivy index --------------------------------------------
    backend = get_backend()
    qs = Document.objects.select_related(
        "correspondent",
        "document_type",
        "storage_path",
        "owner",
    ).prefetch_related("tags", "notes__user", "custom_fields__field")
    backend.rebuild(qs)


class TestSearchProfiling:
    """
    Performance profiling for the Tantivy search backend and DRF API layer.

    Each test builds a fresh 5 000-document corpus, exercises one hot path,
    and prints profile_block() measurements to stdout.  No correctness
    assertions — the goal is to surface hot spots and track regressions.
    """

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path, settings):
        index_dir = tmp_path / "index"
        index_dir.mkdir()
        settings.INDEX_DIR = index_dir

        reset_backend()
        rng = random.Random(SEED)
        fake = Faker()
        Faker.seed(SEED)

        self.user = User.objects.create_superuser(
            username="profiler",
            password="admin",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        _build_corpus(rng, fake)
        yield
        reset_backend()

    # -- 1. Backend: search_ids relevance ---------------------------------

    def test_profile_search_ids_relevance(self):
        """Profile: search_ids() with relevance ordering across several queries."""
        backend = get_backend()
        queries = [
            "invoice payment",
            "annual report",
            "bank statement",
            "contract agreement",
            "receipt",
        ]
        with profile_block(f"search_ids — relevance ({len(queries)} queries)"):
            for q in queries:
                backend.search_ids(q, user=None)

    # -- 2. Backend: search_ids with Tantivy-native sort ------------------

    def test_profile_search_ids_sorted(self):
        """Profile: search_ids() sorted by a Tantivy fast field (created)."""
        backend = get_backend()
        with profile_block("search_ids — sorted by created (asc + desc)"):
            backend.search_ids(
                "the",
                user=None,
                sort_field="created",
                sort_reverse=False,
            )
            backend.search_ids(
                "the",
                user=None,
                sort_field="created",
                sort_reverse=True,
            )

    # -- 3. Backend: highlight_hits for a page of 25 ----------------------

    def test_profile_highlight_hits(self):
        """Profile: highlight_hits() for a 25-document page."""
        backend = get_backend()
        all_ids = backend.search_ids("report", user=None)
        page_ids = all_ids[:PAGE_SIZE]
        with profile_block(f"highlight_hits — {len(page_ids)} docs"):
            backend.highlight_hits("report", page_ids)

    # -- 4. Backend: autocomplete -----------------------------------------

    def test_profile_autocomplete(self):
        """Profile: autocomplete() with eight common prefixes."""
        backend = get_backend()
        prefixes = ["inv", "pay", "con", "rep", "sta", "acc", "doc", "fin"]
        with profile_block(f"autocomplete — {len(prefixes)} prefixes"):
            for prefix in prefixes:
                backend.autocomplete(prefix, limit=10)

    # -- 5. Backend: simple-mode search (TEXT and TITLE) ------------------

    def test_profile_search_ids_simple_modes(self):
        """Profile: search_ids() in TEXT and TITLE simple-search modes."""
        backend = get_backend()
        queries = ["invoice 2023", "annual report", "bank statement"]
        with profile_block(
            f"search_ids — TEXT + TITLE modes ({len(queries)} queries each)",
        ):
            for q in queries:
                backend.search_ids(q, user=None, search_mode=SearchMode.TEXT)
                backend.search_ids(q, user=None, search_mode=SearchMode.TITLE)

    # -- 6. API: full round-trip, relevance + page 1 ----------------------

    def test_profile_api_relevance_search(self):
        """Profile: full API search round-trip, relevance order, page 1."""
        with profile_block(
            f"API /documents/?query=… relevance (page 1, page_size={PAGE_SIZE})",
        ):
            response = self.client.get(
                f"/api/documents/?query=invoice+payment&page=1&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200

    # -- 7. API: full round-trip, ORM-ordered (title) ---------------------

    def test_profile_api_orm_sorted_search(self):
        """Profile: full API search round-trip with ORM-delegated sort (title)."""
        with profile_block("API /documents/?query=…&ordering=title"):
            response = self.client.get(
                f"/api/documents/?query=report&ordering=title&page=1&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200

    # -- 8. API: full round-trip, score sort ------------------------------

    def test_profile_api_score_sort(self):
        """Profile: full API search with ordering=-score (relevance, preserve order)."""
        with profile_block("API /documents/?query=…&ordering=-score"):
            response = self.client.get(
                f"/api/documents/?query=statement&ordering=-score&page=1&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200

    # -- 9. API: full round-trip, with selection_data ---------------------

    def test_profile_api_with_selection_data(self):
        """Profile: full API search including include_selection_data=true."""
        with profile_block("API /documents/?query=…&include_selection_data=true"):
            response = self.client.get(
                f"/api/documents/?query=contract&page=1&page_size={PAGE_SIZE}"
                "&include_selection_data=true",
            )
        assert response.status_code == 200
        assert "selection_data" in response.data

    # -- 10. API: paginated (page 2) --------------------------------------

    def test_profile_api_page_2(self):
        """Profile: full API search, page 2 — exercises page offset arithmetic."""
        with profile_block(f"API /documents/?query=…&page=2&page_size={PAGE_SIZE}"):
            response = self.client.get(
                f"/api/documents/?query=the&page=2&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200
