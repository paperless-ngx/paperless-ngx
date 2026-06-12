import logging
from typing import TYPE_CHECKING
from typing import TypedDict

if TYPE_CHECKING:
    from llama_index.core.schema import NodeWithScore

logger = logging.getLogger("paperless_ai.taxonomy")


class TaxonomyHints(TypedDict):
    tags: list[str]
    document_types: list[str]
    correspondents: list[str]
    storage_paths: list[str]


def build_taxonomy_hints_from_nodes(
    nodes: list["NodeWithScore"],
) -> TaxonomyHints:
    """Collect the unique, sorted taxonomy names carried on retrieved nodes.

    Reads ``tags`` (a list), ``document_type``, ``correspondent``, and
    ``storage_path`` from each node's metadata. Empty / ``None`` values and
    missing keys are skipped. The result is naturally bounded by the retrieval
    ``top_k``, so no cap is applied.
    """
    tags: set[str] = set()
    document_types: set[str] = set()
    correspondents: set[str] = set()
    storage_paths: set[str] = set()

    for node in nodes:
        metadata = node.metadata or {}

        for tag in metadata.get("tags") or []:
            if tag:
                tags.add(tag)

        document_type = metadata.get("document_type")
        if document_type:
            document_types.add(document_type)

        correspondent = metadata.get("correspondent")
        if correspondent:
            correspondents.add(correspondent)

        storage_path = metadata.get("storage_path")
        if storage_path:
            storage_paths.add(storage_path)

    return TaxonomyHints(
        tags=sorted(tags),
        document_types=sorted(document_types),
        correspondents=sorted(correspondents),
        storage_paths=sorted(storage_paths),
    )
