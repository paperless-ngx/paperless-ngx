"""Tests for the zone-based OCR extraction engine."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.test import TestCase
from PIL import Image

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import MatchingModel
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.zone_ocr import _apply_transform
from documents.zone_ocr import _convert_value
from documents.zone_ocr import _crop_zone
from documents.zone_ocr import _detect_mime
from documents.zone_ocr import _extract_zone
from documents.zone_ocr import _process_template
from documents.zone_ocr import _resolve_doc_path
from documents.zone_ocr import extract_zone_preview
from documents.zone_ocr import get_templates_for_document
from documents.zone_ocr import run_zone_extraction
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.permissions import grant_object


class TestZoneExtraction(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)
        self.page = self.tmp_path / "page.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.paste("black", (20, 10, 60, 30))
            image.save(self.page)
        self.zone = OcrTemplateZone(
            name="Account",
            x=10,
            y=5,
            width=20,
            height=10,
            transform="uppercase",
            ocr_language="eng",
        )
        settings = self.settings(SCRATCH_DIR=self.tmp_path)
        settings.enable()
        self.addCleanup(settings.disable)

    def test_crop_scales_coordinates(self):
        with _crop_zone(self.page, self.zone, 100, 50) as cropped:
            self.assertEqual(cropped.size, (40, 20))
            self.assertEqual(cropped.getextrema(), ((0, 0), (0, 0), (0, 0)))

    def test_crop_defaults_to_image_dimensions(self):
        with _crop_zone(self.page, self.zone, 0, 0) as cropped:
            self.assertEqual(cropped.size, (20, 10))
            self.assertEqual(cropped.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(cropped.getpixel((19, 9)), (0, 0, 0))

    def test_crop_clamps_to_image(self):
        self.zone.x, self.zone.y = 90, 40
        with _crop_zone(self.page, self.zone, 100, 50) as cropped:
            self.assertEqual(cropped.size, (20, 20))

    @patch("documents.zone_ocr.subprocess.run")
    def test_tiny_crop_skips_reader(self, run):
        self.zone.width = 0
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertIsNone(result.raw_text)
        self.assertIsNone(result.value)
        run.assert_not_called()

    @patch("documents.zone_ocr.subprocess.run")
    def test_unreadable_image_skips_reader(self, run):
        self.page.write_bytes(b"not an image")
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertIsNone(result.raw_text)
        self.assertIsNone(result.value)
        run.assert_not_called()

    @patch("documents.zone_ocr.subprocess.run")
    def test_text_extraction_retains_raw_text_and_transforms(self, run):
        def read_crop(args, **kwargs):
            with Image.open(args[1]) as crop:
                self.assertEqual(crop.size, (40, 20))
                self.assertEqual(crop.getpixel((0, 0)), (0, 0, 0))
            return MagicMock(stdout="  account abc\n")

        run.side_effect = read_crop
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertEqual(result.raw_text, "account abc")
        self.assertEqual(result.value, "ACCOUNT ABC")
        self.assertEqual(run.call_args.args[0][-4:], ["-l", "eng", "--psm", "6"])
        self.assertEqual(run.call_args.kwargs["timeout"], 30)

    @patch("documents.zone_ocr.subprocess.run")
    def test_no_text_returns_no_value(self, run):
        run.return_value.stdout = " \n"
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertIsNone(result.raw_text)
        self.assertIsNone(result.value)

    @patch("documents.zone_ocr.subprocess.run")
    def test_date_transform_uses_zone_format(self, run):
        self.zone.transform = "date"
        self.zone.date_format = "%d/%m/%Y"
        run.return_value.stdout = "25/12/2025"
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertEqual(result.raw_text, "25/12/2025")
        self.assertEqual(result.value, "2025-12-25")

    @patch("documents.zone_ocr.subprocess.run")
    @patch("zxingcpp.read_barcodes")
    def test_barcode_extraction_bypasses_tesseract(self, read_barcodes, run):
        self.zone.transform = "qr_code"

        def read_crop(image):
            self.assertEqual(image.size, (40, 20))
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0))
            return [MagicMock(text="  https://example.com  ")]

        read_barcodes.side_effect = read_crop
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertEqual(result.raw_text, "  https://example.com  ")
        self.assertEqual(result.value, "https://example.com")
        run.assert_not_called()
        with self.assertRaises(ValueError):
            read_barcodes.call_args.args[0].getpixel((0, 0))

    @patch("zxingcpp.read_barcodes", return_value=[])
    def test_missing_barcode_returns_no_value(self, read_barcodes):
        self.zone.transform = "qr_code"
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertIsNone(result.raw_text)
        self.assertIsNone(result.value)

    @patch("documents.zone_ocr.subprocess.run")
    def test_preview_uses_image_dimensions_without_writing(self, run):
        run.return_value.stdout = "account abc"
        self.assertEqual(
            extract_zone_preview(self.page, self.zone, 0, 0, 1),
            {"raw_text": "account abc", "value": "ACCOUNT ABC"},
        )

    @patch("documents.zone_ocr.subprocess.run")
    def test_preview_unavailable_page_skips_reader(self, run):
        self.zone.page = 2
        self.assertEqual(
            extract_zone_preview(self.page, self.zone, 100, 50, 1),
            {"raw_text": None, "value": None},
        )
        run.assert_not_called()


class TestSavedZoneExtraction(DirectoriesMixin, TestCase):
    @patch("documents.zone_ocr.subprocess.run")
    def test_saved_extraction_matches_preview_and_rejects_invalid_value(self, run):
        page = Path(self.dirs.scratch_dir) / "page.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.save(page)
        document = DocumentFactory(title="Original")
        template = OcrTemplate.objects.create(
            name="Account",
            source_width=100,
            source_height=50,
        )
        zone = OcrTemplateZone.objects.create(
            template=template,
            name="Title",
            target="title",
            x=0,
            y=0,
            width=20,
            height=10,
            transform="uppercase",
            validation_regex="ACCOUNT [A-Z]+",
        )
        for raw_text, expected_title in [
            ("account abc", "ACCOUNT ABC"),
            ("invalid", "ACCOUNT ABC"),
        ]:
            with self.subTest(raw_text=raw_text):
                run.return_value.stdout = raw_text
                preview = extract_zone_preview(page, zone, 100, 50, 1)
                self.assertEqual(preview["raw_text"], raw_text)
                self.assertEqual(preview["value"], raw_text.upper())
                _process_template(document, page, template, [zone])
                document.refresh_from_db()
                self.assertEqual(document.title, expected_title)


class TestTemplateVisibility(DirectoriesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="document_owner")
        self.other = User.objects.create_user(username="other_owner")
        self.document = DocumentFactory(
            owner=self.owner,
            content="Northwind Power & Light statement",
        )
        self.mine = self.template("Mine", owner=self.owner)
        self.unowned = self.template("Unowned")
        self.private = self.template("Private", owner=self.other)

    def template(self, name, **kwargs):
        kwargs.setdefault("match", "Northwind")
        kwargs.setdefault("matching_algorithm", MatchingModel.MATCH_ANY)
        return OcrTemplate.objects.create(
            name=name,
            source_width=100,
            source_height=100,
            **kwargs,
        )

    def test_only_matching_owned_unowned_and_shared_templates_apply(self):
        shared = self.template("Shared", owner=self.other)
        grant_object(self.owner, shared, "view_ocrtemplate")
        self.template("Disabled", owner=self.owner, enabled=False)
        self.template("Other sender", owner=self.owner, match="Contoso")
        self.template(
            "No matching",
            owner=self.owner,
            matching_algorithm=MatchingModel.MATCH_NONE,
        )
        self.assertCountEqual(
            get_templates_for_document(self.document),
            [self.mine, self.unowned, shared],
        )

    def test_group_sharing_applies(self):
        group = Group.objects.create(name="OCR users")
        self.owner.groups.add(group)
        grant_object(group, self.private, "view_ocrtemplate")
        self.assertIn(self.private, get_templates_for_document(self.document))

    def test_unowned_documents_only_use_unowned_templates(self):
        self.document.owner = None
        self.assertEqual(get_templates_for_document(self.document), [self.unowned])

    def test_versions_use_the_root_documents_owner(self):
        version = DocumentFactory(
            root_document=self.document,
            owner=self.other,
            content=self.document.content,
        )
        self.assertCountEqual(
            get_templates_for_document(version),
            [self.mine, self.unowned],
        )

    def test_superuser_owner_can_use_all_visible_templates(self):
        self.owner.is_superuser = True
        self.assertCountEqual(
            get_templates_for_document(self.document),
            [self.mine, self.unowned, self.private],
        )

    def test_inactive_owner_has_no_templates(self):
        self.owner.is_active = False
        self.assertEqual(get_templates_for_document(self.document), [])

    @patch("documents.zone_ocr._process_template")
    def test_extraction_never_processes_private_templates(self, process):
        for template in (self.mine, self.unowned, self.private):
            OcrTemplateZone.objects.create(
                template=template,
                name="Title",
                target="title",
                x=0,
                y=0,
                width=20,
                height=20,
            )
        self.document.source_path.write_bytes(b"test PDF")

        run_zone_extraction(self.document, None)

        self.assertCountEqual(
            [call.args[2] for call in process.call_args_list],
            [self.mine, self.unowned],
        )


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
        self.assertEqual(_apply_transform("Invoice 2026-001", "numeric"), "2026-001")

    def test_numeric_with_currency(self):
        self.assertEqual(_apply_transform("€1,234.56", "numeric"), "1,234.56")

    def test_numeric_empty_result_falls_back(self):
        self.assertEqual(_apply_transform("abc", "numeric"), "abc")

    def test_date_with_format(self):
        self.assertEqual(
            _apply_transform("13.04.2026", "date", "%d.%m.%Y"),
            "2026-04-13",
        )
        self.assertEqual(
            _apply_transform("01/12/2025", "date", "%d/%m/%Y"),
            "2025-12-01",
        )

    def test_date_two_digit_year(self):
        self.assertEqual(
            _apply_transform("13.04.26", "date", "%d.%m.%y"),
            "2026-04-13",
        )

    def test_date_auto_detect(self):
        self.assertEqual(_apply_transform("2026-04-13", "date"), "2026-04-13")
        self.assertEqual(_apply_transform("2026/04/13", "date"), "2026-04-13")
        self.assertEqual(_apply_transform("13 April 2026", "date"), "2026-04-13")

    def test_date_format_mismatch_falls_back_to_auto_detect(self):
        self.assertEqual(
            _apply_transform("2026-04-13", "date", "%d.%m.%Y"),
            "2026-04-13",
        )

    def test_date_invalid_returns_text(self):
        self.assertEqual(
            _apply_transform("32.13.2026", "date", "%d.%m.%Y"),
            "32.13.2026",
        )
        self.assertEqual(_apply_transform("2026-13-32", "date"), "2026-13-32")
        self.assertEqual(_apply_transform("not a date", "date"), "not a date")

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
        self.custom_field = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )

    @patch("documents.zone_ocr._process_template")
    def test_skips_template_that_does_not_match(self, mock_process):
        template = OcrTemplate.objects.create(
            name="Other sender",
            match="Contoso",
            source_width=2480,
            source_height=3508,
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
            title="No Template",
            content="test",
            mime_type="application/pdf",
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(b"%PDF-1.4 fake")
            f.flush()
            run_zone_extraction(doc, Path(f.name))

        mock_process.assert_not_called()

    def test_skips_disabled_template(self):
        template = OcrTemplate.objects.create(
            name="Disabled",
            match="test",
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
        )
        run_zone_extraction(doc, Path("/nonexistent"))
        self.assertEqual(CustomFieldInstance.objects.count(), 0)

    def test_skips_template_with_no_zones(self):
        OcrTemplate.objects.create(
            name="Empty",
            match="test",
            source_width=2480,
            source_height=3508,
            enabled=True,
        )

        doc = Document.objects.create(
            title="Test",
            content="test",
            mime_type="application/pdf",
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
            match="test",
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
            match="test",
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
        )
        # No template, so it exits early — but shouldn't crash on None
        run_zone_extraction(doc, None)

    @patch("documents.zone_ocr._process_template")
    def test_multiple_templates_all_process(self, mock_process):
        """Multiple matching templates should all run."""
        for i in range(3):
            template = OcrTemplate.objects.create(
                name=f"Template {i}",
                match="test",
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
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(b"%PDF-1.4 fake")
            f.flush()
            run_zone_extraction(doc, Path(f.name))

        self.assertEqual(mock_process.call_count, 3)
