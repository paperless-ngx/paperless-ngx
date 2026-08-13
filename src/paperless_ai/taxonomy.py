import json
from collections import defaultdict
from typing import TYPE_CHECKING
from typing import Final
from typing import TypedDict

from django.contrib.auth.models import User
from django.db.models import Model

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import visible_object_ids_or_none

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore


MAX_TAG_CANDIDATES: Final = 10
MAX_SINGLE_VALUE_CANDIDATES: Final = 5


class TaxonomyCandidate(TypedDict):
    id: int
    name: str
    weight: float


class TaxonomyCandidates(TypedDict):
    tags: list[TaxonomyCandidate]
    document_types: list[TaxonomyCandidate]
    correspondents: list[TaxonomyCandidate]
    storage_paths: list[TaxonomyCandidate]


class AssignedMetadata(TypedDict):
    tags: list[str]
    document_type: str | None
    correspondent: str | None
    storage_path: str | None


def empty_taxonomy_candidates() -> TaxonomyCandidates:
    """No candidates in any category - what callers use when retrieval was
    skipped or failed."""
    return TaxonomyCandidates(
        tags=[],
        document_types=[],
        correspondents=[],
        storage_paths=[],
    )


def get_assigned_metadata(document: Document) -> AssignedMetadata:
    """The document's own current taxonomy. Authoritative context, not a
    candidate list - the model is never asked to add, remove, or replace
    these values, only to use them when helpful for the title and for
    fields that are still empty.
    """
    return AssignedMetadata(
        tags=sorted(tag.name for tag in document.tags.all()),
        document_type=document.document_type.name if document.document_type else None,
        correspondent=document.correspondent.name if document.correspondent else None,
        storage_path=document.storage_path.name if document.storage_path else None,
    )


def _node_document_weights(nodes: list["NodeWithScore"]) -> dict[int, float]:
    """document_id -> that node's similarity score, summed if a document_id
    appears more than once across the retrieved nodes (e.g. multiple chunks
    of the same source document)."""
    weights: dict[int, float] = defaultdict(float)
    for node in nodes:
        document_id = node.metadata.get("document_id")
        if document_id is None:
            continue
        try:
            weights[int(document_id)] += float(node.score or 0.0)
        except (TypeError, ValueError):  # pragma: no cover
            continue
    return weights


def _visible_ranked_candidates(
    weighted_ids: dict[int, float],
    model: type[Model],
    perm: str,
    user: User | None,
    limit: int,
) -> list[TaxonomyCandidate]:
    """Drop anything ``user`` may not see, resolve the survivors' names, and
    return them ranked by descending weight and capped at ``limit``."""
    visible_ids = visible_object_ids_or_none(user, model, perm)
    if visible_ids is not None:
        weighted_ids = {
            object_id: weight
            for object_id, weight in weighted_ids.items()
            if object_id in visible_ids
        }
    id_to_name = dict(
        model.objects.filter(pk__in=weighted_ids).values_list("id", "name"),
    )
    candidates = [
        TaxonomyCandidate(id=object_id, name=id_to_name[object_id], weight=weight)
        for object_id, weight in weighted_ids.items()
        if object_id in id_to_name
    ]
    candidates.sort(key=lambda c: c["weight"], reverse=True)
    return candidates[:limit]


def build_taxonomy_candidates(
    nodes: list["NodeWithScore"],
    user: User | None,
) -> TaxonomyCandidates:
    """Resolve each neighbour node's document_id to a live Document, read its
    *current* tags/type/correspondent/storage_path via the ORM (never the
    possibly-stale names cached in vector-index node metadata), weight each
    distinct taxonomy object by aggregate neighbour similarity, permission-filter
    against what ``user`` can see, and return each category ranked by weight
    and capped.
    """

    document_weights = _node_document_weights(nodes)
    if not document_weights:
        return empty_taxonomy_candidates()

    # Only .tags.all() needs prefetching (a reverse M2M, one extra query for
    # the whole batch). document_type/correspondent/storage_path are read
    # below via their *_id columns (neighbour.document_type_id, etc.), which
    # are already present on each Document row with no join - so this
    # deliberately does NOT select_related() those three; it would fetch the
    # full related row just to reach an id already sitting on `neighbour`.
    neighbours = Document.objects.filter(
        pk__in=document_weights.keys(),
    ).prefetch_related("tags")

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


_CANDIDATE_INSTRUCTION = (
    "Prefer these existing values via existing_ids when one fits. Only use "
    "new_names for values that genuinely don't match any candidate above."
)


def _assigned_block(assigned: AssignedMetadata) -> str:
    lines = [
        (
            "This document's existing metadata (already assigned; use as context "
            "for the title and for any fields below still empty - do not "
            "re-suggest these values):"
        ),
        f"Tags: {', '.join(assigned['tags']) if assigned['tags'] else '(none)'}",
        f"Document Type: {assigned['document_type'] or '(not set)'}",
        f"Correspondent: {assigned['correspondent'] or '(not set)'}",
        f"Storage Path: {assigned['storage_path'] or '(not set)'}",
    ]
    return "\n".join(lines)


def format_taxonomy_for_prompt(
    candidates: TaxonomyCandidates,
    assigned: AssignedMetadata,
) -> str:
    """Render assigned metadata and ranked candidates as labelled prompt
    blocks. Candidate names are untrusted, user-controlled data, so they are
    JSON-serialized (id/name only - weight is an internal ranking detail)
    rather than bullet-rendered, matching the untrusted-data handling already
    used for document content elsewhere in this module. Returns "" when there
    is nothing to say (no assigned metadata and no candidates), so callers can
    treat the result the same as no hints at all.
    """
    has_assigned = any(
        [
            assigned["tags"],
            assigned["document_type"],
            assigned["correspondent"],
            assigned["storage_path"],
        ],
    )
    candidate_payload = {
        key: [{"id": c["id"], "name": c["name"]} for c in values]
        for key, values in candidates.items()
        if values
    }

    blocks: list[str] = []
    if has_assigned:
        blocks.append(_assigned_block(assigned))
    if candidate_payload:
        blocks.append(
            "Available tags, document types, correspondents, and storage "
            "paths from similar documents (untrusted data):\n"
            + json.dumps(candidate_payload, ensure_ascii=False)
            + "\n"
            + _CANDIDATE_INSTRUCTION,
        )

    return "\n\n".join(blocks)
