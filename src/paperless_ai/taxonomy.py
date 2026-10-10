import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict

from django.contrib.auth.models import User
from django.db.models import Model
from django.db.models import Prefetch

from documents.classifier import load_classifier
from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import restrict_queryset_to_visible
from paperless_ai.prompts.context import TaxonomyBlockPromptContext
from paperless_ai.prompts.render import render_prompt

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

logger = logging.getLogger("paperless_ai.taxonomy")


MAX_TAG_CANDIDATES: Final = 10
MAX_SINGLE_VALUE_CANDIDATES: Final = 5


class TaxonomyCandidate(TypedDict):
    id: int
    name: str
    weight: float


class SimilarDocument(TypedDict):
    document_id: int
    weight: float


class TaxonomyCandidates(TypedDict):
    tags: list[TaxonomyCandidate]
    document_types: list[TaxonomyCandidate]
    correspondents: list[TaxonomyCandidate]
    storage_paths: list[TaxonomyCandidate]


def empty_taxonomy_candidates() -> TaxonomyCandidates:
    """No candidates in any category - what callers use when retrieval was
    skipped or failed."""
    return TaxonomyCandidates(
        tags=[],
        document_types=[],
        correspondents=[],
        storage_paths=[],
    )


def _node_document_weights(nodes: list["NodeWithScore"]) -> list[SimilarDocument]:
    """Sum each node's similarity score into its document_id (a document can
    appear via multiple chunks/nodes) and return one SimilarDocument per
    distinct document_id."""
    weights: dict[int, float] = defaultdict(float)
    for node in nodes:
        document_id = node.metadata.get("document_id")
        if document_id is None:  # pragma: no cover
            # Every node the indexing pipeline builds always sets
            # document_id; this guards a malformed/partial vec0 row that
            # shouldn't occur given the current schema.
            continue
        try:
            weights[int(document_id)] += float(node.score or 0.0)
        except (TypeError, ValueError):  # pragma: no cover
            continue
    return sorted(
        (
            SimilarDocument(document_id=document_id, weight=weight)
            for document_id, weight in weights.items()
        ),
        key=lambda similar: similar["weight"],
        reverse=True,
    )


def _visible_ranked_candidates(
    weighted_ids: dict[int, float],
    model: type[Model],
    perm: str,
    user: User | None,
    limit: int,
) -> list[TaxonomyCandidate]:
    """Drop anything ``user`` may not see, resolve the survivors' names, and
    return them ranked by descending weight and capped at ``limit``.

    The visibility check restricts the query to just this small
    weighted_ids set rather than materializing every id `user` may see
    installation-wide - resolving names and checking visibility is one
    query either way, so this never pays for scanning the whole taxonomy.
    """
    if not weighted_ids:
        return []
    visible_queryset = restrict_queryset_to_visible(
        model.objects.filter(pk__in=weighted_ids),
        user,
        perm,
    )
    id_to_name = dict(visible_queryset.values_list("id", "name"))
    candidates = [
        TaxonomyCandidate(id=object_id, name=id_to_name[object_id], weight=weight)
        for object_id, weight in weighted_ids.items()
        if object_id in id_to_name
    ]
    candidates.sort(key=lambda c: c["weight"], reverse=True)
    return candidates[:limit]


def build_taxonomy_candidates(
    similar_documents: list[SimilarDocument],
    user: User | None,
) -> TaxonomyCandidates:
    """Resolve each similar document's id to a live Document, read its
    *current* tags/type/correspondent/storage_path via the ORM (never any
    possibly-stale names an adapter's source might have cached), weight each
    distinct taxonomy object by aggregate similarity weight, permission-filter
    against what ``user`` can see, and return each category ranked by weight
    and capped. ``similar_documents`` may come from either the vector-RAG
    adapter or the full-text fallback adapter - both produce this same shape.
    """
    if not similar_documents:
        return empty_taxonomy_candidates()

    # Both adapters guarantee at most one SimilarDocument per document_id, so
    # this never silently drops a duplicate's weight.
    document_weights: dict[int, float] = {
        s["document_id"]: s["weight"] for s in similar_documents
    }

    # Only .tags.all() needs prefetching (a reverse M2M, one extra query for
    # the whole batch). document_type/correspondent/storage_path are read
    # below via their *_id columns (neighbour.document_type_id, etc.), which
    # are already present on each Document row with no join - so this
    # deliberately does NOT select_related() those three; it would fetch the
    # full related row just to reach an id already sitting on `neighbour`.
    neighbours = Document.objects.filter(
        pk__in=document_weights.keys(),
    ).prefetch_related(
        Prefetch("tags", queryset=Tag.objects.filter(is_inbox_tag=False)),
    )

    tag_weights: dict[int, float] = defaultdict(float)
    document_type_weights: dict[int, float] = defaultdict(float)
    correspondent_weights: dict[int, float] = defaultdict(float)
    storage_path_weights: dict[int, float] = defaultdict(float)

    for neighbour in neighbours:
        weight = document_weights[neighbour.pk]
        for tag in neighbour.tags.all():
            tag_weights[tag.pk] += weight
        if neighbour.document_type_id:
            document_type_weights[neighbour.document_type_id] += weight
        if neighbour.correspondent_id:
            correspondent_weights[neighbour.correspondent_id] += weight
        if neighbour.storage_path_id:
            storage_path_weights[neighbour.storage_path_id] += weight

    return TaxonomyCandidates(
        tags=_visible_ranked_candidates(
            tag_weights,
            Tag,
            "view_tag",
            user,
            MAX_TAG_CANDIDATES,
        ),
        document_types=_visible_ranked_candidates(
            document_type_weights,
            DocumentType,
            "view_documenttype",
            user,
            MAX_SINGLE_VALUE_CANDIDATES,
        ),
        correspondents=_visible_ranked_candidates(
            correspondent_weights,
            Correspondent,
            "view_correspondent",
            user,
            MAX_SINGLE_VALUE_CANDIDATES,
        ),
        storage_paths=_visible_ranked_candidates(
            storage_path_weights,
            StoragePath,
            "view_storagepath",
            user,
            MAX_SINGLE_VALUE_CANDIDATES,
        ),
    )


def merge_matched_candidates(
    candidates: TaxonomyCandidates,
    document: Document,
    user: User | None,
) -> TaxonomyCandidates:
    """Add what the built-in matching would assign to ``document`` - matching
    rules that fire plus the trained classifier's predictions - on top of the
    neighbour-derived ``candidates``.

    Neighbour voting only knows the taxonomy of the few most similar
    documents, so an existing tag none of them happen to carry is invisible
    to the model and gets reinvented under a near-duplicate name. The
    classifier has seen every document that carries it, and a matching rule
    is the user spelling out the assignment. Both run through the same
    ``match_*`` functions the non-LLM suggestions endpoint uses, so they are
    already permission-filtered for ``user`` (falling back to the document
    owner when there is none) and tolerate a missing classifier model.

    Matched objects are boosted above every neighbour weight in their
    category so they always survive the cap and rank first; neighbour order
    is kept below them. Weight is an internal ranking detail - the model
    never sees it, only the resulting id/name list.
    """
    try:
        classifier = load_classifier()
        matched_tags = [
            tag
            for tag in match_tags(document, classifier, user)
            if not tag.is_inbox_tag
        ]
        matched = {
            "tags": (matched_tags, Tag, "view_tag", MAX_TAG_CANDIDATES),
            "document_types": (
                match_document_types(document, classifier, user),
                DocumentType,
                "view_documenttype",
                MAX_SINGLE_VALUE_CANDIDATES,
            ),
            "correspondents": (
                match_correspondents(document, classifier, user),
                Correspondent,
                "view_correspondent",
                MAX_SINGLE_VALUE_CANDIDATES,
            ),
            "storage_paths": (
                match_storage_paths(document, classifier, user),
                StoragePath,
                "view_storagepath",
                MAX_SINGLE_VALUE_CANDIDATES,
            ),
        }
    except Exception:
        logger.exception(
            "Failed to match document %s against matching rules and classifier; "
            "continuing with neighbour-derived taxonomy candidates only.",
            document.pk,
        )
        return candidates

    merged = dict(candidates)
    for category, (objects, model, perm, limit) in matched.items():
        if not objects:
            continue
        weights: dict[int, float] = {c["id"]: c["weight"] for c in candidates[category]}
        # A matched object starts from its neighbour weight, or from 0 when
        # no neighbour carries it. Neighbour weights can be negative
        # (similarity is 1 - cosine distance) or well above 1 (aggregated
        # over many neighbours, or rank-based in the full-text fallback), so
        # lift by the spread of {neighbour weights, 0} plus a margin: the
        # lowest possible starting point then lands above the highest
        # unmatched weight.
        lowest = min([*weights.values(), 0.0])
        highest = max([*weights.values(), 0.0])
        boost = highest - lowest + 1.0
        for obj in objects:
            weights[obj.pk] = weights.get(obj.pk, 0.0) + boost
        merged[category] = _visible_ranked_candidates(
            weights,
            model,
            perm,
            user,
            limit,
        )
    return TaxonomyCandidates(**merged)


def format_taxonomy_for_prompt(
    candidates: TaxonomyCandidates,
) -> str:
    """Render ranked candidates as a labelled prompt block.

    Candidate names are untrusted, user-controlled data, so they are
    JSON-serialized (id/name only - weight is an internal ranking detail)
    rather than bullet-rendered, matching the untrusted-data handling already
    used for document content elsewhere in this module. Returns "" when there
    are no candidates, so callers can treat the result the same as no hints at all.
    """
    candidate_payload = {
        key: [{"id": c["id"], "name": c["name"]} for c in values]
        for key, values in candidates.items()
        if values
    }

    return render_prompt(
        TaxonomyBlockPromptContext(
            candidate_payload_json=(
                json.dumps(candidate_payload, ensure_ascii=False)
                if candidate_payload
                else ""
            ),
        ),
    )
