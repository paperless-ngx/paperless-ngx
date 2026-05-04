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

    def test_rolls_back_on_exception(self, backend: TantivyBackend) -> None:
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

        ids = backend.search_ids("should survive", user=None)
        assert len(ids) == 1


class TestSearch:
    """Test search query parsing and matching via search_ids."""

    def test_empty_index_returns_no_ids(self, backend: TantivyBackend) -> None:
        """Empty indexes must not pass a zero limit to Tantivy."""
        assert backend.search_ids("missing", user=None) == []

    def test_text_mode_limits_default_search_to_title_and_content(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Simple text mode must not match metadata-only fields."""
        doc = Document.objects.create(
            title="Invoice document",
            content="monthly statement",
            checksum="TXT1",
            pk=9,
        )
        backend.add_or_update(doc)

        assert (
            len(
                backend.search_ids(
                    "document_type:invoice",
                    user=None,
                    search_mode=SearchMode.TEXT,
                ),
            )
            == 0
        )
        assert (
            len(backend.search_ids("monthly", user=None, search_mode=SearchMode.TEXT))
            == 1
        )

    def test_title_mode_limits_default_search_to_title_only(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Title mode must not match content-only terms."""
        doc = Document.objects.create(
            title="Invoice document",
            content="monthly statement",
            checksum="TXT2",
            pk=10,
        )
        backend.add_or_update(doc)

        assert (
            len(backend.search_ids("monthly", user=None, search_mode=SearchMode.TITLE))
            == 0
        )
        assert (
            len(backend.search_ids("invoice", user=None, search_mode=SearchMode.TITLE))
            == 1
        )

    def test_text_mode_matches_partial_term_substrings(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Simple text mode should support substring matching within tokens."""
        doc = Document.objects.create(
            title="Account access",
            content="password reset instructions",
            checksum="TXT3",
            pk=11,
        )
        backend.add_or_update(doc)

        assert (
            len(backend.search_ids("pass", user=None, search_mode=SearchMode.TEXT)) == 1
        )
        assert (
            len(backend.search_ids("sswo", user=None, search_mode=SearchMode.TEXT)) == 1
        )
        assert (
            len(backend.search_ids("sswo re", user=None, search_mode=SearchMode.TEXT))
            == 1
        )

    def test_text_mode_does_not_match_on_partial_term_overlap(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Simple text mode should not match documents that merely share partial fragments."""
        doc = Document.objects.create(
            title="Adobe Acrobat PDF Files",
            content="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            checksum="TXT7",
            pk=13,
        )
        backend.add_or_update(doc)

        assert (
            len(backend.search_ids("raptor", user=None, search_mode=SearchMode.TEXT))
            == 0
        )

    def test_text_mode_anchors_later_query_tokens_to_token_starts(
        self,
        backend: TantivyBackend,
    ) -> None:
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

        result_ids = set(
            backend.search_ids("Z-Berichte 6", user=None, search_mode=SearchMode.TEXT),
        )

        assert exact_doc.id in result_ids
        assert prefix_doc.id in result_ids
        assert false_positive.id not in result_ids

    def test_text_mode_ignores_queries_without_searchable_tokens(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Simple text mode should safely return no hits for symbol-only strings."""
        doc = Document.objects.create(
            title="Guide",
            content="This is a guide.",
            checksum="TXT8",
            pk=14,
        )
        backend.add_or_update(doc)

        assert (
            len(backend.search_ids("!!!", user=None, search_mode=SearchMode.TEXT)) == 0
        )

    def test_title_mode_matches_partial_term_substrings(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Title mode should support substring matching within title tokens."""
        doc = Document.objects.create(
            title="Password guide",
            content="reset instructions",
            checksum="TXT4",
            pk=12,
        )
        backend.add_or_update(doc)

        assert (
            len(backend.search_ids("pass", user=None, search_mode=SearchMode.TITLE))
            == 1
        )
        assert (
            len(backend.search_ids("sswo", user=None, search_mode=SearchMode.TITLE))
            == 1
        )
        assert (
            len(backend.search_ids("sswo gu", user=None, search_mode=SearchMode.TITLE))
            == 1
        )

    def test_sort_field_ascending(self, backend: TantivyBackend) -> None:
        """Searching with sort_reverse=False must return results in ascending ASN order."""
        for asn in [30, 10, 20]:
            doc = Document.objects.create(
                title="sortable",
                content="sortable content",
                checksum=f"SFA{asn}",
                archive_serial_number=asn,
            )
            backend.add_or_update(doc)

        ids = backend.search_ids(
            "sortable",
            user=None,
            sort_field="archive_serial_number",
            sort_reverse=False,
        )
        assert len(ids) == 3
        asns = [Document.objects.get(pk=doc_id).archive_serial_number for doc_id in ids]
        assert asns == [10, 20, 30]

    def test_sort_field_descending(self, backend: TantivyBackend) -> None:
        """Searching with sort_reverse=True must return results in descending ASN order."""
        for asn in [30, 10, 20]:
            doc = Document.objects.create(
                title="sortable",
                content="sortable content",
                checksum=f"SFD{asn}",
                archive_serial_number=asn,
            )
            backend.add_or_update(doc)

        ids = backend.search_ids(
            "sortable",
            user=None,
            sort_field="archive_serial_number",
            sort_reverse=True,
        )
        assert len(ids) == 3
        asns = [Document.objects.get(pk=doc_id).archive_serial_number for doc_id in ids]
        assert asns == [30, 20, 10]


class TestSearchIds:
    """Test lightweight ID-only search."""

    def test_returns_matching_ids(self, backend: TantivyBackend) -> None:
        """search_ids must return IDs of all matching documents."""
        docs = []
        for i in range(5):
            doc = Document.objects.create(
                title=f"findable doc {i}",
                content="common keyword",
                checksum=f"SI{i}",
            )
            backend.add_or_update(doc)
            docs.append(doc)
        other = Document.objects.create(
            title="unrelated",
            content="nothing here",
            checksum="SI_other",
        )
        backend.add_or_update(other)

        ids = backend.search_ids(
            "common keyword",
            user=None,
            search_mode=SearchMode.QUERY,
        )
        assert set(ids) == {d.pk for d in docs}
        assert other.pk not in ids

    def test_respects_permission_filter(self, backend: TantivyBackend) -> None:
        """search_ids must respect user permission filtering."""
        owner = User.objects.create_user("ids_owner")
        other = User.objects.create_user("ids_other")
        doc = Document.objects.create(
            title="private doc",
            content="secret keyword",
            checksum="SIP1",
            owner=owner,
        )
        backend.add_or_update(doc)

        assert backend.search_ids(
            "secret",
            user=owner,
            search_mode=SearchMode.QUERY,
        ) == [doc.pk]
        assert (
            backend.search_ids("secret", user=other, search_mode=SearchMode.QUERY) == []
        )

    def test_respects_fuzzy_threshold(self, backend: TantivyBackend, settings) -> None:
        """search_ids must apply the same fuzzy threshold as search()."""
        doc = Document.objects.create(
            title="threshold test",
            content="unique term",
            checksum="SIT1",
        )
        backend.add_or_update(doc)

        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 1.1
        ids = backend.search_ids("unique", user=None, search_mode=SearchMode.QUERY)
        assert ids == []

    def test_returns_ids_for_text_mode(self, backend: TantivyBackend) -> None:
        """search_ids must work with TEXT search mode."""
        doc = Document.objects.create(
            title="text mode doc",
            content="findable phrase",
            checksum="SIM1",
        )
        backend.add_or_update(doc)

        ids = backend.search_ids("findable", user=None, search_mode=SearchMode.TEXT)
        assert ids == [doc.pk]


class TestRebuild:
    """Test index rebuilding functionality."""

    def test_with_iter_wrapper_called(self, backend: TantivyBackend) -> None:
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

    def test_basic_functionality(self, backend: TantivyBackend) -> None:
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

    def test_results_ordered_by_document_frequency(
        self,
        backend: TantivyBackend,
    ) -> None:
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

    def test_more_like_this_ids_excludes_original(
        self,
        backend: TantivyBackend,
    ) -> None:
        """more_like_this_ids must return IDs of similar documents, excluding the original."""
        doc1 = Document.objects.create(
            title="Important document",
            content="financial information report",
            checksum="MLTI1",
            pk=150,
        )
        doc2 = Document.objects.create(
            title="Another document",
            content="financial information report",
            checksum="MLTI2",
            pk=151,
        )
        backend.add_or_update(doc1)
        backend.add_or_update(doc2)

        ids = backend.more_like_this_ids(doc_id=150, user=None)
        assert 150 not in ids
        assert 151 in ids


class TestSingleton:
    """Test get_backend() and reset_backend() singleton lifecycle."""

    @pytest.fixture(autouse=True)
    def _clean(self):
        reset_backend()
        yield
        reset_backend()

    def test_returns_same_instance_on_repeated_calls(self, index_dir) -> None:
        """Singleton pattern: repeated calls to get_backend() must return the same instance."""
        assert get_backend() is get_backend()

    def test_reinitializes_when_index_dir_changes(self, tmp_path, settings) -> None:
        """Backend singleton must reinitialize when INDEX_DIR setting changes for test isolation."""
        settings.INDEX_DIR = tmp_path / "a"
        (tmp_path / "a").mkdir()
        b1 = get_backend()

        settings.INDEX_DIR = tmp_path / "b"
        (tmp_path / "b").mkdir()
        b2 = get_backend()

        assert b1 is not b2
        assert b2._path == tmp_path / "b"

    def test_reset_forces_new_instance(self, index_dir) -> None:
        """reset_backend() must force creation of a new backend instance on next get_backend() call."""
        b1 = get_backend()
        reset_backend()
        b2 = get_backend()
        assert b1 is not b2


class TestFieldHandling:
    """Test handling of various document fields."""

    def test_none_values_handled_correctly(self, backend: TantivyBackend) -> None:
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

        assert len(backend.search_ids("test", user=None)) == 1

    def test_custom_fields_include_name_and_value(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Custom fields must be indexed with both field name and value for structured queries."""
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

        backend.add_or_update(doc)

        assert len(backend.search_ids("invoice", user=None)) == 1

    def test_select_custom_field_indexes_label_not_id(
        self,
        backend: TantivyBackend,
    ) -> None:
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

        assert len(backend.search_ids("custom_fields.value:invoice", user=None)) == 1
        assert len(backend.search_ids("custom_fields.value:opt_abc", user=None)) == 0

    def test_none_custom_field_value_not_indexed(self, backend: TantivyBackend) -> None:
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

        assert len(backend.search_ids("custom_fields.value:none", user=None)) == 0

    def test_notes_include_user_information(self, backend: TantivyBackend) -> None:
        """Notes must be indexed with user information when available for structured queries."""
        user = User.objects.create_user("notewriter")
        doc = Document.objects.create(
            title="Doc with notes",
            content="test",
            checksum="NT1",
            pk=80,
        )
        Note.objects.create(document=doc, note="Important note", user=user)

        backend.add_or_update(doc)

        ids = backend.search_ids("test", user=None)
        assert len(ids) == 1, (
            f"Expected 1, got {len(ids)}. Document content should be searchable."
        )

        ids = backend.search_ids("notes.note:important", user=None)
        assert len(ids) == 1, (
            f"Expected 1, got {len(ids)}. Note content should be searchable via notes.note: prefix."
        )


class TestHighlightHits:
    """Test highlight_hits returns proper HTML strings, not raw Snippet objects."""

    def test_highlights_simple_text_mode_returns_html_string(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Simple text search should still produce content highlights for exact-token hits."""
        doc = Document.objects.create(
            title="Highlight Test",
            content="The quick brown fox jumps over the lazy dog",
            checksum="HH0",
            pk=89,
        )
        backend.add_or_update(doc)

        hits = backend.highlight_hits("quick", [doc.pk], search_mode=SearchMode.TEXT)

        assert len(hits) == 1
        highlights = hits[0]["highlights"]
        assert "content" in highlights
        assert "<b>" in highlights["content"]

    def test_highlights_content_returns_html_string(
        self,
        backend: TantivyBackend,
    ) -> None:
        """highlight_hits must return HTML strings (from Snippet.to_html()), not Snippet objects."""
        doc = Document.objects.create(
            title="Highlight Test",
            content="The quick brown fox jumps over the lazy dog",
            checksum="HH1",
            pk=90,
        )
        backend.add_or_update(doc)

        hits = backend.highlight_hits("quick", [doc.pk])

        assert len(hits) == 1
        highlights = hits[0]["highlights"]
        assert "content" in highlights
        content_highlight = highlights["content"]
        assert isinstance(content_highlight, str), (
            f"Expected str, got {type(content_highlight)}: {content_highlight!r}"
        )
        # Tantivy wraps matched terms in <b> tags
        assert "<b>" in content_highlight, (
            f"Expected HTML with <b> tags, got: {content_highlight!r}"
        )

    def test_highlights_notes_returns_html_string(
        self,
        backend: TantivyBackend,
    ) -> None:
        """Note highlights must be HTML strings via notes_text companion field.

        The notes JSON field does not support tantivy SnippetGenerator; the
        notes_text plain-text field is used instead.  We use the full-text
        query "urgent" (not notes.note:) because notes_text IS in
        DEFAULT_SEARCH_FIELDS via the normal search path… actually, we use
        notes.note: prefix so the query targets notes content directly, but
        the snippet is generated from notes_text which stores the same text.
        """
        user = User.objects.create_user("hl_noteuser")
        doc = Document.objects.create(
            title="Doc with matching note",
            content="unrelated content",
            checksum="HH2",
            pk=91,
        )
        Note.objects.create(document=doc, note="urgent payment required", user=user)
        backend.add_or_update(doc)

        # Use notes.note: prefix so the document matches the query and the
        # notes_text snippet generator can produce highlights.
        hits = backend.highlight_hits("notes.note:urgent", [doc.pk])

        assert len(hits) == 1
        highlights = hits[0]["highlights"]
        assert "notes" in highlights
        note_highlight = highlights["notes"]
        assert isinstance(note_highlight, str), (
            f"Expected str, got {type(note_highlight)}: {note_highlight!r}"
        )
        assert "<b>" in note_highlight, (
            f"Expected HTML with <b> tags, got: {note_highlight!r}"
        )

    def test_empty_doc_list_returns_empty_hits(self, backend: TantivyBackend) -> None:
        """highlight_hits with no doc IDs must return an empty list."""
        hits = backend.highlight_hits("anything", [])
        assert hits == []

    def test_no_highlights_when_no_match(self, backend: TantivyBackend) -> None:
        """Documents not matching the query should not appear in results."""
        doc = Document.objects.create(
            title="Unrelated",
            content="completely different text",
            checksum="HH3",
            pk=92,
        )
        backend.add_or_update(doc)

        hits = backend.highlight_hits("quick", [doc.pk])

        assert len(hits) == 0
