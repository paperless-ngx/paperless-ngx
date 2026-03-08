from typing import Any

from documents.management.commands.base import PaperlessCommand
from documents.tasks import llmindex_index


class Command(PaperlessCommand):
    help = "Manages the LLM-based vector index for Paperless."

    def add_arguments(self, parser: Any) -> None:
        super().add_arguments(parser)
        parser.add_argument("command", choices=["rebuild", "update"])

    def handle(self, *args: Any, **options: Any) -> None:
        llmindex_index(
            rebuild=options["command"] == "rebuild",
            scheduled=False,
            iter_wrapper=lambda docs: self.track(
                docs,
                description="Indexing documents...",
            ),
        )
