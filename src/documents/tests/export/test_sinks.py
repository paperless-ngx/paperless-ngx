import io
import json

from documents.export.sinks import StreamingManifestWriter
from documents.export.sinks import _dumps


class TestDumps:
    def test_dumps_is_indented_unicode_json(self) -> None:
        result: str = _dumps({"a": "é", "b": 1})
        assert '"é"' in result  # ensure_ascii=False keeps unicode literal
        assert "\n" in result  # indent=2 produces newlines
        assert json.loads(result) == {"a": "é", "b": 1}


class TestStreamingManifestWriter:
    def test_writes_json_array_of_records(self) -> None:
        handle: io.StringIO = io.StringIO()
        writer: StreamingManifestWriter = StreamingManifestWriter(handle)
        writer.write_batch([{"pk": 1}, {"pk": 2}])
        writer.write_record({"pk": 3})
        writer.close()
        assert json.loads(handle.getvalue()) == [{"pk": 1}, {"pk": 2}, {"pk": 3}]

    def test_empty_manifest_is_valid_empty_array(self) -> None:
        handle: io.StringIO = io.StringIO()
        writer: StreamingManifestWriter = StreamingManifestWriter(handle)
        writer.close()
        assert json.loads(handle.getvalue()) == []
