"""
Phase 4 profiling benchmark: ijson streaming parse vs json.load for manifest files.

Run with:
    uv run pytest src/documents/tests/test_importer_profile_phase4.py \
        -m profiling --override-ini="addopts=" -s
"""

import json
import shutil
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import TestCase

from documents.management.commands.document_importer import iter_manifest_records
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.profiling import profile_block
from documents.tests.factories import DocumentFactory
from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import SampleDirMixin


@pytest.mark.profiling
class TestImporterProfilePhase4(DirectoriesMixin, SampleDirMixin, TestCase):
    """
    Benchmarks streaming ijson parse vs json.load over exported manifest files.

    Creates 200 documents + 1 custom field + 200 custom field instances,
    exports them, then compares the parse step in isolation.

    Does not assert on results — inspect printed profile_block output manually.
    """

    def setUp(self) -> None:
        super().setUp()
        self.export_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.export_dir)

    def _create_test_data(self) -> None:
        cf = CustomField.objects.create(
            name="Phase4 Field",
            data_type=CustomField.FieldDataType.STRING,
        )
        docs = DocumentFactory.create_batch(200)
        for doc in docs:
            CustomFieldInstance.objects.create(
                field=cf,
                document=doc,
                value_text=f"value for {doc.pk}",
            )

    def _get_manifest_paths(self) -> list[Path]:
        paths = [self.export_dir / "manifest.json"]
        paths += list(self.export_dir.glob("**/*-manifest.json"))
        return [p for p in paths if p.exists()]

    def test_profile_streaming_vs_json_load(self) -> None:
        self._create_test_data()

        call_command(
            "document_exporter",
            str(self.export_dir),
            "--no-progress-bar",
            "--data-only",
        )

        manifest_paths = self._get_manifest_paths()
        self.assertTrue(manifest_paths, "No manifest files found after export")

        # Baseline: json.load then iterate (original approach — loads all into memory)
        with profile_block("baseline: json.load + iterate"):
            for path in manifest_paths:
                with path.open() as f:
                    records = json.load(f)
                for r in records:
                    _ = r["model"]  # simulate check_manifest_validity

        # New: ijson streaming without accumulation (mirrors check_manifest_validity)
        with profile_block("new: ijson streaming (no accumulation)"):
            for path in manifest_paths:
                for record in iter_manifest_records(path):
                    _ = record["model"]  # process one at a time, no list buildup

        # New: ijson stream-decrypt to temp file (mirrors decrypt_secret_fields)
        tmp_path = self.export_dir / "manifest.bench.json"
        with profile_block("new: ijson stream to temp file"):
            for path in manifest_paths:
                with tmp_path.open("w", encoding="utf-8") as out:
                    out.write("[\n")
                    first = True
                    for record in iter_manifest_records(path):
                        if not first:
                            out.write(",\n")
                        json.dump(record, out, ensure_ascii=False)
                        first = False
                    out.write("\n]\n")
        tmp_path.unlink(missing_ok=True)
