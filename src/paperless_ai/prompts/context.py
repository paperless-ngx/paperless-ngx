from dataclasses import dataclass
from typing import ClassVar

from paperless_ai.prompts.render import PromptContext
from paperless_ai.prompts.render import PromptName


@dataclass(frozen=True, slots=True)
class TaxonomyBlockPromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.TAXONOMY_BLOCK
    candidate_payload_json: str


@dataclass(frozen=True, slots=True)
class ClassificationPromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.CLASSIFICATION
    filename: str
    content: str
    taxonomy_block: str
    has_candidates: bool


@dataclass(frozen=True, slots=True)
class RagContextPromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.CLASSIFICATION_RAG_CONTEXT
    base_prompt: str
    context: str


@dataclass(frozen=True, slots=True)
class LocalizationPromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.LOCALIZATION
    language_name: str
    suggestions_json: str


@dataclass(frozen=True, slots=True)
class ChatQaPromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.CHAT_QA
    output_language: str | None


@dataclass(frozen=True, slots=True)
class ChatRefinePromptContext(PromptContext):
    template_name: ClassVar[PromptName] = PromptName.CHAT_REFINE
    output_language: str | None
