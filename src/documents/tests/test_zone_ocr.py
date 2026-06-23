"""Tests for the zone-based OCR extraction engine."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from django.test import TestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.zone_ocr import _apply_transform
from documents.zone_ocr import _convert_value
from documents.zone_ocr import _detect_mime
from documents.zone_ocr import _resolve_doc_path
from documents.zone_ocr import run_zone_extraction


class TestApplyTransform(TestCase):
    """Tests for the _apply_transform function."""

    def test_strip(self):
        self.assertEqual(_apply_transform("  hello  ", "strip"), "hello")

    def test_none_transform(self):
        self.assertEqual(_apply_transform("  hello  ", "none"), "hello")

    def test_uppercase(self):
        self.assertEqual(_apply_transform("hello world", "uppercase"), "HELLO WORLD")

    def test_lowercase(self):
        self.assertEqual(_apply_transform("HELLO WORLD", "lowercase"), "hello world")

    def test_numeric_basic(self):
        self.assertEqual(_apply_transform("INV-2026-001", "numeric"), "2026-001")

    def test_numeric_with_currency(self):
        self.assertEqual(_apply_transform("€1,234.56", "numeric"), "1,234.56")

    def test_numeric_empty_result_falls_back(self):
        self.assertEqual(_apply_transform("abc", "numeric"), "abc")

    def test_date_dmy_dots(self):
        self.assertEqual(_apply_transform("13.04.2026", "date_dmy"), "2026-04-13")

    def test_date_dmy_slashes(self):
        self.assertEqual(_apply_transform("01/12/2025", "date_dmy"), "2025-12-01")

    def test_date_dmy_two_digit_year(self):
        self.assertEqual(_apply_transform("13.04.26", "date_dmy"), "2026-04-13")

    def test_date_dmy_with_prefix(self):
        self.assertEqual(_apply_transform("Date: 01/12/2025", "date_dmy"), "2025-12-01")

    def test_date_dmy_invalid_falls_back(self):
        self.assertEqual(_apply_transform("32.13.2026", "date_dmy"), "32.13.2026")

    def test_date_dmy_no_match_falls_back(self):
        self.assertEqual(_apply_transform("not a date", "date_dmy"), "not a date")

    def test_date_ymd_dashes(self):
        self.assertEqual(_apply_transform("2026-04-13", "date_ymd"), "2026-04-13")

    def test_date_ymd_slashes(self):
        self.assertEqual(_apply_transform("2026/04/13", "date_ymd"), "2026-04-13")

    def test_date_ymd_invalid_falls_back(self):
        self.assertEqual(_apply_transform("2026-13-32", "date_ymd"), "2026-13-32")

    def test_empty_string(self):
        self.assertEqual(_apply_transform("", "strip"), "")

    def test_whitespace_only(self):
        self.assertEqual(_apply_transform("   ", "strip"), "")

    def test_unknown_transform_strips(self):
        self.assertEqual(_apply_transform("  hello  ", "unknown"), "hello")


class TestConvertValue(TestCase):
    """Tests for the _convert_value function."""

    def test_string(self):
        self.assertEqual(
            _convert_value("Hello", CustomField.FieldDataType.STRING),
            "Hello",
        )

    def test_string_truncation(self):
        result = _convert_value("x" * 200, CustomField.FieldDataType.STRING)
        self.assertEqual(len(result), 128)

    def test_url(self):
        self.assertEqual(
            _convert_value("https://example.com", CustomField.FieldDataType.URL),
            "https://example.com",
        )

    def test_long_text(self):
        long = "x" * 500
        self.assertEqual(
            _convert_value(long, CustomField.FieldDataType.LONG_TEXT),
            long,
        )

    def test_int_simple(self):
        self.assertEqual(_convert_value("42", CustomField.FieldDataType.INT), 42)

    def test_int_with_noise(self):
        self.assertEqual(_convert_value("INV-123", CustomField.FieldDataType.INT), 123)

    def test_int_negative(self):
        self.assertEqual(_convert_value("-42", CustomField.FieldDataType.INT), -42)

    def test_int_empty_returns_none(self):
        self.assertIsNone(_convert_value("abc", CustomField.FieldDataType.INT))

    def test_int_only_dash_returns_none(self):
        self.assertIsNone(_convert_value("-", CustomField.FieldDataType.INT))

    def test_float_simple(self):
        self.assertAlmostEqual(
            _convert_value("1234.56", CustomField.FieldDataType.FLOAT),
            1234.56,
        )

    def test_float_european_format(self):
        self.assertAlmostEqual(
            _convert_value("1.234,56", CustomField.FieldDataType.FLOAT),
            1234.56,
        )

    def test_float_us_format(self):
        self.assertAlmostEqual(
            _convert_value("1,234.56", CustomField.FieldDataType.FLOAT),
            1234.56,
        )

    def test_float_comma_only(self):
        self.assertAlmostEqual(
            _convert_value("1234,56", CustomField.FieldDataType.FLOAT),
            1234.56,
        )

    def test_float_empty_returns_none(self):
        self.assertIsNone(_convert_value("abc", CustomField.FieldDataType.FLOAT))

    def test_float_only_separator_returns_none(self):
        self.assertIsNone(_convert_value(",", CustomField.FieldDataType.FLOAT))

    def test_date_iso(self):
        self.assertEqual(
            _convert_value("2026-04-13", CustomField.FieldDataType.DATE),
            "2026-04-13",
        )

    def test_date_invalid_returns_none(self):
        self.assertIsNone(_convert_value("not a date", CustomField.FieldDataType.DATE))

    def test_date_invalid_values_returns_none(self):
        self.assertIsNone(_convert_value("2026-13-32", CustomField.FieldDataType.DATE))

    def test_monetary_simple(self):
        self.assertEqual(
            _convert_value("123.45", CustomField.FieldDataType.MONETARY),
            "123.45",
        )

    def test_monetary_european(self):
        self.assertEqual(
            _convert_value("1.234,56", CustomField.FieldDataType.MONETARY),
            "1234.56",
        )

    def test_monetary_with_currency_symbol(self):
        self.assertEqual(
            _convert_value("€1,234.56", CustomField.FieldDataType.MONETARY),
            "1234.56",
        )

    def test_monetary_empty_returns_none(self):
        self.assertIsNone(_convert_value("CHF", CustomField.FieldDataType.MONETARY))

    def test_bool_true(self):
        for val in ("true", "True", "yes", "1", "ja", "x", "X"):
            self.assertTrue(
                _convert_value(val, CustomField.FieldDataType.BOOL),
                f"Expected True for {val!r}",
            )

    def test_bool_false(self):
        for val in ("false", "False", "no", "0", "nein"):
            self.assertFalse(
                _convert_value(val, CustomField.FieldDataType.BOOL),
                f"Expected False for {val!r}",
            )

    def test_bool_unknown_returns_none(self):
        self.assertIsNone(_convert_value("maybe", CustomField.FieldDataType.BOOL))

    def test_unsupported_type_returns_none(self):
        self.assertIsNone(
            _convert_value("test", CustomField.FieldDataType.DOCUMENTLINK),
        )
        self.assertIsNone(
            _convert_value("test", CustomField.FieldDataType.SELECT),
        )

    def test_empty_string_returns_none(self):
        self.assertIsNone(_convert_value("", CustomField.FieldDataType.STRING))


class TestDetectMime(TestCase):
    """Tests for _detect_mime."""

    def test_pdf_extension(self):
        self.assertEqual(_detect_mime(Path("test.pdf")), "application/pdf")

    def test_png_extension(self):
        self.assertEqual(_detect_mime(Path("test.png")), "image/png")

    def test_jpg_extension(self):
        self.assertEqual(_detect_mime(Path("test.jpg")), "image/jpeg")

    def test_unknown_extension(self):
        self.assertIsNone(_detect_mime(Path("test.xyz")))

    def test_webp_extension(self):
        self.assertEqual(_detect_mime(Path("test.webp")), "image/webp")


class TestResolveDocPath(TestCase):
    """Tests for _resolve_doc_path."""

    def test_returns_none_when_no_files_exist(self):
        doc = MagicMock()
        doc.has_archive_version = False
        doc.source_path = Path("/nonexistent/source.pdf")
        result = _resolve_doc_path(doc, None)
        self.assertIsNone(result)

    def test_returns_original_file_as_fallback(self):
        doc = MagicMock()
        doc.has_archive_version = False
        doc.source_path = Path("/nonexistent/source.pdf")

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            result = _resolve_doc_path(doc, Path(f.name))
            self.assertEqual(result, Path(f.name))

    def test_returns_none_for_none_original_file(self):
        doc = MagicMock()
        doc.has_archive_version = False
        doc.source_path = Path("/nonexistent/source.pdf")
        result = _resolve_doc_path(doc, None)
        self.assertIsNone(result)


class TestRunZoneExtraction(TestCase):
    """Tests for the full extraction pipeline."""

    def setUp(self):
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.custom_field = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )

    def test_skips_document_without_type(self):
        doc = Document.objects.create(
            title="No Type",
            content="test",
            mime_type="application/pdf",
        )
        run_zone_extraction(doc, Path("/nonexistent"))
        self.assertEqual(CustomFieldInstance.objects.count(), 0)

    def test_skips_document_without_matching_template(self):
        other_type = DocumentType.objects.create(name="Other")
        doc = Document.objects.create(
            title="No Template",
            content="test",
            mime_type="application/pdf",
            document_type=other_type,
        )
        run_zone_extraction(doc, Path("/nonexistent"))
        self.assertEqual(CustomFieldInstance.objects.count(), 0)

    def test_skips_disabled_template(self):
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

    def test_skips_template_with_no_zones(self):
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
            run_zone_extraction(doc, Path(f.name))
        self.assertEqual(CustomFieldInstance.objects.count(), 0)

    @patch("documents.zone_ocr._process_template")
    def test_calls_process_for_enabled_template(self, mock_process):
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

    @patch("documents.zone_ocr._process_template")
    def test_handles_process_exception_gracefully(self, mock_process):
        """A failing template should not prevent other templates from running."""
        mock_process.side_effect = RuntimeError("test error")

        template = OcrTemplate.objects.create(
            name="Failing",
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
            # Should not raise
            run_zone_extraction(doc, Path(f.name))

    def test_handles_none_original_file(self):
        """Should not crash when original_file is None."""
        doc = Document.objects.create(
            title="Test",
            content="test",
            mime_type="application/pdf",
            document_type=self.doc_type,
        )
        # No template, so it exits early — but shouldn't crash on None
        run_zone_extraction(doc, None)

    @patch("documents.zone_ocr._process_template")
    def test_multiple_templates_all_process(self, mock_process):
        """Multiple enabled templates for the same type should all run."""
        for i in range(3):
            template = OcrTemplate.objects.create(
                name=f"Template {i}",
                document_type=self.doc_type,
                source_width=2480,
                source_height=3508,
                enabled=True,
            )
            OcrTemplateZone.objects.create(
                template=template,
                name=f"Zone {i}",
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

        self.assertEqual(mock_process.call_count, 3)
