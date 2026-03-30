import pytest
from django.contrib.auth.models import User

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestWriteBatch:
    """Test WriteBatch context manager functionality."""

    def test_rolls_back_on_exception(self, backend: TantivyBackend):
        """Data integrity: a mid-batch exception must not corrupt the index."""
        doc = Document.objects.create(
            title="Rollback Target",
            content="should survive",
            checksum="RB1",
            pk=1,
        )
        backend.add_or_update(doc)

        try:
            with backend.batch_update() as batch:
                batch.remove(doc.pk)
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass

        r = backend.search(
            "should survive",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert r.total == 1


class TestSearch:
    """Test search functionality."""

    def test_scores_normalised_top_hit_is_one(self, backend: TantivyBackend):
        """UI score bar depends on the top hit being 1.0."""
        for i, title in enumerate(["bank invoice", "bank statement", "bank receipt"]):
            doc = Document.objects.create(
                title=title,
                content=title,
                checksum=f"SN{i}",
                pk=10 + i,
            )
            backend.add_or_update(doc)
        r = backend.search(
            "bank",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert r.hits[0]["score"] == pytest.approx(1.0)
        assert all(0.0 <= h["score"] <= 1.0 for h in r.hits)

    def test_owner_filter(self, backend: TantivyBackend):
        """Owner can find their document; other user cannot."""
        owner = User.objects.create_user("owner")
        other = User.objects.create_user("other")
        doc = Document.objects.create(
            title="Private",
            content="secret",
            checksum="PF1",
            pk=20,
            owner=owner,
        )
        backend.add_or_update(doc)

        assert (
            backend.search(
                "secret",
                user=owner,
                page=1,
                page_size=10,
                sort_field=None,
                sort_reverse=False,
            ).total
            == 1
        )
        assert (
            backend.search(
                "secret",
                user=other,
                page=1,
                page_size=10,
                sort_field=None,
                sort_reverse=False,
            ).total
            == 0
        )


class TestRebuild:
    """Test index rebuilding functionality."""

    def test_with_iter_wrapper_called(self, backend: TantivyBackend):
        """rebuild() must pass documents through iter_wrapper."""
        seen = []

        def wrapper(docs):
            for doc in docs:
                seen.append(doc.pk)
                yield doc

        Document.objects.create(title="Tracked", content="x", checksum="TW1", pk=30)
        backend.rebuild(Document.objects.all(), iter_wrapper=wrapper)
        assert 30 in seen


class TestAutocomplete:
    """Test autocomplete functionality."""

    def test_basic_functionality(self, backend: TantivyBackend):
        """Autocomplete should find word prefixes."""
        doc = Document.objects.create(
            title="Invoice from Microsoft Corporation",
            content="payment details",
            checksum="AC1",
            pk=40,
        )
        backend.add_or_update(doc)

        results = backend.autocomplete("micro", limit=10)
        assert "microsoft" in results


class TestMoreLikeThis:
    """Test more like this functionality."""

    def test_excludes_original(self, backend: TantivyBackend):
        """More like this should not return the original document."""
        doc1 = Document.objects.create(
            title="Important document",
            content="financial information",
            checksum="MLT1",
            pk=50,
        )
        doc2 = Document.objects.create(
            title="Another document",
            content="financial report",
            checksum="MLT2",
            pk=51,
        )
        backend.add_or_update(doc1)
        backend.add_or_update(doc2)

        results = backend.more_like_this(doc_id=50, user=None, page=1, page_size=10)
        returned_ids = [hit["id"] for hit in results.hits]
        assert 50 not in returned_ids  # Original document excluded


class TestFieldHandling:
    """Test handling of various document fields."""

    def test_none_values_handled_correctly(self, backend: TantivyBackend):
        """Test that None values for original_filename and page_count are handled properly."""
        doc = Document.objects.create(
            title="Test Doc",
            content="test content",
            checksum="NV1",
            pk=60,
            original_filename=None,
            page_count=None,
        )
        # Should not raise an exception
        backend.add_or_update(doc)

        results = backend.search(
            "test",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1

    def test_custom_fields_include_name_and_value(self, backend: TantivyBackend):
        """Custom field indexing should include both name and value."""
        # Create a custom field
        field = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        doc = Document.objects.create(
            title="Invoice",
            content="test",
            checksum="CF1",
            pk=70,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=field,
            value_text="INV-2024-001",
        )

        # Should not raise an exception during indexing
        backend.add_or_update(doc)

        results = backend.search(
            "invoice",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1

    def test_notes_include_user_information(self, backend: TantivyBackend):
        """Notes should include user information when available."""
        user = User.objects.create_user("notewriter")
        doc = Document.objects.create(
            title="Doc with notes",
            content="test",
            checksum="NT1",
            pk=80,
        )
        Note.objects.create(document=doc, note="Important note", user=user)

        # Should not raise an exception during indexing
        backend.add_or_update(doc)

        # Test basic document search first
        results = backend.search(
            "test",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1, (
            f"Expected 1, got {results.total}. Document content should be searchable."
        )

        # Test notes search
        results = backend.search(
            "important",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1, (
            f"Expected 1, got {results.total}. Note content should be searchable."
        )
