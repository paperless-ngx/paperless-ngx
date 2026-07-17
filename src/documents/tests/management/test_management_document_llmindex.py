from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.management import call_command

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

_COMPACT = "documents.management.commands.document_llmindex.llm_index_compact"
_INDEX = "documents.management.commands.document_llmindex.llmindex_index"


class TestDocumentLlmindexCommand:
    def test_compact_calls_llm_index_compact(self, mocker: MockerFixture) -> None:
        mock_compact = mocker.patch(_COMPACT)
        call_command("document_llmindex", "compact")
        mock_compact.assert_called_once_with()

    def test_rebuild_calls_llmindex_index_with_rebuild_true(
        self,
        mocker: MockerFixture,
    ) -> None:
        mock_index = mocker.patch(_INDEX)
        call_command("document_llmindex", "rebuild")
        mock_index.assert_called_once()
        assert mock_index.call_args.kwargs["rebuild"] is True

    def test_update_calls_llmindex_index_with_rebuild_false(
        self,
        mocker: MockerFixture,
    ) -> None:
        mock_index = mocker.patch(_INDEX)
        call_command("document_llmindex", "update")
        mock_index.assert_called_once()
        assert mock_index.call_args.kwargs["rebuild"] is False
