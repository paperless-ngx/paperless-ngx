import logging

from django.conf import settings
from django.contrib.auth.models import User

from documents.models import Document
from documents.permissions import permitted_object_ids
from documents.permissions import restrict_queryset_to_visible
from documents.permissions import user_is_unrestricted
from paperless.config import AIConfig
from paperless_ai.base_model import ClassificationSuggestions
from paperless_ai.base_model import TaxonomyChoiceDict
from paperless_ai.base_model import classification_suggestions_to_model
from paperless_ai.client import AIClient
from paperless_ai.db import db_connection_released
from paperless_ai.indexing import retrieve_similar_nodes
from paperless_ai.indexing import truncate_content
from paperless_ai.prompts.context import ClassificationPromptContext
from paperless_ai.prompts.context import LocalizationPromptContext
from paperless_ai.prompts.context import RagContextPromptContext
from paperless_ai.prompts.render import render_prompt
from paperless_ai.taxonomy import SimilarDocument
from paperless_ai.taxonomy import TaxonomyCandidates
from paperless_ai.taxonomy import _node_document_weights
from paperless_ai.taxonomy import build_taxonomy_candidates
from paperless_ai.taxonomy import empty_taxonomy_candidates
from paperless_ai.taxonomy import format_taxonomy_for_prompt

logger = logging.getLogger("paperless_ai.rag_classifier")

# Neighbours retrieved for taxonomy-candidate weighting, decoupled from
# get_taxonomy_context's max_docs (which caps how many of those same
# neighbours get their text spliced into the RAG context block). A wider
# pool of weighted neighbours gives build_taxonomy_candidates() more signal
# for which tags/correspondents/etc. actually cluster around this document,
# while the ranked candidate lists it returns stay capped by
# taxonomy.MAX_TAG_CANDIDATES / MAX_SINGLE_VALUE_CANDIDATES regardless of
# how many neighbours went in - so raising this does not by itself grow the
# prompt.
TAXONOMY_CANDIDATE_TOP_K = 15


def _fulltext_similar_documents(
    document: Document,
    user: User | None,
    top_k: int,
) -> list[SimilarDocument]:
    """Rank-based fallback when no embedding backend is configured. Uses
    Tantivy's "More Like This" (term-overlap similarity) instead of vector
    similarity - cruder, but far better than no candidates at all.
    more_like_this_ids returns only a ranked ID list, no scores, so weight is
    synthesized from rank (descending from top_k) rather than claiming a
    similarity magnitude that doesn't exist. An unrestricted user (none, or an
    active superuser - see user_is_unrestricted) is normalized to ``None``
    before calling, since the backend's permission filter has no superuser
    short-circuit of its own. Results are re-checked with
    restrict_queryset_to_visible() since Tantivy's indexed permission fields
    lag the DB via async reindexing.
    """
    from documents.search import get_backend

    unrestricted = user_is_unrestricted(user)
    search_user = None if unrestricted else user
    backend = get_backend()
    similar_ids = backend.more_like_this_ids(
        document.pk,
        user=search_user,
        limit=top_k,
    )
    if not unrestricted:
        allowed_ids = set(
            restrict_queryset_to_visible(
                Document.objects.filter(pk__in=similar_ids),
                user,
                "view_document",
            ).values_list("pk", flat=True),
        )
        similar_ids = [doc_id for doc_id in similar_ids if doc_id in allowed_ids]
    return [
        SimilarDocument(document_id=doc_id, weight=float(top_k - rank))
        for rank, doc_id in enumerate(similar_ids)
    ]


def get_language_name(language_code: str) -> str:
    normalized_language_code = language_code.lower()
    for code, name in settings.LANGUAGES:
        if code.lower() == normalized_language_code:
            return str(name)
    return language_code


def get_llm_output_language(ai_config: AIConfig, user: User | None) -> str | None:
    """
    Language to localize LLM output into: the configured language, falling back
    to the user's own UI language when unset.
    """
    output_language = ai_config.llm_output_language
    if (
        not output_language
        and user is not None
        and hasattr(user, "ui_settings")
        and isinstance(user.ui_settings.settings, dict)
    ):
        output_language = user.ui_settings.settings.get("language")
    return output_language


def build_prompt_without_rag(
    document: Document,
    config: AIConfig,
    candidates: TaxonomyCandidates | None = None,
) -> str:
    filename = document.filename or ""
    content = truncate_content(
        document.content[:4000] or "",
        chunk_size=config.llm_embedding_chunk_size,
        context_size=config.llm_context_size,
    )

    taxonomy_block = (
        format_taxonomy_for_prompt(candidates) if candidates is not None else ""
    )
    has_candidates = candidates is not None and any(candidates.values())

    return render_prompt(
        ClassificationPromptContext(
            filename=filename,
            content=content,
            taxonomy_block=taxonomy_block,
            has_candidates=has_candidates,
        ),
    )


def build_prompt_with_rag(
    document: Document,
    config: AIConfig,
    candidates: TaxonomyCandidates | None = None,
    context: str = "",
) -> str:
    base_prompt = build_prompt_without_rag(
        document,
        config,
        candidates=candidates,
    )
    truncated_context = truncate_content(
        context,
        chunk_size=config.llm_embedding_chunk_size,
        context_size=config.llm_context_size,
    )

    return render_prompt(
        RagContextPromptContext(
            base_prompt=base_prompt,
            context=truncated_context,
        ),
    )


def build_localization_prompt(
    suggestions: ClassificationSuggestions,
    output_language: str,
) -> str:
    """Render internal suggestions in the same flat shape the model returns.
    Only the name fields and title are used from the localized response; the
    merge step always keeps the original ID fields.
    """
    language_name = get_language_name(output_language)
    model_suggestions = classification_suggestions_to_model(suggestions)
    return render_prompt(
        LocalizationPromptContext(
            language_name=language_name,
            suggestions_json=model_suggestions.model_dump_json(),
        ),
    )


def get_taxonomy_context(
    document: Document,
    user: User | None = None,
    max_docs: int = 5,
) -> tuple[TaxonomyCandidates, str]:
    """One retrieval feeds both taxonomy candidates and RAG text context. Uses
    vector similarity when an embedding backend is configured, otherwise
    falls back to Tantivy full-text "More Like This" similarity - see
    _fulltext_similar_documents. On any retrieval failure, degrades to empty
    candidates/context rather than propagating the exception - neither a
    vector-store outage nor a search-index issue should block classification,
    only its context-assisted enrichment.
    """
    ai_config = AIConfig()
    try:
        if ai_config.llm_embedding_backend:
            # None means "no restriction" to retrieve_similar_nodes. A superuser
            # (like no user at all) can see every document, so skip materializing
            # every visible pk into a Python list and passing it through as an IN
            # filter: for a large library that is a wasted quadratic scan in the
            # vector store at best, and past ~32,763 documents a hard
            # sqlite3.OperationalError (SQLite's bound-parameter limit) at worst.
            # permitted_object_ids() has its own superuser shortcut that would
            # return every Document's id anyway, so this changes nothing about
            # which documents are considered -- only how we get there.
            visible_document_ids = (
                None
                if user is None or user.is_superuser
                else list(permitted_object_ids(user, Document, "view_document"))
            )
            nodes = retrieve_similar_nodes(
                document,
                top_k=TAXONOMY_CANDIDATE_TOP_K,
                document_ids=visible_document_ids,
            )
            similar_documents = _node_document_weights(nodes)
        else:
            # See _fulltext_similar_documents: it applies its own permission
            # filter via `user`, so no visible-document-id list is needed here.
            similar_documents = _fulltext_similar_documents(
                document,
                user,
                top_k=TAXONOMY_CANDIDATE_TOP_K,
            )

        candidates = build_taxonomy_candidates(similar_documents, user)

        # similar_documents is already ordered by descending weight; don't lose it.
        similar_document_ids = [s["document_id"] for s in similar_documents]
        similar_documents_by_id = Document.objects.in_bulk(similar_document_ids)
        similar_docs = [
            similar_documents_by_id[document_id]
            for document_id in similar_document_ids
            if document_id in similar_documents_by_id
        ][:max_docs]
        context_blocks = []
        for similar in similar_docs:
            text = similar.content[:1000] or ""
            title = similar.title or similar.filename or "Untitled"
            context_blocks.append(f"TITLE: {title}\n{text}")
    except Exception:
        logger.exception(
            "Failed to retrieve similar-document context for document %s; "
            "continuing without taxonomy candidates or similar-document context.",
            document.pk,
        )
        return empty_taxonomy_candidates(), ""

    return candidates, "\n\n".join(context_blocks)


def parse_ai_response(raw: dict) -> ClassificationSuggestions:
    """``raw`` is AIClient.run_llm_query()'s validated internal-shape result.
    This gives the rest of the module a named, typed boundary instead of
    passing the client's bare dict straight through everywhere.
    """

    def _choice(value: dict | None) -> TaxonomyChoiceDict:
        value = value or {}
        return TaxonomyChoiceDict(
            existing_ids=value.get("existing_ids", []),
            new_names=value.get("new_names", []),
        )

    return ClassificationSuggestions(
        title=raw.get("title", ""),
        tags=_choice(raw.get("tags")),
        correspondents=_choice(raw.get("correspondents")),
        document_types=_choice(raw.get("document_types")),
        storage_paths=_choice(raw.get("storage_paths")),
        dates=raw.get("dates", []),
    )


def _candidate_id_allowlist(
    candidates: TaxonomyCandidates,
) -> dict[str, set[int]]:
    """Candidate IDs grouped by category for validating model mappings."""
    return {
        "tags": {candidate["id"] for candidate in candidates["tags"]},
        "document_types": {
            candidate["id"] for candidate in candidates["document_types"]
        },
        "correspondents": {
            candidate["id"] for candidate in candidates["correspondents"]
        },
        "storage_paths": {candidate["id"] for candidate in candidates["storage_paths"]},
    }


def get_ai_document_classification(
    document: Document,
    user: User | None = None,
    output_language: str | None = None,
) -> ClassificationSuggestions:
    ai_config = AIConfig()

    candidates, context = get_taxonomy_context(document, user)
    prompt = build_prompt_with_rag(
        document,
        ai_config,
        candidates=candidates,
        context=context,
    )

    client = AIClient()
    # Hand the pooled DB connection back while the (slow) LLM query runs so it
    # is not pinned for the call's duration; see paperless_ai.db and #12976.
    with db_connection_released():
        result = client.run_llm_query(
            prompt,
            allowed_candidate_ids=_candidate_id_allowlist(candidates),
        )
        suggestions = parse_ai_response(result)
        if output_language:
            localized = client.run_llm_query(
                build_localization_prompt(suggestions, output_language),
            )
            localized_suggestions = parse_ai_response(localized)

            def _localized_choice(field: str) -> TaxonomyChoiceDict:
                # existing_ids always come from the ORIGINAL suggestions -
                # never from localized_suggestions, whatever the model echoed
                # back there. This is the concrete fix for the bug this
                # feature exists to close: localization must never be able to
                # corrupt an exact taxonomy match.
                return TaxonomyChoiceDict(
                    existing_ids=suggestions[field]["existing_ids"],
                    new_names=localized_suggestions[field]["new_names"]
                    or suggestions[field]["new_names"],
                )

            suggestions = ClassificationSuggestions(
                title=localized_suggestions["title"] or suggestions["title"],
                tags=_localized_choice("tags"),
                correspondents=suggestions["correspondents"],  # never localized
                document_types=_localized_choice("document_types"),
                storage_paths=_localized_choice("storage_paths"),
                dates=suggestions["dates"],
            )
    return suggestions
