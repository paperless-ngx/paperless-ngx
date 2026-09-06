from typing import Any

from documents.management.commands.base import PaperlessCommand
from documents.tasks import llmindex_index
from paperless_ai.indexing import llm_index_compact
from paperless_ai.indexing import llm_index_migrate


class Command(PaperlessCommand):
    help = "Manages the LLM-based vector index for Paperless."

    supports_progress_bar = True
    supports_multiprocessing = False

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument(
            "command",
            choices=["rebuild", "update", "compact", "migrate"],
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["command"] == "compact":
            llm_index_compact()
            return
        if options["command"] == "migrate":
            llm_index_migrate()
            return
        llmindex_index(
            rebuild=options["command"] == "rebuild",
            iter_wrapper=lambda docs: self.track(
                docs,
                description="Indexing documents...",
            ),
        )
