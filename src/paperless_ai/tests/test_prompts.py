import pytest

from paperless_ai.prompts.context import AssignedBlockPromptContext
from paperless_ai.prompts.context import ChatQaPromptContext
from paperless_ai.prompts.context import ChatRefinePromptContext
from paperless_ai.prompts.context import ClassificationPromptContext
from paperless_ai.prompts.context import LocalizationPromptContext
from paperless_ai.prompts.context import RagContextPromptContext
from paperless_ai.prompts.context import TaxonomyBlockPromptContext
from paperless_ai.prompts.render import PromptName
from paperless_ai.prompts.render import render_prompt


class TestRenderPrompt:
    def test_renders_assigned_block_with_all_fields_set(self) -> None:
        """
        GIVEN:
            - An AssignedBlockPromptContext with every field populated
        WHEN:
            - render_prompt() is called
        THEN:
            - The rendered text contains the labeled header and each value
        """
        context = AssignedBlockPromptContext(
            tags=["Bloodwork", "Urgent"],
            document_type="Invoice",
            correspondent="Acme Corp",
            storage_path="/invoices",
        )

        result = render_prompt(context)

        assert "already assigned" in result
        assert "Tags: Bloodwork, Urgent" in result
        assert "Document Type: Invoice" in result
        assert "Correspondent: Acme Corp" in result
        assert "Storage Path: /invoices" in result

    def test_renders_assigned_block_defaults_for_empty_fields(self) -> None:
        """
        GIVEN:
            - An AssignedBlockPromptContext with no values set
        WHEN:
            - render_prompt() is called
        THEN:
            - Each field falls back to its "(none)"/"(not set)" placeholder
        """
        context = AssignedBlockPromptContext(
            tags=[],
            document_type=None,
            correspondent=None,
            storage_path=None,
        )

        result = render_prompt(context)

        assert "Tags: (none)" in result
        assert "Document Type: (not set)" in result
        assert "Correspondent: (not set)" in result
        assert "Storage Path: (not set)" in result

    def test_renders_taxonomy_block_empty_when_both_fields_empty(self) -> None:
        """
        GIVEN:
            - A TaxonomyBlockPromptContext with both fields empty
        WHEN:
            - render_prompt() is called
        THEN:
            - The result is an empty string
        """
        context = TaxonomyBlockPromptContext(
            assigned_block="",
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
        assigned_block="",
        candidate_payload_json="",
    ),
    PromptName.ASSIGNED_BLOCK: AssignedBlockPromptContext(
        tags=[],
        document_type=None,
        correspondent=None,
        storage_path=None,
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
