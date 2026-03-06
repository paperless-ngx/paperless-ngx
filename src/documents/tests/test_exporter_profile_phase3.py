"""
Phase 3 profiling test: StreamingManifestWriter

Compares memory usage of Phase 3 streaming against a Phase 2 simulation.
The Phase 2 simulation is achieved by monkey-patching StreamingManifestWriter
with a BufferedManifestWriter that has the same interface but accumulates all
records in memory before writing — exactly what Phase 2's manifest_dict did.

Both runs execute the same dump() code path (same querysets, same flow);
the only difference is whether records are written incrementally or buffered.
This isolates the memory impact of the StreamingManifestWriter.

Run with:
    cd src
    uv run pytest documents/tests/test_exporter_profile_phase3.py \
        -m profiling -s --override-ini="addopts="
"""

import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.serializers.json import DjangoJSONEncoder
from django.test import TestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.profiling import profile_block
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin


def _make_documents(n: int, *, sample_dir: Path, originals_dir: Path) -> list[Document]:
    """Create *n* Document rows and copy a real PDF into ORIGINALS_DIR for each."""
    sample_pdf = sample_dir / "simple.pdf"
    docs = []
    for i in range(n):
        doc = Document.objects.create(
            title=f"doc-{i:04d}",
            filename=f"{i:07d}.pdf",
            mime_type="application/pdf",
            checksum=f"{i:032x}",
            content=f"Content of document {i}",
        )
        dest = originals_dir / f"{i:07d}.pdf"
        if sample_pdf.exists():
            shutil.copy(sample_pdf, dest)
        else:
            dest.write_bytes(b"%PDF-1.4 fake")
        docs.append(doc)
    return docs


class BufferedManifestWriter:
    """Phase 2 simulation: accumulates all records in memory, writes all at once on close().

    Has the same interface as StreamingManifestWriter so it can be dropped in
    as a monkey-patch to replicate Phase 2 memory behaviour within Phase 3's dump().
    """

    def __init__(
        self,
        path: Path,
        *,
        compare_json: bool = False,
        files_in_export_dir=None,
    ) -> None:
        self._path = path.resolve()
        self._compare_json = compare_json
        self._files_in_export_dir = (
            files_in_export_dir if files_in_export_dir is not None else set()
        )
        self._records: list[dict] = []

    def write_record(self, record: dict) -> None:
        self._records.append(record)

    def write_batch(self, records: list[dict]) -> None:
        self._records.extend(records)

    def close(self) -> None:
        if self._path in self._files_in_export_dir:
            self._files_in_export_dir.remove(self._path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                self._records,
                cls=DjangoJSONEncoder,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def discard(self) -> None:
        self._records.clear()

    def __enter__(self) -> "BufferedManifestWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is None:
            self.close()
        return False


@pytest.mark.profiling
class TestExporterProfilePhase3(
    DirectoriesMixin,
    SampleDirMixin,
    TestCase,
):
    """Profile streaming vs buffered manifest writing."""

    N_DOCS = 200

    def setUp(self) -> None:
        super().setUp()
        self.export_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.export_dir)

        self.docs = _make_documents(
            self.N_DOCS,
            sample_dir=self.SAMPLE_DIR,
            originals_dir=self.dirs.originals_dir,
        )

        cf = CustomField.objects.create(
            name="Phase3Field",
            data_type=CustomField.FieldDataType.STRING,
        )
        for doc in self.docs:
            CustomFieldInstance.objects.create(
                field=cf,
                document=doc,
                value_text=f"value-{doc.pk}",
            )

    def _run_export(self, target: Path) -> None:
        call_command(
            "document_exporter",
            str(target),
            "--no-progress-bar",
            "--data-only",
            stdout=StringIO(),
            stderr=StringIO(),
        )

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_streaming_export_produces_valid_manifest(self) -> None:
        """Streaming export writes a parseable manifest with all records."""
        self._run_export(self.export_dir)

        manifest_path = self.export_dir / "manifest.json"
        self.assertTrue(manifest_path.exists(), "manifest.json was not created")
        self.assertFalse(
            (self.export_dir / "manifest.json.tmp").exists(),
            "manifest.json.tmp was not cleaned up",
        )

        with manifest_path.open(encoding="utf-8") as fh:
            manifest = json.load(fh)

        self.assertIsInstance(manifest, list)

        doc_records = [r for r in manifest if r.get("model") == "documents.document"]
        self.assertEqual(len(doc_records), self.N_DOCS)

        cfi_records = [
            r for r in manifest if r.get("model") == "documents.customfieldinstance"
        ]
        self.assertEqual(len(cfi_records), self.N_DOCS)

    def test_streaming_peak_memory_less_than_buffered(self) -> None:
        """Streaming export should use less peak memory than buffered (Phase 2).

        Both runs execute the same dump() code path with the same querysets.
        The only variable is whether the manifest writer streams records to disk
        incrementally or accumulates them all in memory before writing.
        """
        import tracemalloc

        patch_target = (
            "documents.management.commands.document_exporter.StreamingManifestWriter"
        )

        # --- Phase 2 simulation: BufferedManifestWriter ---
        buffered_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, buffered_dir)

        with mock.patch(patch_target, BufferedManifestWriter):
            tracemalloc.start()
            self._run_export(buffered_dir)
            _, buffered_peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

        # --- Phase 3: StreamingManifestWriter ---
        streaming_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, streaming_dir)

        tracemalloc.start()
        self._run_export(streaming_dir)
        _, streaming_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"\n  Buffered (Phase 2) peak:  {buffered_peak / 1024:.1f} KiB")  # noqa: T201
        print(f"  Streaming (Phase 3) peak: {streaming_peak / 1024:.1f} KiB")  # noqa: T201
        print(f"  Reduction: {(1 - streaming_peak / buffered_peak) * 100:.1f}%")  # noqa: T201

        self.assertLess(
            streaming_peak,
            buffered_peak,
            f"Streaming peak ({streaming_peak / 1024:.1f} KiB) was not less than "
            f"buffered peak ({buffered_peak / 1024:.1f} KiB)",
        )

    def test_profiling_output(self) -> None:
        """Print detailed profile output for Phase 2 simulation vs Phase 3 streaming."""
        patch_target = (
            "documents.management.commands.document_exporter.StreamingManifestWriter"
        )

        buffered_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, buffered_dir)

        streaming_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, streaming_dir)

        with mock.patch(patch_target, BufferedManifestWriter):
            with profile_block(
                f"Phase 2 simulation — buffered ({self.N_DOCS} docs + {self.N_DOCS} CFIs)",
            ):
                self._run_export(buffered_dir)

        with profile_block(
            f"Phase 3 — streaming ({self.N_DOCS} docs + {self.N_DOCS} CFIs)",
        ):
            self._run_export(streaming_dir)
