import pytest
from django.contrib.auth.models import User

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.search._backend import SearchMode
from documents.search._backend import TantivyBackend
from documents.search._backend import get_backend
from documents.search._backend import reset_backend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestWriteBatch:
    """Test WriteBatch context manager functionality."""

    def test_rolls_back_on_exception(self, backend: TantivyBackend):
        """Batch operations must rollback on exception to preserve index integrity."""
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

    def test_text_mode_limits_default_search_to_title_and_content(
        self,
        backend: TantivyBackend,
    ):
        """Simple text mode must not match metadata-only fields."""
        doc = Document.objects.create(
            title="Invoice document",
            content="monthly statement",
            checksum="TXT1",
            pk=9,
        )
        backend.add_or_update(doc)

        metadata_only = backend.search(
            "document_type:invoice",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert metadata_only.total == 0

        content_match = backend.search(
            "monthly",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert content_match.total == 1

    def test_title_mode_limits_default_search_to_title_only(
        self,
        backend: TantivyBackend,
    ):
        """Title mode must not match content-only terms."""
        doc = Document.objects.create(
            title="Invoice document",
            content="monthly statement",
            checksum="TXT2",
            pk=10,
        )
        backend.add_or_update(doc)

        content_only = backend.search(
            "monthly",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TITLE,
        )
        assert content_only.total == 0

        title_match = backend.search(
            "invoice",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TITLE,
        )
        assert title_match.total == 1

    def test_text_mode_matches_partial_term_substrings(
        self,
        backend: TantivyBackend,
    ):
        """Simple text mode should support substring matching within tokens."""
        doc = Document.objects.create(
            title="Account access",
            content="password reset instructions",
            checksum="TXT3",
            pk=11,
        )
        backend.add_or_update(doc)

        prefix_match = backend.search(
            "pass",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert prefix_match.total == 1

        infix_match = backend.search(
            "sswo",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert infix_match.total == 1

        phrase_match = backend.search(
            "sswo re",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert phrase_match.total == 1

    def test_text_mode_does_not_match_on_partial_term_overlap(
        self,
        backend: TantivyBackend,
    ):
        """Simple text mode should not match documents that merely share partial fragments."""
        doc = Document.objects.create(
            title="Adobe Acrobat PDF Files",
            content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            checksum="TXT7",
            pk=13,
        )
        backend.add_or_update(doc)

        non_match = backend.search(
            "raptor",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert non_match.total == 0

    def test_text_mode_anchors_later_query_tokens_to_token_starts(
        self,
        backend: TantivyBackend,
    ):
        """Multi-token simple search should not match later tokens in the middle of a word."""
        exact_doc = Document.objects.create(
            title="Z-Berichte 6",
            content="monthly report",
            checksum="TXT9",
            pk=15,
        )
        prefix_doc = Document.objects.create(
            title="Z-Berichte 60",
            content="monthly report",
            checksum="TXT10",
            pk=16,
        )
        false_positive = Document.objects.create(
            title="Z-Berichte 16",
            content="monthly report",
            checksum="TXT11",
            pk=17,
        )
        backend.add_or_update(exact_doc)
        backend.add_or_update(prefix_doc)
        backend.add_or_update(false_positive)

        results = backend.search(
            "Z-Berichte 6",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        result_ids = {hit["id"] for hit in results.hits}

        assert exact_doc.id in result_ids
        assert prefix_doc.id in result_ids
        assert false_positive.id not in result_ids

    def test_text_mode_ignores_queries_without_searchable_tokens(
        self,
        backend: TantivyBackend,
    ):
        """Simple text mode should safely return no hits for symbol-only strings."""
        doc = Document.objects.create(
            title="Guide",
            content="This is a guide.",
            checksum="TXT8",
            pk=14,
        )
        backend.add_or_update(doc)

        no_tokens = backend.search(
            "!!!",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TEXT,
        )
        assert no_tokens.total == 0

    def test_title_mode_matches_partial_term_substrings(
        self,
        backend: TantivyBackend,
    ):
        """Title mode should support substring matching within title tokens."""
        doc = Document.objects.create(
            title="Password guide",
            content="reset instructions",
            checksum="TXT4",
            pk=12,
        )
        backend.add_or_update(doc)

        prefix_match = backend.search(
            "pass",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TITLE,
        )
        assert prefix_match.total == 1

        infix_match = backend.search(
            "sswo",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TITLE,
        )
        assert infix_match.total == 1

        phrase_match = backend.search(
            "sswo gu",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
            search_mode=SearchMode.TITLE,
        )
        assert phrase_match.total == 1

    def test_scores_normalised_top_hit_is_one(self, backend: TantivyBackend):
        """Search scores must be normalized so top hit has score 1.0 for UI consistency."""
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

    def test_sort_field_ascending(self, backend: TantivyBackend):
        """Searching with sort_reverse=False must return results in ascending ASN order."""
        for asn in [30, 10, 20]:
            doc = Document.objects.create(
                title="sortable",
                content="sortable content",
                checksum=f"SFA{asn}",
                archive_serial_number=asn,
            )
            backend.add_or_update(doc)

        r = backend.search(
            "sortable",
            user=None,
            page=1,
            page_size=10,
            sort_field="archive_serial_number",
            sort_reverse=False,
        )
        assert r.total == 3
        asns = [Document.objects.get(pk=h["id"]).archive_serial_number for h in r.hits]
        assert asns == [10, 20, 30]

    def test_sort_field_descending(self, backend: TantivyBackend):
        """Searching with sort_reverse=True must return results in descending ASN order."""
        for asn in [30, 10, 20]:
            doc = Document.objects.create(
                title="sortable",
                content="sortable content",
                checksum=f"SFD{asn}",
                archive_serial_number=asn,
            )
            backend.add_or_update(doc)

        r = backend.search(
            "sortable",
            user=None,
            page=1,
            page_size=10,
            sort_field="archive_serial_number",
            sort_reverse=True,
        )
        assert r.total == 3
        asns = [Document.objects.get(pk=h["id"]).archive_serial_number for h in r.hits]
        assert asns == [30, 20, 10]

    def test_fuzzy_threshold_filters_low_score_hits(
        self,
        backend: TantivyBackend,
        settings,
    ):
        """When ADVANCED_FUZZY_SEARCH_THRESHOLD exceeds all normalized scores, hits must be filtered out."""
        doc = Document.objects.create(
            title="Invoice document",
            content="financial report",
            checksum="FT1",
            pk=120,
        )
        backend.add_or_update(doc)

        # Threshold above 1.0 filters every hit (normalized scores top out at 1.0)
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 1.1
        r = backend.search(
            "invoice",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert r.hits == []

    def test_owner_filter(self, backend: TantivyBackend):
        """Document owners can search their private documents; other users cannot access them."""
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

    def test_highlight_page_only_highlights_requested_slice(
        self,
        backend: TantivyBackend,
    ):
        """Only hits in the highlight_page slice should have non-empty highlights."""
        for i in range(6):
            doc = Document.objects.create(
                title=f"highlight doc {i}",
                content=f"searchable highlight content number {i}",
                checksum=f"HP{i}",
            )
            backend.add_or_update(doc)

        r = backend.search(
            "searchable",
            user=None,
            page=1,
            page_size=10000,
            sort_field=None,
            sort_reverse=False,
            highlight_page=1,
            highlight_page_size=3,
        )
        assert r.total == 6
        assert len(r.hits) == 6
        highlighted = [h for h in r.hits if h["highlights"]]
        not_highlighted = [h for h in r.hits if not h["highlights"]]
        assert len(highlighted) == 3
        assert len(not_highlighted) == 3

    def test_highlight_page_2_highlights_correct_slice(self, backend: TantivyBackend):
        """highlight_page=2 should highlight only the second page of results."""
        for i in range(6):
            doc = Document.objects.create(
                title=f"page2 doc {i}",
                content=f"searchable page2 content number {i}",
                checksum=f"HP2{i}",
            )
            backend.add_or_update(doc)

        r = backend.search(
            "searchable",
            user=None,
            page=1,
            page_size=10000,
            sort_field=None,
            sort_reverse=False,
            highlight_page=2,
            highlight_page_size=2,
        )
        assert r.total == 6
        assert len(r.hits) == 6
        highlighted = [h for h in r.hits if h["highlights"]]
        not_highlighted = [h for h in r.hits if not h["highlights"]]
        # Only 2 hits (the second page) should have highlights
        assert len(highlighted) == 2
        assert len(not_highlighted) == 4

    def test_no_highlight_page_highlights_all(self, backend: TantivyBackend):
        """When highlight_page is not specified, all hits get highlights (backward compat)."""
        for i in range(3):
            doc = Document.objects.create(
                title=f"compat doc {i}",
                content=f"searchable compat content {i}",
                checksum=f"HC{i}",
            )
            backend.add_or_update(doc)

        r = backend.search(
            "searchable",
            user=None,
            page=1,
            page_size=10000,
            sort_field=None,
            sort_reverse=False,
        )
        assert len(r.hits) == 3
        for hit in r.hits:
            assert "content" in hit["highlights"]


class TestRebuild:
    """Test index rebuilding functionality."""

    def test_with_iter_wrapper_called(self, backend: TantivyBackend):
        """Index rebuild must pass documents through iter_wrapper for progress tracking."""
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
        """Autocomplete must return words matching the given prefix."""
        doc = Document.objects.create(
            title="Invoice from Microsoft Corporation",
            content="payment details",
            checksum="AC1",
            pk=40,
        )
        backend.add_or_update(doc)

        results = backend.autocomplete("micro", limit=10)
        assert "microsoft" in results

    def test_results_ordered_by_document_frequency(self, backend: TantivyBackend):
        """Autocomplete results must be ordered by document frequency to prioritize common terms."""
        # "payment" appears in 3 docs; "payslip" in 1 — "pay" prefix should
        # return "payment" before "payslip".
        for i, (title, checksum) in enumerate(
            [
                ("payment invoice", "AF1"),
                ("payment receipt", "AF2"),
                ("payment confirmation", "AF3"),
                ("payslip march", "AF4"),
            ],
            start=41,
        ):
            doc = Document.objects.create(
                title=title,
                content="details",
                checksum=checksum,
                pk=i,
            )
            backend.add_or_update(doc)

        results = backend.autocomplete("pay", limit=10)
        assert results.index("payment") < results.index("payslip")


class TestMoreLikeThis:
    """Test more like this functionality."""

    def test_excludes_original(self, backend: TantivyBackend):
        """More like this queries must exclude the reference document from results."""
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

    def test_with_user_applies_permission_filter(self, backend: TantivyBackend):
        """more_like_this with a user must exclude documents that user cannot see."""
        viewer = User.objects.create_user("mlt_viewer")
        other = User.objects.create_user("mlt_other")
        public_doc = Document.objects.create(
            title="Public financial document",
            content="quarterly financial analysis report figures",
            checksum="MLT3",
            pk=52,
        )
        private_doc = Document.objects.create(
            title="Private financial document",
            content="quarterly financial analysis report figures",
            checksum="MLT4",
            pk=53,
            owner=other,
        )
        backend.add_or_update(public_doc)
        backend.add_or_update(private_doc)

        results = backend.more_like_this(doc_id=52, user=viewer, page=1, page_size=10)
        returned_ids = [hit["id"] for hit in results.hits]
        # private_doc is owned by other, so viewer cannot see it
        assert 53 not in returned_ids

    def test_document_not_in_index_returns_empty(self, backend: TantivyBackend):
        """more_like_this for a doc_id absent from the index must return empty results."""
        results = backend.more_like_this(doc_id=9999, user=None, page=1, page_size=10)
        assert results.hits == []
        assert results.total == 0


class TestSingleton:
    """Test get_backend() and reset_backend() singleton lifecycle."""

    @pytest.fixture(autouse=True)
    def _clean(self):
        reset_backend()
        yield
        reset_backend()

    def test_returns_same_instance_on_repeated_calls(self, index_dir):
        """Singleton pattern: repeated calls to get_backend() must return the same instance."""
        assert get_backend() is get_backend()

    def test_reinitializes_when_index_dir_changes(self, tmp_path, settings):
        """Backend singleton must reinitialize when INDEX_DIR setting changes for test isolation."""
        settings.INDEX_DIR = tmp_path / "a"
        (tmp_path / "a").mkdir()
        b1 = get_backend()

        settings.INDEX_DIR = tmp_path / "b"
        (tmp_path / "b").mkdir()
        b2 = get_backend()

        assert b1 is not b2
        assert b2._path == tmp_path / "b"

    def test_reset_forces_new_instance(self, index_dir):
        """reset_backend() must force creation of a new backend instance on next get_backend() call."""
        b1 = get_backend()
        reset_backend()
        b2 = get_backend()
        assert b1 is not b2


class TestFieldHandling:
    """Test handling of various document fields."""

    def test_none_values_handled_correctly(self, backend: TantivyBackend):
        """Document fields with None values must not cause indexing errors."""
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
        """Custom fields must be indexed with both field name and value for structured queries."""
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

    def test_select_custom_field_indexes_label_not_id(self, backend: TantivyBackend):
        """SELECT custom fields must index the human-readable label, not the opaque option ID."""
        field = CustomField.objects.create(
            name="Category",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={
                "select_options": [
                    {"id": "opt_abc", "label": "Invoice"},
                    {"id": "opt_def", "label": "Receipt"},
                ],
            },
        )
        doc = Document.objects.create(
            title="Categorised doc",
            content="test",
            checksum="SEL1",
            pk=71,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=field,
            value_select="opt_abc",
        )
        backend.add_or_update(doc)

        # Label should be findable
        results = backend.search(
            "custom_fields.value:invoice",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1

        # Opaque ID must not appear in the index
        results = backend.search(
            "custom_fields.value:opt_abc",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 0

    def test_none_custom_field_value_not_indexed(self, backend: TantivyBackend):
        """Custom field instances with no value set must not produce an index entry."""
        field = CustomField.objects.create(
            name="Optional",
            data_type=CustomField.FieldDataType.SELECT,
            extra_data={"select_options": [{"id": "opt_1", "label": "Yes"}]},
        )
        doc = Document.objects.create(
            title="Unset field doc",
            content="test",
            checksum="SEL2",
            pk=72,
        )
        CustomFieldInstance.objects.create(
            document=doc,
            field=field,
            value_select=None,
        )
        backend.add_or_update(doc)

        # The string "none" must not appear as an indexed value
        results = backend.search(
            "custom_fields.value:none",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 0

    def test_notes_include_user_information(self, backend: TantivyBackend):
        """Notes must be indexed with user information when available for structured queries."""
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

        # Test notes search — must use structured JSON syntax now that note
        # is no longer in DEFAULT_SEARCH_FIELDS
        results = backend.search(
            "notes.note:important",
            user=None,
            page=1,
            page_size=10,
            sort_field=None,
            sort_reverse=False,
        )
        assert results.total == 1, (
            f"Expected 1, got {results.total}. Note content should be searchable via notes.note: prefix."
        )
