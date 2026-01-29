"""Transform service for converting v2 exports to v3 format."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import AsyncGenerator
from collections.abc import Callable
from collections.abc import Generator
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict

import ijson

if TYPE_CHECKING:
    from pathlib import Path


class FixtureObject(TypedDict):
    """Structure of a Django fixture object."""

    model: str
    pk: int
    fields: dict[str, Any]


class ProgressUpdate(TypedDict, total=False):
    """Progress update message structure."""

    type: str
    completed: int
    stats: dict[str, int]
    message: str
    level: str
    duration: float
    total_processed: int
    speed: float


TransformFn = Callable[[FixtureObject], FixtureObject]


def transform_documents_document(obj: FixtureObject) -> FixtureObject:
    """Transform a documents.document fixture object for v3 schema."""
    fields: dict[str, Any] = obj["fields"]
    fields.pop("storage_type", None)
    content: Any = fields.get("content")
    fields["content_length"] = len(content) if isinstance(content, str) else 0
    return obj


# Registry of model-specific transforms
TRANSFORMS: dict[str, TransformFn] = {
    "documents.document": transform_documents_document,
}


@dataclass
class TransformService:
    """Service for transforming v2 exports to v3 format.

    This service processes JSON fixtures incrementally using ijson for
    memory-efficient streaming, and yields progress updates suitable
    for WebSocket transmission.
    """

    input_path: Path
    output_path: Path
    update_frequency: int = 100
    _stats: Counter[str] = field(default_factory=Counter, init=False)
    _total_processed: int = field(default=0, init=False)

    def validate(self) -> str | None:
        """Validate preconditions for transform. Returns error message or None."""
        if not self.input_path.exists():
            return f"Input file not found: {self.input_path}"
        if self.output_path.exists():
            return f"Output file already exists: {self.output_path}"
        if self.input_path.resolve() == self.output_path.resolve():
            return "Input and output paths cannot be the same file"
        return None

    def _process_fixture(self, obj: FixtureObject) -> FixtureObject:
        """Apply any registered transforms to a fixture object."""
        model: str = obj["model"]
        transform: TransformFn | None = TRANSFORMS.get(model)
        if transform:
            obj = transform(obj)
            self._stats[model] += 1
        return obj

    def run_sync(self) -> Generator[ProgressUpdate, None, None]:
        """Run the transform synchronously, yielding progress updates.

        This is the core implementation that processes the JSON file
        and yields progress updates at regular intervals.
        """
        error = self.validate()
        if error:
            yield {"type": "error", "message": error}
            return

        self._stats.clear()
        self._total_processed = 0
        start_time = time.perf_counter()

        yield {"type": "log", "message": "Opening input file...", "level": "info"}

        try:
            with (
                self.input_path.open("rb") as infile,
                self.output_path.open("w", encoding="utf-8") as outfile,
            ):
                outfile.write("[\n")
                first = True

                for i, obj in enumerate(ijson.items(infile, "item")):
                    fixture: FixtureObject = obj
                    fixture = self._process_fixture(fixture)
                    self._total_processed += 1

                    if not first:
                        outfile.write(",\n")
                    first = False

                    json.dump(fixture, outfile, ensure_ascii=False)

                    # Yield progress at configured frequency
                    if i > 0 and i % self.update_frequency == 0:
                        yield {
                            "type": "progress",
                            "completed": self._total_processed,
                            "stats": dict(self._stats),
                        }

                outfile.write("\n]\n")

        except Exception as exc:
            # Clean up partial output on error
            if self.output_path.exists():
                self.output_path.unlink()
            yield {"type": "error", "message": str(exc)}
            return

        end_time = time.perf_counter()
        duration = end_time - start_time
        speed = self._total_processed / duration if duration > 0 else 0

        yield {
            "type": "complete",
            "duration": duration,
            "total_processed": self._total_processed,
            "stats": dict(self._stats),
            "speed": speed,
        }

    async def run_async(self) -> AsyncGenerator[ProgressUpdate, None]:
        """Run the transform asynchronously, yielding progress updates.

        This wraps the synchronous implementation to work with async consumers.
        The actual I/O is done synchronously since ijson doesn't support async,
        but we yield control periodically to keep the event loop responsive.
        """
        import asyncio

        for update in self.run_sync():
            yield update
            # Yield control to the event loop periodically
            await asyncio.sleep(0)
