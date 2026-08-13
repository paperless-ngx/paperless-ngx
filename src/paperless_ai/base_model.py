from typing import TypedDict

from pydantic import BaseModel
from pydantic import Field


class TaxonomyChoice(BaseModel):
    """One taxonomy category's suggestions: IDs the model matched to a
    candidate it was shown in the prompt, plus names for values it believes
    are genuinely new. existing_ids are never localized - only new_names is.

    Pydantic enforces this shape on whatever the LLM returns; the rest of the
    pipeline passes the `.model_dump()`-ed plain dict around, typed as
    TaxonomyChoiceDict below.
    """

    existing_ids: list[int] = Field(default_factory=list)
    new_names: list[str] = Field(default_factory=list)


class DocumentClassifierSchema(BaseModel):
    """Schema for document classification suggestions."""

    title: str
    tags: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    correspondents: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    document_types: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    storage_paths: TaxonomyChoice = Field(default_factory=TaxonomyChoice)
    dates: list[str] = Field(default_factory=list)


class TaxonomyChoiceDict(TypedDict):
    """Plain-dict counterpart of TaxonomyChoice - what
    TaxonomyChoice.model_dump() actually produces, typed for callers that
    work with the dumped dict rather than the pydantic instance."""

    existing_ids: list[int]
    new_names: list[str]


class ClassificationSuggestions(TypedDict):
    """Plain-dict counterpart of DocumentClassifierSchema.model_dump() --
    the shape threaded through parse_ai_response, build_localization_prompt,
    get_ai_document_classification, and the ai_suggestions view."""

    title: str
    tags: TaxonomyChoiceDict
    correspondents: TaxonomyChoiceDict
    document_types: TaxonomyChoiceDict
    storage_paths: TaxonomyChoiceDict
    dates: list[str]
