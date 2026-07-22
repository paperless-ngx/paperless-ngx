from __future__ import annotations

import json
from typing import TYPE_CHECKING

from django.core.serializers.json import DjangoJSONEncoder

if TYPE_CHECKING:
    from typing import TextIO


def _dumps(content: list | dict) -> str:
    """Serialize export JSON consistently across all sinks."""
    return json.dumps(content, cls=DjangoJSONEncoder, indent=2, ensure_ascii=False)


class StreamingManifestWriter:
    """Incrementally writes a JSON array to a text handle, one record at a time.

    Knows nothing about folders or zips: it writes the array framing and records
    to whatever handle the sink's ``stream()`` yields. The sink owns the handle's
    lifecycle (atomic rename, compare, spooling).
    """

    def __init__(self, handle: TextIO) -> None:
        self._file = handle
        self._first = True
        self._file.write("[")

    def write_record(self, record: dict) -> None:
        if not self._first:
            self._file.write(",\n")
        else:
            self._first = False
        self._file.write(_dumps(record))

    def write_batch(self, records: list[dict]) -> None:
        for record in records:
            self.write_record(record)

    def close(self) -> None:
        """Write the closing bracket. Does NOT close the handle (the sink owns it)."""
        self._file.write("\n]")
