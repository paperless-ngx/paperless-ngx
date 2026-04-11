"""
Document list API profiling — no search, pure ORM path.

Run with:
    uv run pytest ../test_doclist_profile.py \
        -m profiling --override-ini="addopts=" -s -v

Corpus: 5 000 documents, 30 correspondents, 20 doc types, 80 tags,
        ~500 notes (10 %), 10 custom fields with instances on ~50 % of docs.

Scenarios
---------
TestDocListProfile
  - test_list_default_ordering     GET /api/documents/ created desc, page 1, page_size=25
  - test_list_title_ordering       same with ordering=title
  - test_list_page_size_comparison page_size=10 / 25 / 100 in sequence
  - test_list_detail_fields        GET /api/documents/{id}/ — single document serializer cost
  - test_list_cpu_profile          cProfile of one list request

TestSelectionDataProfile
  - test_selection_data_unfiltered  _get_selection_data_for_queryset(all docs) in isolation
  - test_selection_data_via_api     GET /api/documents/?include_selection_data=true
  - test_selection_data_filtered    filtered vs unfiltered COUNT query comparison
"""

from __future__ import annotations

import datetime
import random
import time

import pytest
from django.contrib.auth.models import User
from faker import Faker
from profiling import profile_block
from profiling import profile_cpu
from rest_framework.test import APIClient

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import Tag
from documents.views import DocumentViewSet

pytestmark = [pytest.mark.profiling, pytest.mark.django_db]

# ---------------------------------------------------------------------------
# Corpus parameters
# ---------------------------------------------------------------------------

NUM_DOCS = 5_000
NUM_CORRESPONDENTS = 30
NUM_DOC_TYPES = 20
NUM_TAGS = 80
NOTE_FRACTION = 0.10
CUSTOM_FIELD_COUNT = 10
CUSTOM_FIELD_FRACTION = 0.50
PAGE_SIZE = 25
SEED = 42


# ---------------------------------------------------------------------------
# Module-scoped corpus fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def module_db(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        yield


@pytest.fixture(scope="module")
def doclist_corpus(module_db):
    """
    Build a 5 000-document corpus with tags, notes, custom fields, correspondents,
    doc types, and storage paths.  All objects are deleted on teardown.
    """
    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)

    print(f"\n[setup] Creating {NUM_CORRESPONDENTS} correspondents...")  # noqa: T201
    correspondents = [
        Correspondent.objects.create(name=f"dlcorp-{i}-{fake.company()}"[:128])
        for i in range(NUM_CORRESPONDENTS)
    ]

    print(f"[setup] Creating {NUM_DOC_TYPES} doc types...")  # noqa: T201
    doc_types = [
        DocumentType.objects.create(name=f"dltype-{i}-{fake.word()}"[:128])
        for i in range(NUM_DOC_TYPES)
    ]

    print(f"[setup] Creating {NUM_TAGS} tags...")  # noqa: T201
    tags = [
        Tag.objects.create(name=f"dltag-{i}-{fake.word()}"[:100])
        for i in range(NUM_TAGS)
    ]

    print(f"[setup] Creating {CUSTOM_FIELD_COUNT} custom fields...")  # noqa: T201
    custom_fields = [
        CustomField.objects.create(
            name=f"Field {i}",
            data_type=CustomField.FieldDataType.STRING,
        )
        for i in range(CUSTOM_FIELD_COUNT)
    ]

    note_user = User.objects.create_user(username="doclistnoteuser", password="x")
    owner = User.objects.create_superuser(username="doclistowner", password="admin")

    print(f"[setup] Building {NUM_DOCS} document rows...")  # noqa: T201
    base_date = datetime.date(2018, 1, 1)
    raw_docs = []
    for i in range(NUM_DOCS):
        day_offset = rng.randint(0, 6 * 365)
        raw_docs.append(
            Document(
                title=fake.sentence(nb_words=rng.randint(3, 8)).rstrip("."),
                content="\n\n".join(
                    fake.paragraph(nb_sentences=rng.randint(2, 5))
                    for _ in range(rng.randint(1, 3))
                ),
                checksum=f"DL{i:07d}",
                correspondent=rng.choice(correspondents + [None] * 5),
                document_type=rng.choice(doc_types + [None] * 4),
                created=base_date + datetime.timedelta(days=day_offset),
                owner=owner if rng.random() < 0.8 else None,
            ),
        )
    t0 = time.perf_counter()
    documents = Document.objects.bulk_create(raw_docs)
    print(f"[setup] bulk_create {NUM_DOCS} docs: {time.perf_counter() - t0:.2f}s")  # noqa: T201

    t0 = time.perf_counter()
    for doc in documents:
        k = rng.randint(0, 5)
        if k:
            doc.tags.add(*rng.sample(tags, k))
    print(f"[setup] tag M2M assignments: {time.perf_counter() - t0:.2f}s")  # noqa: T201

    note_docs = rng.sample(documents, int(NUM_DOCS * NOTE_FRACTION))
    Note.objects.bulk_create(
        [
            Note(
                document=doc,
                note=fake.sentence(nb_words=rng.randint(4, 15)),
                user=note_user,
            )
            for doc in note_docs
        ],
    )

    cf_docs = rng.sample(documents, int(NUM_DOCS * CUSTOM_FIELD_FRACTION))
    CustomFieldInstance.objects.bulk_create(
        [
            CustomFieldInstance(
                document=doc,
                field=rng.choice(custom_fields),
                value_text=fake.word(),
            )
            for doc in cf_docs
        ],
    )

    first_doc_pk = documents[0].pk

    yield {"owner": owner, "first_doc_pk": first_doc_pk, "tags": tags}

    print("\n[teardown] Removing doclist corpus...")  # noqa: T201
    Document.objects.all().delete()
    Correspondent.objects.all().delete()
    DocumentType.objects.all().delete()
    Tag.objects.all().delete()
    CustomField.objects.all().delete()
    User.objects.filter(username__in=["doclistnoteuser", "doclistowner"]).delete()


# ---------------------------------------------------------------------------
# TestDocListProfile
# ---------------------------------------------------------------------------


class TestDocListProfile:
    """Profile GET /api/documents/ — pure ORM path, no Tantivy."""

    @pytest.fixture(autouse=True)
    def _client(self, doclist_corpus):
        owner = doclist_corpus["owner"]
        self.client = APIClient()
        self.client.force_authenticate(user=owner)
        self.first_doc_pk = doclist_corpus["first_doc_pk"]

    def test_list_default_ordering(self):
        """GET /api/documents/ default ordering (-created), page 1, page_size=25."""
        with profile_block(
            f"GET /api/documents/ default ordering  [page_size={PAGE_SIZE}]",
        ):
            response = self.client.get(
                f"/api/documents/?page=1&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200

    def test_list_title_ordering(self):
        """GET /api/documents/ ordered by title — tests ORM sort path."""
        with profile_block(
            f"GET /api/documents/?ordering=title  [page_size={PAGE_SIZE}]",
        ):
            response = self.client.get(
                f"/api/documents/?ordering=title&page=1&page_size={PAGE_SIZE}",
            )
        assert response.status_code == 200

    def test_list_page_size_comparison(self):
        """Compare serializer cost at page_size=10, 25, 100."""
        for page_size in [10, 25, 100]:
            with profile_block(f"GET /api/documents/  [page_size={page_size}]"):
                response = self.client.get(
                    f"/api/documents/?page=1&page_size={page_size}",
                )
            assert response.status_code == 200

    def test_list_detail_fields(self):
        """GET /api/documents/{id}/ — per-doc serializer cost with all relations."""
        pk = self.first_doc_pk
        with profile_block(f"GET /api/documents/{pk}/ — single doc serializer"):
            response = self.client.get(f"/api/documents/{pk}/")
        assert response.status_code == 200

    def test_list_cpu_profile(self):
        """cProfile of one list request — surfaces hot frames in serializer."""
        profile_cpu(
            lambda: self.client.get(
                f"/api/documents/?page=1&page_size={PAGE_SIZE}",
            ),
            label=f"GET /api/documents/ cProfile  [page_size={PAGE_SIZE}]",
            top=30,
        )


# ---------------------------------------------------------------------------
# TestSelectionDataProfile
# ---------------------------------------------------------------------------


class TestSelectionDataProfile:
    """Profile _get_selection_data_for_queryset — the 5+ COUNT queries per request."""

    @pytest.fixture(autouse=True)
    def _setup(self, doclist_corpus):
        owner = doclist_corpus["owner"]
        self.client = APIClient()
        self.client.force_authenticate(user=owner)
        self.tags = doclist_corpus["tags"]

    def test_selection_data_unfiltered(self):
        """Call _get_selection_data_for_queryset(all docs) directly — COUNT queries in isolation."""
        viewset = DocumentViewSet()
        qs = Document.objects.all()

        with profile_block("_get_selection_data_for_queryset(all docs) — direct call"):
            viewset._get_selection_data_for_queryset(qs)

    def test_selection_data_via_api(self):
        """Full API round-trip with include_selection_data=true."""
        with profile_block(
            f"GET /api/documents/?include_selection_data=true  [page_size={PAGE_SIZE}]",
        ):
            response = self.client.get(
                f"/api/documents/?page=1&page_size={PAGE_SIZE}&include_selection_data=true",
            )
        assert response.status_code == 200
        assert "selection_data" in response.data

    def test_selection_data_filtered(self):
        """selection_data on a tag-filtered queryset — filtered COUNT vs unfiltered."""
        tag = self.tags[0]
        viewset = DocumentViewSet()
        filtered_qs = Document.objects.filter(tags=tag)
        unfiltered_qs = Document.objects.all()

        print(f"\n  Tag '{tag.name}' matches {filtered_qs.count()} docs")  # noqa: T201

        with profile_block("_get_selection_data_for_queryset(unfiltered)"):
            viewset._get_selection_data_for_queryset(unfiltered_qs)

        with profile_block("_get_selection_data_for_queryset(filtered by tag)"):
            viewset._get_selection_data_for_queryset(filtered_qs)
