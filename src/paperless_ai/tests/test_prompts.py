import pytest

from paperless_ai.prompts.context import ChatQaPromptContext
from paperless_ai.prompts.context import ChatRefinePromptContext
from paperless_ai.prompts.context import ClassificationPromptContext
from paperless_ai.prompts.context import LocalizationPromptContext
from paperless_ai.prompts.context import RagContextPromptContext
from paperless_ai.prompts.context import TaxonomyBlockPromptContext
from paperless_ai.prompts.render import PromptName
from paperless_ai.prompts.render import render_prompt


class TestRenderPrompt:
    def test_renders_taxonomy_block_empty_when_candidates_empty(self) -> None:
        """
        GIVEN:
            - A TaxonomyBlockPromptContext with no candidate payload
        WHEN:
            - render_prompt() is called
        THEN:
            - The result is an empty string
        """
        context = TaxonomyBlockPromptContext(
            candidate_payload_json="",
        )

        result = render_prompt(context)

        assert result == ""


_MINIMAL_CONTEXTS = {
    PromptName.CLASSIFICATION: ClassificationPromptContext(
        filename="file.pdf",
        content="content",
        taxonomy_block="",
        has_candidates=False,
    ),
    PromptName.CLASSIFICATION_RAG_CONTEXT: RagContextPromptContext(
        base_prompt="base",
        context="context",
    ),
    PromptName.LOCALIZATION: LocalizationPromptContext(
        language_name="German",
        suggestions_json="{}",
    ),
    PromptName.TAXONOMY_BLOCK: TaxonomyBlockPromptContext(
        candidate_payload_json="",
    ),
    PromptName.CHAT_QA: ChatQaPromptContext(output_language=None),
    PromptName.CHAT_REFINE: ChatRefinePromptContext(output_language=None),
}


class TestEveryPromptNameHasATemplate:
    @pytest.mark.parametrize("prompt_name", list(PromptName))
    def test_render_prompt_resolves_every_prompt_name(
        self,
        prompt_name: PromptName,
    ) -> None:
        """
        GIVEN:
            - A minimal, valid context instance for each PromptName
        WHEN:
            - render_prompt() is called
        THEN:
            - It resolves a real packaged .j2 file and returns a string,
              rather than raising TemplateNotFound
        """
        context = _MINIMAL_CONTEXTS.get(prompt_name)
        assert context is not None, f"No minimal context defined for {prompt_name}"

        result = render_prompt(context)

        assert isinstance(result, str)
