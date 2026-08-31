from typing import Any
from typing import Final
from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationInfo
from pydantic import field_validator
from pydantic.fields import FieldInfo

# taxonomy.py MAX_TAG_CANDIDATES = 10, prompt is "up to 3 relevant dates"
MAX_EXISTING_IDS: Final = 10
MAX_NEW_NAMES: Final = 8
MAX_SINGLE_VALUE_NAMES: Final = 4
MAX_DATES: Final = 3
# Matches documents.models.Document.title's CharField(max_length=128).
MAX_TITLE_LENGTH: Final = 128


def _truncate_to_field_limit(value: Any, field: FieldInfo) -> Any:
    """
    Clip down to its it's declared maximum. Run as a `mode="before"` validator.
    """
    limit = next(
        (m.max_length for m in field.metadata if hasattr(m, "max_length")),
        None,
    )
    return (
        value
        if (limit is None or not isinstance(value, (list, str)))
        else value[:limit]
    )


# This model is serialized into the schema handed to the LLM, so its docstring
# and field descriptions are instructions for the model. Keep implementation
# details in code comments instead.
class DocumentClassifierSchema(BaseModel):
    """Classification suggestions for a single document."""

    title: str = Field(
        max_length=MAX_TITLE_LENGTH,
        description=(
            "A short, descriptive title for this document, at most "
            f"{MAX_TITLE_LENGTH} characters."
        ),
    )
    tags: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "All topic labels you would suggest from the document itself, e.g. "
            "'Insurance', 'Car', 'Warranty'. Always include every suggested "
            "name here, even when it matches an available tag."
        ),
    )
    matched_tags: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "Names copied exactly from tags that mean the same thing as an "
            "available tag. Align each name by position with tag_ids."
        ),
    )
    tag_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "Available tag IDs matching matched_tags, in the same order. "
            "Only use IDs shown in the prompt."
        ),
    )
    correspondents: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Who this document is from or was sent to, not every party merely "
            "mentioned. A document has a single correspondent, so give at most "
            f"{MAX_SINGLE_VALUE_NAMES}, best first, and prefer one name over "
            "several names for the same organisation. Always include every "
            "suggested name here, even when it matches an available "
            "correspondent."
        ),
    )
    matched_correspondents: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Names copied exactly from correspondents that identify the same "
            "entity as an available correspondent. Align each name by position "
            "with correspondent_ids."
        ),
    )
    correspondent_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Available correspondent IDs matching matched_correspondents, in "
            "the same order. Only use IDs shown in the prompt."
        ),
    )
    document_types: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "What kind of document this is, e.g. 'Invoice', 'Contract', 'Bank "
            "Statement', 'Letter'. Never use its subject or sender as a "
            "document type. A document has a single type, so give at most "
            f"{MAX_SINGLE_VALUE_NAMES}, best first. Always include every "
            "suggested name here, even when it matches an available document "
            "type."
        ),
    )
    matched_document_types: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Names copied exactly from document_types that mean the same thing "
            "as an available document type. Align each name by position with "
            "document_type_ids."
        ),
    )
    document_type_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Available document type IDs matching matched_document_types, in "
            "the same order. Only use IDs shown in the prompt."
        ),
    )
    storage_paths: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Folder-style filing location, e.g. 'Finance/Invoices'. Leave "
            "empty unless a filing location is clearly implied - never put "
            "tags, document types or correspondents here. A document has a "
            f"single storage path, so give at most {MAX_SINGLE_VALUE_NAMES}, "
            "best first. Always include every suggested name here, even when "
            "it matches an available storage path."
        ),
    )
    matched_storage_paths: list[str] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Names copied exactly from storage_paths that mean the same filing "
            "location as an available storage path. Align each name by position "
            "with storage_path_ids."
        ),
    )
    storage_path_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_SINGLE_VALUE_NAMES,
        description=(
            "Available storage path IDs matching matched_storage_paths, in the "
            "same order. Only use IDs shown in the prompt."
        ),
    )
    dates: list[str] = Field(
        default_factory=list,
        max_length=MAX_DATES,
        description=(
            f"Up to {MAX_DATES} dates relevant to this document, each "
            "formatted YYYY-MM-DD. The most important is the date the "
            "document was issued."
        ),
    )

    @field_validator(
        "title",
        "tags",
        "matched_tags",
        "tag_ids",
        "correspondents",
        "matched_correspondents",
        "correspondent_ids",
        "document_types",
        "matched_document_types",
        "document_type_ids",
        "storage_paths",
        "matched_storage_paths",
        "storage_path_ids",
        "dates",
        mode="before",
    )
    @classmethod
    def _truncate(cls, value: Any, info: ValidationInfo) -> Any:
        return _truncate_to_field_limit(value, cls.model_fields[info.field_name])


class TaxonomyChoiceDict(TypedDict):
    """Internal representation of names and existing IDs for one taxonomy."""

    existing_ids: list[int]
    new_names: list[str]


class ClassificationSuggestions(TypedDict):
    """Internal shape used after the flat LLM response is validated."""

    title: str
    tags: TaxonomyChoiceDict
    correspondents: TaxonomyChoiceDict
    document_types: TaxonomyChoiceDict
    storage_paths: TaxonomyChoiceDict
    dates: list[str]


def model_to_classification_suggestions(
    model: DocumentClassifierSchema,
    allowed_candidate_ids: dict[str, set[int]] | None = None,
) -> ClassificationSuggestions:
    """Validate optional candidate mappings and convert to the internal shape.

    A mapping is accepted only when its name is copied from the model's own
    complete suggestion list and its ID was actually shown for that category.
    Invalid or unpaired mappings leave the original name untouched.
    """
    allowed_candidate_ids = allowed_candidate_ids or {}

    def _choice(
        names: list[str],
        matched_names: list[str],
        ids: list[int],
        category: str,
    ) -> TaxonomyChoiceDict:
        remaining_names = [name for name in names if name.strip()]
        existing_ids: list[int] = []
        allowed_ids = allowed_candidate_ids.get(category, set())
        for name, object_id in zip(matched_names, ids, strict=False):
            if (
                not name.strip()
                or name not in remaining_names
                or object_id not in allowed_ids
                or object_id in existing_ids
            ):
                continue
            remaining_names.remove(name)
            existing_ids.append(object_id)
        return TaxonomyChoiceDict(
            existing_ids=existing_ids,
            new_names=remaining_names,
        )

    return ClassificationSuggestions(
        title=model.title,
        tags=_choice(
            model.tags,
            model.matched_tags,
            model.tag_ids,
            "tags",
        ),
        correspondents=_choice(
            model.correspondents,
            model.matched_correspondents,
            model.correspondent_ids,
            "correspondents",
        ),
        document_types=_choice(
            model.document_types,
            model.matched_document_types,
            model.document_type_ids,
            "document_types",
        ),
        storage_paths=_choice(
            model.storage_paths,
            model.matched_storage_paths,
            model.storage_path_ids,
            "storage_paths",
        ),
        dates=model.dates,
    )


def classification_suggestions_to_model(
    suggestions: ClassificationSuggestions,
) -> DocumentClassifierSchema:
    """Convert internal suggestions to the flat shape used for localization."""
    return DocumentClassifierSchema(
        title=suggestions["title"],
        tags=suggestions["tags"]["new_names"],
        matched_tags=[],
        tag_ids=[],
        correspondents=suggestions["correspondents"]["new_names"],
        matched_correspondents=[],
        correspondent_ids=[],
        document_types=suggestions["document_types"]["new_names"],
        matched_document_types=[],
        document_type_ids=[],
        storage_paths=suggestions["storage_paths"]["new_names"],
        matched_storage_paths=[],
        storage_path_ids=[],
        dates=suggestions["dates"],
    )
