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
    if limit is None or not isinstance(value, (list, str)):
        return value
    return value[:limit]


class TaxonomyChoice(BaseModel):
    """One taxonomy category's suggestions: IDs the model matched to a
    candidate it was shown in the prompt, plus names for values it believes
    are genuinely new. existing_ids are never localized - only new_names is.

    Pydantic enforces this shape on whatever the LLM returns; the rest of the
    pipeline passes the `.model_dump()`-ed plain dict around, typed as
    TaxonomyChoiceDict below.
    """

    existing_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
    )
    new_names: list[str] = Field(default_factory=list, max_length=MAX_NEW_NAMES)

    @field_validator("existing_ids", "new_names", mode="before")
    @classmethod
    def _truncate(cls, value: Any, info: ValidationInfo) -> Any:
        return _truncate_to_field_limit(value, cls.model_fields[info.field_name])


class DocumentClassifierSchema(BaseModel):
    """Schema for document classification suggestions."""

    title: str = Field(max_length=MAX_TITLE_LENGTH)
    tags: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    correspondents: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    document_types: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    storage_paths: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    dates: list[str] = Field(default_factory=list, max_length=MAX_DATES)

    @field_validator("title", "dates", mode="before")
    @classmethod
    def _truncate(cls, value: Any, info: ValidationInfo) -> Any:
        return _truncate_to_field_limit(value, cls.model_fields[info.field_name])


class TaxonomyChoiceDict(TypedDict):
    """Plain-dict counterpart of TaxonomyChoice - what
    TaxonomyChoice.model_dump() actually produces, typed for callers that
    work with the dumped dict rather than the pydantic instance."""

    existing_ids: list[int]
    new_names: list[str]


class ClassificationSuggestions(TypedDict):
    """Plain-dict counterpart of DocumentClassifierSchema.model_dump() -
    the shape threaded through parse_ai_response, build_localization_prompt,
    get_ai_document_classification, and the ai_suggestions view."""

    title: str
    tags: TaxonomyChoiceDict
    correspondents: TaxonomyChoiceDict
    document_types: TaxonomyChoiceDict
    storage_paths: TaxonomyChoiceDict
    dates: list[str]
