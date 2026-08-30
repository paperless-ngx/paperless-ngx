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
            "Names of topic labels describing what this document is about, "
            "e.g. 'Insurance', 'Car', 'Warranty'. When an available tag "
            "represents the same label, use its ID in tag_ids instead."
        ),
    )
    tag_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "IDs of available tags that clearly apply to this document. Only "
            "use IDs shown in the prompt; never invent one or choose a weak match."
        ),
    )
    correspondents: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "Names of people, institutions or companies this document is from "
            "or was sent to, not every party merely mentioned. When an "
            "available correspondent is the same entity, use its ID in "
            "correspondent_ids instead."
        ),
    )
    correspondent_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "IDs of available correspondents that clearly apply to this "
            "document. Only use IDs shown in the prompt; never invent one or "
            "choose a weak match."
        ),
    )
    document_types: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "Names describing what kind of document this is, e.g. 'Invoice', "
            "'Contract', 'Bank Statement', 'Letter'. Never use its subject or "
            "sender as a document type. When an available document type is the "
            "same kind, use its ID in document_type_ids instead."
        ),
    )
    document_type_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "IDs of available document types that clearly apply to this "
            "document. Only use IDs shown in the prompt; never invent one or "
            "choose a weak match."
        ),
    )
    storage_paths: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "Names of folder-style filing locations, e.g. "
            "'Finance/Invoices'. Leave empty unless a filing location is "
            "clearly implied - never put tags, document types or "
            "correspondents here. When an available storage path is the same "
            "location, use its ID in storage_path_ids instead."
        ),
    )
    storage_path_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "IDs of available storage paths that clearly apply to this "
            "document. Only use IDs shown in the prompt; never invent one or "
            "choose a weak match."
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
        "tag_ids",
        "correspondents",
        "correspondent_ids",
        "document_types",
        "document_type_ids",
        "storage_paths",
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
) -> ClassificationSuggestions:
    """Convert the flat, model-friendly response to the internal shape."""
    return ClassificationSuggestions(
        title=model.title,
        tags=TaxonomyChoiceDict(
            existing_ids=model.tag_ids,
            new_names=model.tags,
        ),
        correspondents=TaxonomyChoiceDict(
            existing_ids=model.correspondent_ids,
            new_names=model.correspondents,
        ),
        document_types=TaxonomyChoiceDict(
            existing_ids=model.document_type_ids,
            new_names=model.document_types,
        ),
        storage_paths=TaxonomyChoiceDict(
            existing_ids=model.storage_path_ids,
            new_names=model.storage_paths,
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
        tag_ids=suggestions["tags"]["existing_ids"],
        correspondents=suggestions["correspondents"]["new_names"],
        correspondent_ids=suggestions["correspondents"]["existing_ids"],
        document_types=suggestions["document_types"]["new_names"],
        document_type_ids=suggestions["document_types"]["existing_ids"],
        storage_paths=suggestions["storage_paths"]["new_names"],
        storage_path_ids=suggestions["storage_paths"]["existing_ids"],
        dates=suggestions["dates"],
    )
