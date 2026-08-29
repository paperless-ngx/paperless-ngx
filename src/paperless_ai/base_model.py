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


# Docstrings and field descriptions on both models below are serialized into
# the schema handed to the LLM, so write them for the model. Code comments
# should go here only.
class TaxonomyChoice(BaseModel):
    """One field's suggestions: existing values to reuse, plus new ones to create."""

    existing_ids: list[int] = Field(
        default_factory=list,
        max_length=MAX_EXISTING_IDS,
        description=(
            "IDs from the candidate list shown in the prompt that clearly "
            "represent values you would suggest for this field. Never invent "
            "an ID, select a weak match merely because it exists, or use an "
            "ID when no candidates are shown."
        ),
    )
    new_names: list[str] = Field(
        default_factory=list,
        max_length=MAX_NEW_NAMES,
        description=(
            "Names for clearly supported values that no shown candidate "
            "represents. When a candidate represents the same value, use its "
            "ID instead so an existing value is not duplicated under a new name."
        ),
    )

    @field_validator("existing_ids", "new_names", mode="before")
    @classmethod
    def _truncate(cls, value: Any, info: ValidationInfo) -> Any:
        return _truncate_to_field_limit(value, cls.model_fields[info.field_name])


class DocumentClassifierSchema(BaseModel):
    """Classification suggestions for a single document."""

    title: str = Field(
        max_length=MAX_TITLE_LENGTH,
        description=(
            "A short, descriptive title for this document, at most "
            f"{MAX_TITLE_LENGTH} characters."
        ),
    )
    tags: TaxonomyChoice = Field(
        default_factory=TaxonomyChoice,
        description=(
            "Topic labels describing what this document is about. A document "
            "may have several, e.g. 'Insurance', 'Car', 'Warranty'."
        ),
    )
    correspondents: TaxonomyChoice = Field(
        default_factory=TaxonomyChoice,
        description=(
            "The person, institution or company this document originates "
            "from, or was sent to. Not every party merely mentioned in the "
            "text, and not the subject of the document."
        ),
    )
    document_types: TaxonomyChoice = Field(
        default_factory=TaxonomyChoice,
        description=(
            "What kind of document this is, e.g. 'Invoice', 'Contract', "
            "'Bank Statement', 'Letter'. Never its subject matter and never "
            "who sent it."
        ),
    )
    storage_paths: TaxonomyChoice = Field(
        default_factory=TaxonomyChoice,
        description=(
            "A folder-style filing location for this document, e.g. "
            "'Finance/Invoices'. Leave empty unless a filing location is "
            "clearly implied - never put tags, document types or "
            "correspondents here."
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

    @field_validator("title", "dates", mode="before")
    @classmethod
    def _truncate(cls, value: Any, info: ValidationInfo) -> Any:
        return _truncate_to_field_limit(value, cls.model_fields[info.field_name])

    @classmethod
    def model_json_schema(cls, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Inline TaxonomyChoice for backends that reject JSON Schema refs."""
        schema = super().model_json_schema(*args, **kwargs)
        taxonomy_choice = schema.pop("$defs")["TaxonomyChoice"]
        for field in ("tags", "correspondents", "document_types", "storage_paths"):
            # Pydantic emits a field's description as a sibling of its $ref;
            # those keys must survive and win over the shared definition.
            siblings = {
                key: value
                for key, value in schema["properties"][field].items()
                if key != "$ref"
            }
            schema["properties"][field] = taxonomy_choice | siblings
        return schema


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
