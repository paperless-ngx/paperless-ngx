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


_HINT_INSTRUCTION = (
    "Prefer existing names from these lists verbatim. Only propose a new value "
    "if none of the existing names fits."
)


def format_hints_for_prompt(hints: TaxonomyHints) -> str:
    """Render non-empty hint categories as labelled blocks plus one instruction.

    Returns "" when every category is empty, so callers can treat the result
    the same as no hints at all.
    """
    # Literal-key access keeps this TypedDict-safe for mypy; the order here is
    # the order the blocks appear in the prompt.
    labelled_values: list[tuple[str, list[str]]] = [
        ("Available tags", hints["tags"]),
        ("Available document types", hints["document_types"]),
        ("Available correspondents", hints["correspondents"]),
        ("Available storage paths", hints["storage_paths"]),
    ]
    blocks: list[str] = []
    for label, values in labelled_values:
        if values:
            listing = "\n".join(f"- {value}" for value in values)
            blocks.append(f"{label}:\n{listing}")

    if not blocks:
        return ""

    return "\n\n".join([*blocks, _HINT_INSTRUCTION])
