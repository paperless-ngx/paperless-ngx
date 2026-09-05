import datetime
from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
import pytest_mock
from django.test import override_settings

from documents.models import Document
from documents.search import TantivyBackend
from documents.tests.factories import DocumentFactory
from documents.tests.factories import TagFactory
from documents.tests.factories import UserFactory
from paperless.config import AIConfig
from paperless_ai.ai_classifier import TAXONOMY_CANDIDATE_TOP_K
from paperless_ai.ai_classifier import _fulltext_similar_documents
from paperless_ai.ai_classifier import build_localization_prompt
from paperless_ai.ai_classifier import build_prompt_with_rag
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_language_name
from paperless_ai.ai_classifier import get_taxonomy_context
from paperless_ai.taxonomy import SimilarDocument
from paperless_ai.taxonomy import TaxonomyCandidate
from paperless_ai.taxonomy import TaxonomyCandidates


@pytest.fixture
def mock_document():
    doc = MagicMock(spec=Document)
    doc.title = "Test Title"
    doc.filename = "test_file.pdf"
    doc.created = "2023-01-01"
    doc.added = "2023-01-02"
    doc.modified = "2023-01-03"

    tag1 = MagicMock()
    tag1.name = "Tag1"
    tag2 = MagicMock()
    tag2.name = "Tag2"
    doc.tags.all = MagicMock(return_value=[tag1, tag2])

    doc.document_type = MagicMock()
    doc.document_type.name = "Invoice"
    doc.correspondent = MagicMock()
    doc.correspondent.name = "Test Correspondent"
    doc.storage_path = None
    doc.archive_serial_number = "12345"
    doc.content = "This is the document content."

    cf1 = MagicMock(__str__=lambda x: "Value1")
    cf1.field = MagicMock()
    cf1.field.name = "Field1"
    cf1.value = "Value1"
    cf2 = MagicMock(__str__=lambda x: "Value2")
    cf2.field = MagicMock()
    cf2.field.name = "Field2"
    cf2.value = "Value2"
    doc.custom_fields.all = MagicMock(return_value=[cf1, cf2])

    return doc


NESTED_SUGGESTIONS = {
    "title": "Test Title",
    "tags": {"existing_ids": [], "new_names": ["test", "document"]},
    "correspondents": {"existing_ids": [], "new_names": ["John Doe"]},
    "document_types": {"existing_ids": [], "new_names": ["report"]},
    "storage_paths": {"existing_ids": [], "new_names": ["Reports"]},
    "dates": ["2023-01-01"],
}


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
def test_get_ai_document_classification_success(mock_run_llm_query, mock_document):
    """
    GIVEN:
        - An LLM backend configured without RAG
        - A classification call followed by a localization call
    WHEN:
        - get_ai_document_classification() is called with an output_language
    THEN:
        - The localized title/new_names are used
        - Correspondents are never localized, so the original suggestion survives
        - Dates are never localized
        - The classification prompt has no taxonomy title instruction and the
          localization prompt asks to rewrite only new_names/title
    """
    mock_run_llm_query.side_effect = [
        NESTED_SUGGESTIONS,
        {
            "title": "Testtitel",
            "tags": {"existing_ids": [], "new_names": ["Test", "Document"]},
            "correspondents": {"existing_ids": [], "new_names": ["Jane Doe"]},
            "document_types": {"existing_ids": [], "new_names": ["Bericht"]},
            "storage_paths": {"existing_ids": [], "new_names": ["Berichte"]},
            "dates": ["2024-01-01"],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Testtitel"
    assert result["tags"]["new_names"] == ["Test", "Document"]
    # Correspondents are never localized - the merge step doesn't touch them,
    # so the original (English) suggestion survives, same as before this change.
    assert result["correspondents"]["new_names"] == ["John Doe"]
    assert result["document_types"]["new_names"] == ["Bericht"]
    assert result["storage_paths"]["new_names"] == ["Berichte"]
    assert result["dates"] == ["2023-01-01"]
    classification_prompt = mock_run_llm_query.call_args_list[0].args[0]
    localization_prompt = mock_run_llm_query.call_args_list[1].args[0]
    assert "Write suggested titles" not in classification_prompt
    assert "Rewrite only the" in localization_prompt
    assert "Do not translate correspondents or dates" in localization_prompt


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
def test_get_ai_document_classification_keeps_originals_when_localization_empty(
    mock_run_llm_query,
    mock_document,
):
    """
    GIVEN:
        - A localization response whose fields are all empty
    WHEN:
        - get_ai_document_classification() is called with an output_language
    THEN:
        - The original (pre-localization) suggestions are kept for every field
    """
    mock_run_llm_query.side_effect = [
        NESTED_SUGGESTIONS,
        {
            "title": "",
            "tags": {"existing_ids": [], "new_names": []},
            "correspondents": {"existing_ids": [], "new_names": []},
            "document_types": {"existing_ids": [], "new_names": []},
            "storage_paths": {"existing_ids": [], "new_names": []},
            "dates": [],
        },
    ]

    result = get_ai_document_classification(mock_document, output_language="de-de")

    assert result["title"] == "Test Title"
    assert result["tags"]["new_names"] == ["test", "document"]
    assert result["correspondents"]["new_names"] == ["John Doe"]
    assert result["document_types"]["new_names"] == ["report"]
    assert result["storage_paths"]["new_names"] == ["Reports"]
    assert result["dates"] == ["2023-01-01"]


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
def test_get_ai_document_classification_failure(mock_run_llm_query, mock_document):
    """
    GIVEN:
        - The LLM client raises an exception
    WHEN:
        - get_ai_document_classification() is called
    THEN:
        - The exception propagates rather than being swallowed
    """
    mock_run_llm_query.side_effect = Exception("LLM query failed")

    with pytest.raises(Exception):
        get_ai_document_classification(mock_document)


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_with_rag")
@patch("paperless_ai.ai_classifier.build_taxonomy_candidates")
@patch("paperless_ai.ai_classifier.retrieve_similar_nodes")
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_EMBEDDING_MODEL="some_model",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_use_rag_if_configured(
    mock_retrieve,
    mock_build_candidates,
    mock_build_prompt_with_rag,
    mock_run_llm_query,
    mock_document,
):
    """
    GIVEN:
        - An LLM embedding backend is configured
    WHEN:
        - get_ai_document_classification() is called
    THEN:
        - The RAG-augmented prompt builder is used
        - Classification and candidate reconciliation happen in one LLM call
        - Only candidate IDs from the permission-filtered candidate set are allowed
    """
    mock_retrieve.return_value = []
    mock_build_candidates.return_value = TaxonomyCandidates(
        tags=[TaxonomyCandidate(id=12, name="Contractor", weight=1.0)],
        document_types=[],
        correspondents=[],
        storage_paths=[],
    )
    mock_build_prompt_with_rag.return_value = "Prompt with RAG"
    mock_run_llm_query.return_value = NESTED_SUGGESTIONS
    get_ai_document_classification(mock_document)
    mock_build_prompt_with_rag.assert_called_once()
    mock_run_llm_query.assert_called_once_with(
        "Prompt with RAG",
        allowed_candidate_ids={
            "tags": {12},
            "document_types": set(),
            "correspondents": set(),
            "storage_paths": set(),
        },
    )


@pytest.mark.django_db
@patch("paperless_ai.client.AIClient.run_llm_query")
@patch("paperless_ai.ai_classifier.build_prompt_with_rag")
@override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
def test_use_rag_prompt_even_without_embedding_backend(
    mock_build_prompt_with_rag,
    mock_run_llm_query,
    mock_document,
):
    """
    GIVEN:
        - No LLM embedding backend is configured
    WHEN:
        - get_ai_document_classification() is called
    THEN:
        - The RAG-context prompt builder is still used (fed by the full-text
          fallback's context/candidates instead of the vector store's)
    """
    mock_build_prompt_with_rag.return_value = "Prompt with RAG"
    mock_run_llm_query.return_value = NESTED_SUGGESTIONS
    get_ai_document_classification(mock_document)
    mock_build_prompt_with_rag.assert_called_once()


@pytest.mark.django_db
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_prompt_with_without_rag(mock_document):
    """
    GIVEN:
        - A document and an AIConfig
    WHEN:
        - build_prompt_without_rag(), build_prompt_with_rag(), and
          build_localization_prompt() are called
    THEN:
        - build_prompt_without_rag() has no similar-documents section
        - build_prompt_with_rag() includes the similar-documents context
        - build_localization_prompt() asks to rewrite only names/title and
          not to translate correspondents or dates
    """
    config = AIConfig()
    prompt = build_prompt_without_rag(mock_document, config)
    assert "Additional context from similar documents" not in prompt
    assert "for generated" not in prompt

    prompt = build_prompt_with_rag(
        mock_document,
        config,
        context="Context from similar documents",
    )
    assert "Additional context from similar documents" in prompt
    assert "Context from similar documents" in prompt

    prompt = build_localization_prompt(NESTED_SUGGESTIONS, output_language="de-de")
    assert "Rewrite only the" in prompt
    assert "Do not translate correspondents or dates" in prompt
    assert '"tag_ids":[]' in prompt


def test_get_language_name_falls_back_to_language_code():
    """
    GIVEN:
        - A language code not present in settings.LANGUAGES
    WHEN:
        - get_language_name() is called
    THEN:
        - The original language code is returned unchanged
    """
    assert get_language_name("zz-zz") == "zz-zz"


def test_build_localization_prompt_preserves_unicode_characters():
    """
    GIVEN:
        - Suggestions containing non-ASCII characters
    WHEN:
        - build_localization_prompt() is called
    THEN:
        - The unicode characters are preserved as-is rather than escaped
    """
    prompt = build_localization_prompt(
        {
            "title": "Gebührenbescheid",
            "tags": {"existing_ids": [], "new_names": []},
            "correspondents": {"existing_ids": [], "new_names": []},
            "document_types": {"existing_ids": [], "new_names": []},
            "storage_paths": {"existing_ids": [], "new_names": []},
            "dates": [],
        },
        output_language="de-de",
    )

    assert "Gebührenbescheid" in prompt
    assert "\\u00fc" not in prompt


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
def test_get_taxonomy_context_assembles_rag_text_and_candidates():
    """
    GIVEN:
        - A neighbour document with a tag, retrieved via retrieve_similar_nodes
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - The neighbour's tag appears in the taxonomy candidates
        - The neighbour's title/content appear in the RAG text context
    """
    tag = TagFactory.create(name="Bloodwork")
    neighbour = DocumentFactory.create(
        content="Content of neighbour document",
        title="Neighbour Title",
    )
    neighbour.tags.add(tag)
    document = DocumentFactory.create(content="Some content")
    fake_node = SimpleNamespace(
        metadata={"document_id": str(neighbour.pk)},
        score=0.8,
    )

    with patch(
        "paperless_ai.ai_classifier.retrieve_similar_nodes",
        return_value=[fake_node],
    ):
        candidates, context = get_taxonomy_context(document, user=None)

    assert candidates["tags"][0]["name"] == "Bloodwork"
    assert "TITLE: Neighbour Title" in context
    assert "Content of neighbour document" in context


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
def test_get_taxonomy_context_preserves_similarity_order_and_distinct_documents():
    """
    GIVEN:
        - Ranked nodes whose similarity order conflicts with Document's
          newest-created-first default ordering
        - Two chunks belonging to the most similar document
        - A stale node whose document no longer exists
    WHEN:
        - get_taxonomy_context() builds a two-document RAG context
    THEN:
        - The two most similar distinct documents are used in ranked order
        - The duplicate chunk does not consume a context slot
        - The missing document does not consume a context slot
    """
    most_similar = DocumentFactory.create(
        created=datetime.date(2020, 1, 1),
        content="Most similar content",
        title="Most Similar",
    )
    second_most_similar = DocumentFactory.create(
        created=datetime.date(2021, 1, 1),
        content="Second most similar content",
        title="Second Most Similar",
    )
    newest_but_least_similar = DocumentFactory.create(
        created=datetime.date(2026, 1, 1),
        content="Least similar content",
        title="Newest But Least Similar",
    )
    document = DocumentFactory.create(content="Some content")
    fake_nodes = [
        SimpleNamespace(
            metadata={"document_id": str(most_similar.pk)},
            score=0.9,
        ),
        SimpleNamespace(
            metadata={"document_id": str(most_similar.pk)},
            score=0.8,
        ),
        SimpleNamespace(
            metadata={"document_id": "999999999"},
            score=0.75,
        ),
        SimpleNamespace(
            metadata={"document_id": str(second_most_similar.pk)},
            score=0.7,
        ),
        SimpleNamespace(
            metadata={"document_id": str(newest_but_least_similar.pk)},
            score=0.6,
        ),
    ]

    with patch(
        "paperless_ai.ai_classifier.retrieve_similar_nodes",
        return_value=fake_nodes,
    ):
        _candidates, context = get_taxonomy_context(
            document,
            user=None,
            max_docs=2,
        )

    assert context == (
        "TITLE: Most Similar\nMost similar content\n\n"
        "TITLE: Second Most Similar\nSecond most similar content"
    )


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
def test_get_taxonomy_context_no_similar_docs():
    """
    GIVEN:
        - No similar documents are retrieved
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - An empty RAG context and empty taxonomy candidates are returned
    """
    document = DocumentFactory.create(content="Some content")

    with patch("paperless_ai.ai_classifier.retrieve_similar_nodes", return_value=[]):
        candidates, context = get_taxonomy_context(document, user=None)

    assert context == ""
    assert candidates == {
        "tags": [],
        "document_types": [],
        "correspondents": [],
        "storage_paths": [],
    }


@pytest.mark.django_db
def test_get_taxonomy_context_uses_fulltext_fallback_when_no_embedding_backend(
    mocker: pytest_mock.MockerFixture,
) -> None:
    """
    GIVEN:
        - No LLM embedding backend is configured (the default test settings)
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - _fulltext_similar_documents() is called with the document, the user
          and TAXONOMY_CANDIDATE_TOP_K
        - retrieve_similar_nodes() (the vector path) is never called
    """
    document = DocumentFactory.create(content="Some content")
    mock_fulltext = mocker.patch(
        "paperless_ai.ai_classifier._fulltext_similar_documents",
        return_value=[],
    )
    mock_retrieve = mocker.patch("paperless_ai.ai_classifier.retrieve_similar_nodes")

    get_taxonomy_context(document, user=None)

    mock_fulltext.assert_called_once_with(
        document,
        None,
        top_k=TAXONOMY_CANDIDATE_TOP_K,
    )
    mock_retrieve.assert_not_called()


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
def test_get_taxonomy_context_uses_vector_path_when_embedding_backend_configured(
    mocker: pytest_mock.MockerFixture,
) -> None:
    """
    GIVEN:
        - An LLM embedding backend is configured
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - retrieve_similar_nodes() (the vector path) is called
        - _fulltext_similar_documents() (the no-embedding-backend fallback)
          is never called
    """
    document = DocumentFactory.create(content="Some content")
    mock_retrieve = mocker.patch(
        "paperless_ai.ai_classifier.retrieve_similar_nodes",
        return_value=[],
    )
    mock_fulltext = mocker.patch(
        "paperless_ai.ai_classifier._fulltext_similar_documents",
    )

    get_taxonomy_context(document, user=None)

    mock_retrieve.assert_called_once()
    mock_fulltext.assert_not_called()


class TestGetTaxonomyContextVisibility:
    """get_taxonomy_context must not materialize every visible document id
    for a user who can already see the whole library: a superuser (like no
    user at all) gets document_ids=None (no restriction) straight through to
    retrieve_similar_nodes(), instead of a full-library IN filter that is
    wasteful at best and, past ~32,763 documents, a hard
    sqlite3.OperationalError at worst (SQLite's bound-parameter limit). Ports
    the coverage that used to live on get_context_for_document before this
    refactor folded it into get_taxonomy_context.
    """

    @pytest.mark.django_db
    @override_settings(LLM_EMBEDDING_BACKEND="huggingface")
    def test_skips_permission_lookup_for_superuser(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A superuser
        WHEN:
            - get_taxonomy_context() is called
        THEN:
            - Permission lookup is skipped and no document_ids restriction is
              passed to retrieve_similar_nodes()
        """
        document = DocumentFactory.create(content="Some content")
        mock_retrieve = mocker.patch(
            "paperless_ai.ai_classifier.retrieve_similar_nodes",
            return_value=[],
        )
        mock_permitted = mocker.patch(
            "paperless_ai.ai_classifier.permitted_object_ids",
        )
        user = UserFactory.create(is_superuser=True)

        get_taxonomy_context(document, user)

        mock_permitted.assert_not_called()
        assert mock_retrieve.call_args.kwargs["document_ids"] is None

    @pytest.mark.django_db
    @override_settings(LLM_EMBEDDING_BACKEND="huggingface")
    def test_skips_permission_lookup_when_no_user(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - No user is supplied
        WHEN:
            - get_taxonomy_context() is called
        THEN:
            - Permission lookup is skipped and no document_ids restriction is
              passed to retrieve_similar_nodes()
        """
        document = DocumentFactory.create(content="Some content")
        mock_retrieve = mocker.patch(
            "paperless_ai.ai_classifier.retrieve_similar_nodes",
            return_value=[],
        )
        mock_permitted = mocker.patch(
            "paperless_ai.ai_classifier.permitted_object_ids",
        )

        get_taxonomy_context(document, None)

        mock_permitted.assert_not_called()
        assert mock_retrieve.call_args.kwargs["document_ids"] is None

    @pytest.mark.django_db
    @override_settings(LLM_EMBEDDING_BACKEND="huggingface")
    def test_restricts_to_visible_documents_for_non_superuser(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A non-superuser
        WHEN:
            - get_taxonomy_context() is called
        THEN:
            - The user's permitted document ids are looked up and passed to
              retrieve_similar_nodes() as a restriction
        """
        document = DocumentFactory.create(content="Some content")
        mock_retrieve = mocker.patch(
            "paperless_ai.ai_classifier.retrieve_similar_nodes",
            return_value=[],
        )
        mock_permitted = mocker.patch(
            "paperless_ai.ai_classifier.permitted_object_ids",
            return_value=[1, 2, 3],
        )
        user = UserFactory.create(is_superuser=False)

        get_taxonomy_context(document, user)

        mock_permitted.assert_called_once_with(user, Document, "view_document")
        assert mock_retrieve.call_args.kwargs["document_ids"] == [1, 2, 3]


@pytest.mark.django_db
class TestFulltextSimilarDocuments:
    """_fulltext_similar_documents is the no-embedding-backend fallback: it
    asks the Tantivy full-text index for "More Like This" neighbours instead
    of the vector store, and synthesizes a rank-based weight since Tantivy's
    more_like_this_ids returns only an ordered id list, no scores.
    """

    @pytest.fixture
    def fulltext_backend(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> Generator[TantivyBackend, None, None]:
        """An in-memory Tantivy backend, wired up as the module-level
        singleton _fulltext_similar_documents resolves via get_backend()."""
        backend = TantivyBackend(path=None)
        backend.open()
        mocker.patch("documents.search.get_backend", return_value=backend)
        try:
            yield backend
        finally:
            backend.close()

    def test_ranks_by_rank_based_weight_descending(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A source document and two similar documents indexed in Tantivy
        WHEN:
            - _fulltext_similar_documents() is called
        THEN:
            - Each result's weight reflects its rank (first result weighted
              higher than the second), not a raw similarity score
        """
        source = DocumentFactory.create(content="quarterly financial report details")
        first = DocumentFactory.create(content="quarterly financial report details")
        second = DocumentFactory.create(content="financial report")
        for doc in (source, first, second):
            fulltext_backend.add_or_update(doc)

        result = _fulltext_similar_documents(source, user=None, top_k=5)

        assert len(result) == 2
        weight_by_id = {s["document_id"]: s["weight"] for s in result}
        assert weight_by_id[first.pk] > weight_by_id[second.pk]

    def test_excludes_source_document(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A source document indexed in Tantivy with no other documents
        WHEN:
            - _fulltext_similar_documents() is called
        THEN:
            - An empty list is returned - the source document is never its
              own similar document
        """
        source = DocumentFactory.create(content="unique unrelated content")
        fulltext_backend.add_or_update(source)

        result = _fulltext_similar_documents(source, user=None, top_k=5)

        assert result == []

    def test_empty_index_returns_empty_list(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A document that has never been indexed (fresh/empty Tantivy index)
        WHEN:
            - _fulltext_similar_documents() is called
        THEN:
            - An empty list is returned rather than raising
        """
        source = DocumentFactory.create(content="never indexed")

        result = _fulltext_similar_documents(source, user=None, top_k=5)

        assert result == []

    def test_respects_top_k_limit(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A source document and four similar documents indexed
        WHEN:
            - _fulltext_similar_documents() is called with top_k=2
        THEN:
            - At most 2 results are returned
        """
        source = DocumentFactory.create(content="shared overlapping keyword text")
        fulltext_backend.add_or_update(source)
        for _ in range(4):
            fulltext_backend.add_or_update(
                DocumentFactory.create(content="shared overlapping keyword text"),
            )

        result = _fulltext_similar_documents(source, user=None, top_k=2)

        assert len(result) == 2

    def test_result_shape_is_similar_document(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A source document and one similar document indexed
        WHEN:
            - _fulltext_similar_documents() is called
        THEN:
            - Each result is a SimilarDocument (document_id + weight only)
        """
        source = DocumentFactory.create(content="shared content phrase")
        other = DocumentFactory.create(content="shared content phrase")
        fulltext_backend.add_or_update(source)
        fulltext_backend.add_or_update(other)

        result = _fulltext_similar_documents(source, user=None, top_k=5)

        # rank 0 (the only/best result) with top_k=5 -> weight = top_k - rank = 5.0,
        # per the "first result gets top_k, the last gets 1" formula.
        assert result == [SimilarDocument(document_id=other.pk, weight=5.0)]

    def test_superuser_sees_other_users_documents(
        self,
        fulltext_backend: TantivyBackend,
    ) -> None:
        """
        GIVEN:
            - A source document owned by one user and a similar document
              owned by a different user, with no sharing between them
        WHEN:
            - _fulltext_similar_documents() is called with a superuser
        THEN:
            - The other user's document is still returned as a similar
              document - a superuser must not be narrowed by the backend's
              owner-based permission filter
        """
        owner = UserFactory.create()
        other_owner = UserFactory.create()
        superuser = UserFactory.create(is_superuser=True)
        source = DocumentFactory.create(
            content="shared content phrase",
            owner=owner,
        )
        other = DocumentFactory.create(
            content="shared content phrase",
            owner=other_owner,
        )
        fulltext_backend.add_or_update(source)
        fulltext_backend.add_or_update(other)

        result = _fulltext_similar_documents(source, user=superuser, top_k=5)

        assert [s["document_id"] for s in result] == [other.pk]


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
@patch("paperless_ai.ai_classifier.retrieve_similar_nodes")
def test_get_taxonomy_context_retrieval_failure_degrades_to_no_hints(mock_retrieve):
    """
    GIVEN:
        - retrieve_similar_nodes() raises an exception (e.g. vector store outage)
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - Empty taxonomy candidates and an empty RAG context are returned
          instead of propagating the exception
    """
    document = DocumentFactory.create(content="Some content")
    mock_retrieve.side_effect = RuntimeError("vector store unavailable")

    candidates, rag_context = get_taxonomy_context(document, user=None)

    assert candidates == {
        "tags": [],
        "document_types": [],
        "correspondents": [],
        "storage_paths": [],
    }
    assert rag_context == ""


@pytest.mark.django_db
@override_settings(LLM_EMBEDDING_BACKEND="huggingface")
@patch("paperless_ai.ai_classifier.build_taxonomy_candidates")
@patch("paperless_ai.ai_classifier.retrieve_similar_nodes")
def test_get_taxonomy_context_candidate_building_failure_degrades_to_no_hints(
    mock_retrieve,
    mock_build_candidates,
):
    """
    GIVEN:
        - retrieve_similar_nodes() succeeds but build_taxonomy_candidates()
          raises (e.g. a DB or permission-backend failure)
    WHEN:
        - get_taxonomy_context() is called
    THEN:
        - Empty taxonomy candidates and an empty RAG context are returned
          instead of propagating the exception - the error boundary covers
          everything derived from the retrieval, not just the retrieval call
          itself
    """
    document = DocumentFactory.create(content="Some content")
    mock_retrieve.return_value = []
    mock_build_candidates.side_effect = RuntimeError("permission backend unavailable")

    candidates, rag_context = get_taxonomy_context(document, user=None)

    assert candidates == {
        "tags": [],
        "document_types": [],
        "correspondents": [],
        "storage_paths": [],
    }
    assert rag_context == ""


@pytest.mark.django_db
def test_build_prompt_without_rag_includes_taxonomy_block():
    """
    GIVEN:
        - Non-empty taxonomy candidates
    WHEN:
        - build_prompt_without_rag() is called with candidates
    THEN:
        - The candidate and single-call reconciliation instructions appear
        - Complete name suggestions remain mandatory
        - Assigned metadata is not included
    """
    document = DocumentFactory.create(content="Some content")
    config = AIConfig()
    candidates = {
        "tags": [{"id": 12, "name": "Bloodwork", "weight": 1.0}],
        "document_types": [],
        "correspondents": [],
        "storage_paths": [],
    }
    prompt = build_prompt_without_rag(
        document,
        config,
        candidates=candidates,
    )

    assert '"id": 12' in prompt
    assert "Always include every suggested name" in prompt
    assert "matched_*" in prompt
    assert "corresponding *_ids" in prompt
    assert "Candidates must not create, replace, or suppress suggestions" in prompt
    assert "already assigned" not in prompt


@pytest.mark.django_db
def test_build_prompt_without_rag_identical_when_no_candidates():
    """
    GIVEN:
        - Empty taxonomy candidates
    WHEN:
        - build_prompt_without_rag() is called with those empty values, and
          separately with no candidates at all
    THEN:
        - Both prompts are identical
        - Neither carries candidate reconciliation instructions
    """
    document = DocumentFactory.create(content="Some content")
    config = AIConfig()
    empty_candidates = {
        "tags": [],
        "document_types": [],
        "correspondents": [],
        "storage_paths": [],
    }
    with_empty_hints = build_prompt_without_rag(
        document,
        config,
        candidates=empty_candidates,
    )
    with_no_hints = build_prompt_without_rag(document, config)

    assert with_empty_hints == with_no_hints
    assert "Available " not in with_no_hints
    assert "matched_*" not in with_no_hints


@pytest.mark.django_db
def test_build_prompt_without_rag_never_includes_assigned_metadata():
    """
    GIVEN:
        - A document with assigned taxonomy metadata
    WHEN:
        - build_prompt_without_rag() is called
    THEN:
        - Assigned metadata is absent so it cannot anchor classification
    """
    document = DocumentFactory.create(content="Some content")
    config = AIConfig()
    assigned_tag = TagFactory.create(name="Bloodwork")
    document.tags.add(assigned_tag)

    prompt = build_prompt_without_rag(document, config)

    assert "Bloodwork" not in prompt
    assert "already assigned" not in prompt


@pytest.mark.django_db
@patch("paperless_ai.ai_classifier.AIClient")
@patch("paperless_ai.ai_classifier.build_taxonomy_candidates")
@patch("paperless_ai.ai_classifier.retrieve_similar_nodes")
@override_settings(
    LLM_EMBEDDING_BACKEND="huggingface",
    LLM_BACKEND="ollama",
    LLM_MODEL="some_model",
)
def test_get_ai_document_classification_localizes_only_new_names(
    mock_retrieve,
    mock_build_candidates,
    mock_client_cls,
):
    """
    GIVEN:
        - A classification response with a resolved existing tag id that
          was actually offered as a candidate
        - A localization response that echoes back a different existing_ids value
    WHEN:
        - get_ai_document_classification() is called with an output_language
    THEN:
        - The localized new_names are used
        - The ORIGINAL existing_ids are kept, never the localized response's
          existing_ids - localization must never corrupt an exact taxonomy match
    """
    document = DocumentFactory.create(content="Some content")
    mock_retrieve.return_value = []
    mock_build_candidates.return_value = TaxonomyCandidates(
        tags=[TaxonomyCandidate(id=12, name="Contractor", weight=1.0)],
        document_types=[],
        correspondents=[],
        storage_paths=[],
    )
    mock_client = mock_client_cls.return_value
    mock_client.run_llm_query.side_effect = [
        {
            "title": "Invoice",
            "tags": {"existing_ids": [12], "new_names": ["Contractor Work"]},
            "correspondents": {"existing_ids": [], "new_names": []},
            "document_types": {"existing_ids": [], "new_names": []},
            "storage_paths": {"existing_ids": [], "new_names": []},
            "dates": [],
        },
        {
            # The model's own localized-response existing_ids (999) must be
            # discarded - the merge always keeps the ORIGINAL resolved id.
            "title": "Rechnung",
            "tags": {"existing_ids": [999], "new_names": ["Auftragsarbeit"]},
            "correspondents": {"existing_ids": [], "new_names": []},
            "document_types": {"existing_ids": [], "new_names": []},
            "storage_paths": {"existing_ids": [], "new_names": []},
            "dates": [],
        },
    ]

    result = get_ai_document_classification(document, output_language="de-de")

    localization_prompt = mock_client.run_llm_query.call_args_list[1].args[0]
    assert "Contractor Work" in localization_prompt
    assert result["tags"]["existing_ids"] == [12]  # untouched by localization
    assert result["tags"]["new_names"] == ["Auftragsarbeit"]
