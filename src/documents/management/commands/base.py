"""
Base command class for Paperless-ngx management commands.

Provides automatic progress bar and multiprocessing support with minimal boilerplate.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from collections.abc import Sized
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import TypeVar

from django import db
from django.core.management import CommandError
from django.db.models import QuerySet
from django_rich.management import RichCommand
from rich.console import Console
from rich.progress import BarColumn
from rich.progress import MofNCompleteColumn
from rich.progress import Progress
from rich.progress import SpinnerColumn
from rich.progress import TextColumn
from rich.progress import TimeElapsedColumn
from rich.progress import TimeRemainingColumn

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Generator
    from collections.abc import Iterable
    from collections.abc import Sequence

    from django.core.management import CommandParser

T = TypeVar("T")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class ProcessResult(Generic[T, R]):
    """
    Result of processing a single item in parallel.

    Attributes:
        item: The input item that was processed.
        result: The return value from the processing function, or None if an error occurred.
        error: The exception if processing failed, or None on success.
    """

    item: T
    result: R | None
    error: BaseException | None

    @property
    def success(self) -> bool:
        """Return True if the item was processed successfully."""
        return self.error is None


class PaperlessCommand(RichCommand):
    """
    Base command class with automatic progress bar and multiprocessing support.

    Features are opt-in via class attributes:
        supports_progress_bar: Adds --no-progress-bar argument (default: True)
        supports_multiprocessing: Adds --processes argument (default: False)

    Example usage:

        class Command(PaperlessCommand):
            help = "Process all documents"

            def handle(self, *args, **options):
                documents = Document.objects.all()
                for doc in self.track(documents, description="Processing..."):
                    process_document(doc)

        class Command(PaperlessCommand):
            help = "Regenerate thumbnails"
            supports_multiprocessing = True

            def handle(self, *args, **options):
                ids = list(Document.objects.values_list("id", flat=True))
                for result in self.process_parallel(process_doc, ids):
                    if result.error:
                        self.console.print(f"[red]Failed: {result.error}[/red]")
    """

    supports_progress_bar: ClassVar[bool] = True
    supports_multiprocessing: ClassVar[bool] = False

    # Instance attributes set by execute() before handle() runs
    no_progress_bar: bool
    process_count: int

    def add_arguments(self, parser: CommandParser) -> None:
        """Add arguments based on supported features."""
        super().add_arguments(parser)

        if self.supports_progress_bar:
            parser.add_argument(
                "--no-progress-bar",
                default=False,
                action="store_true",
                help="Disable the progress bar",
            )

        if self.supports_multiprocessing:
            default_processes = max(1, (os.cpu_count() or 1) // 4)
            parser.add_argument(
                "--processes",
                default=default_processes,
                type=int,
                help=f"Number of processes to use (default: {default_processes})",
            )

    def execute(self, *args: Any, **options: Any) -> str | None:
        """
        Set up instance state before handle() is called.

        This is called by Django's command infrastructure after argument parsing
        but before handle(). We use it to set instance attributes from options.
        """
        # Set progress bar state
        if self.supports_progress_bar:
            self.no_progress_bar = options.get("no_progress_bar", False)
        else:
            self.no_progress_bar = True

        # Set multiprocessing state
        if self.supports_multiprocessing:
            self.process_count = options.get("processes", 1)
            if self.process_count < 1:
                raise CommandError("--processes must be at least 1")
        else:
            self.process_count = 1

        return super().execute(*args, **options)

    def _create_progress(self, description: str) -> Progress:
        """
        Create a configured Progress instance.

        Progress output is directed to stderr to match the convention that
        progress bars are transient UI feedback, not command output. This
        mirrors tqdm's default behavior and prevents progress bar rendering
        from interfering with stdout-based assertions in tests or piped
        command output.

        Args:
            description: Text to display alongside the progress bar.

        Returns:
            A Progress instance configured with appropriate columns.
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=Console(stderr=True),
            transient=False,
        )

    def _get_iterable_length(self, iterable: Iterable[object]) -> int | None:
        """
        Attempt to determine the length of an iterable without consuming it.

        Tries .count() first (for Django querysets - executes SELECT COUNT(*)),
        then falls back to len() for sequences.

        Args:
            iterable: The iterable to measure.

        Returns:
            The length if determinable, None otherwise.
        """
        if isinstance(iterable, QuerySet):
            return iterable.count()

        if isinstance(iterable, Sized):
            return len(iterable)

        return None

    def track(
        self,
        iterable: Iterable[T],
        *,
        description: str = "Processing...",
        total: int | None = None,
    ) -> Generator[T, None, None]:
        """
        Iterate over items with an optional progress bar.

        Respects --no-progress-bar flag. When disabled, simply yields items
        without any progress display.

        Args:
            iterable: The items to iterate over.
            description: Text to display alongside the progress bar.
            total: Total number of items. If None, attempts to determine
                automatically via .count() (for querysets) or len().

        Yields:
            Items from the iterable.

        Example:
            for doc in self.track(documents, description="Renaming..."):
                process(doc)
        """
        if self.no_progress_bar:
            yield from iterable
            return

        # Attempt to determine total if not provided
        if total is None:
            total = self._get_iterable_length(iterable)

        with self._create_progress(description) as progress:
            task_id = progress.add_task(description, total=total)
            for item in iterable:
                yield item
                progress.advance(task_id)

    def process_parallel(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        *,
        description: str = "Processing...",
    ) -> Generator[ProcessResult[T, R], None, None]:
        """
        Process items in parallel with progress tracking.

        When --processes=1, runs sequentially in the main process without
        spawning subprocesses. This is critical for testing, as multiprocessing
        breaks fixtures, mocks, and database transactions.

        When --processes > 1, uses ProcessPoolExecutor and automatically closes
        database connections before spawning workers (required for PostgreSQL).

        Args:
            fn: Function to apply to each item. Must be picklable for parallel
                execution (i.e., defined at module level, not a lambda or closure).
            items: Sequence of items to process.
            description: Text to display alongside the progress bar.

        Yields:
            ProcessResult for each item, containing the item, result, and any error.

        Example:
            def regenerate_thumbnail(doc_id: int) -> Path:
                ...

            for result in self.process_parallel(regenerate_thumbnail, doc_ids):
                if result.error:
                    self.console.print(f"[red]Failed {result.item}[/red]")
        """
        total = len(items)

        if self.process_count == 1:
            # Sequential execution in main process - critical for testing
            yield from self._process_sequential(fn, items, description, total)
        else:
            # Parallel execution with ProcessPoolExecutor
            yield from self._process_parallel(fn, items, description, total)

    def _process_sequential(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        description: str,
        total: int,
    ) -> Generator[ProcessResult[T, R], None, None]:
        """Process items sequentially in the main process."""
        for item in self.track(items, description=description, total=total):
            try:
                result = fn(item)
                yield ProcessResult(item=item, result=result, error=None)
            except Exception as e:
                yield ProcessResult(item=item, result=None, error=e)

    def _process_parallel(
        self,
        fn: Callable[[T], R],
        items: Sequence[T],
        description: str,
        total: int,
    ) -> Generator[ProcessResult[T, R], None, None]:
        """Process items in parallel using ProcessPoolExecutor."""
        # Close database connections before forking - required for PostgreSQL
        db.connections.close_all()

        with self._create_progress(description) as progress:
            task_id = progress.add_task(description, total=total)

            with ProcessPoolExecutor(max_workers=self.process_count) as executor:
                # Submit all tasks and map futures back to items
                future_to_item = {executor.submit(fn, item): item for item in items}

                # Yield results as they complete
                for future in as_completed(future_to_item):
                    item = future_to_item[future]
                    try:
                        result = future.result()
                        yield ProcessResult(item=item, result=result, error=None)
                    except Exception as e:
                        yield ProcessResult(item=item, result=None, error=e)
                    finally:
                        progress.advance(task_id)
