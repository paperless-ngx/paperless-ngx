import tempfile
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch, call

from django.test import TestCase, override_settings

from documents.models import CustomField, CustomFieldInstance, Document, DocumentType
from documents.models_ocr_templates import OcrTemplate, OcrTemplateZone
from documents.zone_ocr import (
    _apply_transform,
    _convert_value,
    run_zone_extraction,
)


class TestApplyTransform(TestCase):
    """Tests for the _apply_transform function."""

    def test_strip(self):
        self.assertEqual(_apply_transform("  hello  ", "strip"), "hello")

    def test_none(self):
        self.assertEqual(_apply_transform("  hello  ", "none"), "hello")

    def test_uppercase(self):
        self.assertEqual(_apply_transform("hello world", "uppercase"), "HELLO WORLD")

    def test_lowercase(self):
        self.assertEqual(_apply_transform("HELLO WORLD", "lowercase"), "hello world")

    def test_numeric(self):
        self.assertEqual(_apply_transform("INV-2026-001", "numeric"), "2026001")
        self.assertEqual(_apply_transform("€1,234.56", "numeric"), "1,234.56")

    def test_date_dmy(self):
        self.assertEqual(_apply_transform("13.04.2026", "date_dmy"), "2026-04-13")
        self.assertEqual(_apply_transform("Date: 01/12/2025", "date_dmy"), "2025-12-01")
        self.assertEqual(_apply_transform("13.04.26", "date_dmy"), "2026-04-13")

    def test_date_ymd(self):
        self.assertEqual(_apply_transform("2026-04-13", "date_ymd"), "2026-04-13")
        self.assertEqual(_apply_transform("Date: 2026/04/13", "date_ymd"), "2026-04-13")

    def test_date_invalid_falls_back(self):
        self.assertEqual(_apply_transform("not a date", "date_dmy"), "not a date")


class TestConvertValue(TestCase):
    """Tests for the _convert_value function."""

    def test_string(self):
        self.assertEqual(
            _convert_value("Hello", CustomField.FieldDataType.STRING),
            "Hello",
        )

    def test_string_truncation(self):
        long_str = "x" * 200
        result = _convert_value(long_str, CustomField.FieldDataType.STRING)
        self.assertEqual(len(result), 128)

    def test_int(self):
        self.assertEqual(
            _convert_value("42", CustomField.FieldDataType.INT),
            42,
        )

    def test_int_with_noise(self):
        self.assertEqual(
            _convert_value("INV-123", CustomField.FieldDataType.INT),
            123,
        )

    def test_float(self):
        self.assertAlmostEqual(
            _convert_value("1.234,56", CustomField.FieldDataType.FLOAT),
            1234.56,
            places=2,
        )

    def test_float_dot_decimal(self):
        self.assertAlmostEqual(
            _convert_value("1234.56", CustomField.FieldDataType.FLOAT),
            1234.56,
            places=2,
        )

    def test_date_iso(self):
        self.assertEqual(
            _convert_value("2026-04-13", CustomField.FieldDataType.DATE),
            "2026-04-13",
        )

    def test_date_invalid(self):
        self.assertIsNone(
            _convert_value("not a date", CustomField.FieldDataType.DATE),
        )

    def test_long_text(self):
        long = "x" * 500
        self.assertEqual(
            _convert_value(long, CustomField.FieldDataType.LONG_TEXT),
            long,
        )


class TestRunZoneExtraction(TestCase):
    """Tests for the full extraction pipeline."""

    def setUp(self):
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.custom_field = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )

    def test_skips_document_without_type(self):
        """Documents without a document_type should be skipped."""
        doc = Document.objects.create(
            title="No Type",
            content="test",
            mime_type="application/pdf",
        )
        # Should not raise
        run_zone_extraction(doc, Path("/nonexistent"))

    def test_skips_document_without_matching_template(self):
        """Documents with a type but no template should be skipped."""
        other_type = DocumentType.objects.create(name="Other")
        doc = Document.objects.create(
            title="No Template",
            content="test",
            mime_type="application/pdf",
            document_type=other_type,
        )
        run_zone_extraction(doc, Path("/nonexistent"))

    def test_skips_disabled_template(self):
        """Disabled templates should not run."""
        template = OcrTemplate.objects.create(
            name="Disabled",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
            enabled=False,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone",
            custom_field=self.custom_field,
            x=0,
            y=0,
            width=100,
            height=50,
        )

        doc = Document.objects.create(
            title="Test",
            content="test",
            mime_type="application/pdf",
            document_type=self.doc_type,
        )
        run_zone_extraction(doc, Path("/nonexistent"))
        self.assertEqual(CustomFieldInstance.objects.count(), 0)

    @patch("documents.zone_ocr._process_template")
    def test_calls_process_for_enabled_template(self, mock_process):
        """Enabled templates with zones should trigger processing."""
        template = OcrTemplate.objects.create(
            name="Active",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
            enabled=True,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone",
            custom_field=self.custom_field,
            x=0,
            y=0,
            width=100,
            height=50,
        )

        doc = Document.objects.create(
            title="Test",
            content="test",
            mime_type="application/pdf",
            document_type=self.doc_type,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(b"%PDF-1.4 fake")
            f.flush()
            run_zone_extraction(doc, Path(f.name))

        self.assertTrue(mock_process.called)

    def test_skips_template_with_no_zones(self):
        """Templates without zones should be skipped."""
        OcrTemplate.objects.create(
            name="Empty",
            document_type=self.doc_type,
            source_width=2480,
            source_height=3508,
            enabled=True,
        )

        doc = Document.objects.create(
            title="Test",
            content="test",
            mime_type="application/pdf",
            document_type=self.doc_type,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(b"%PDF-1.4 fake")
            f.flush()
            # Should not raise
            run_zone_extraction(doc, Path(f.name))
