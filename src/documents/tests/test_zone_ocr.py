"""Tests for the zone-based OCR extraction engine."""

import subprocess
import tempfile
from datetime import date
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
from documents.zone_ocr import _combine_field_value
from documents.zone_ocr import _convert_value
from documents.zone_ocr import _crop_zone
from documents.zone_ocr import _detect_mime
from documents.zone_ocr import _extract_zone
from documents.zone_ocr import _prepare_field_update
from documents.zone_ocr import _process_template
from documents.zone_ocr import _render_pages
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
    def test_reader_failures_return_no_value(self, run):
        for error in [
            subprocess.TimeoutExpired("tesseract", 30),
            subprocess.CalledProcessError(1, "tesseract", stderr="failure"),
            subprocess.CalledProcessError(1, "tesseract"),
            FileNotFoundError("tesseract"),
        ]:
            with self.subTest(error=type(error).__name__):
                run.side_effect = error
                result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
                self.assertIsNone(result.raw_text)
                self.assertIsNone(result.value)

    @patch("zxingcpp.read_barcodes", side_effect=RuntimeError("reader failed"))
    def test_barcode_failure_returns_no_value(self, read_barcodes):
        self.zone.transform = "qr_code"
        result = _extract_zone(self.page, self.zone, 100, 50, self.tmp_path)
        self.assertIsNone(result.raw_text)
        self.assertIsNone(result.value)

    @patch("documents.zone_ocr.subprocess.run")
    def test_preview_tiny_crop_returns_empty_result(self, run):
        self.zone.width = 0
        self.assertEqual(
            extract_zone_preview(self.page, self.zone, 100, 50, 1),
            {
                "raw_text": None,
                "value": None,
            },
        )
        run.assert_not_called()

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
    def setUp(self):
        super().setUp()
        self.page = self.dirs.scratch_dir / "page.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.save(self.page)
        self.document = DocumentFactory(title="Original")
        self.template = OcrTemplate.objects.create(
            name="Account",
            source_width=100,
            source_height=50,
        )

    def zone(self, name, target="title", **kwargs):
        return OcrTemplateZone.objects.create(
            template=self.template,
            name=name,
            target=target,
            x=0,
            y=0,
            width=20,
            height=10,
            **kwargs,
        )

    @patch("documents.zone_ocr.subprocess.run")
    def test_combines_zones_and_writes_each_field_once(self, run):
        zones = [self.zone("First"), self.zone("Second")]
        self.template.combine_formats = {"title": "{Second} / {First}"}
        run.side_effect = [MagicMock(stdout="one"), MagicMock(stdout="two")]
        with patch.object(self.document, "save", wraps=self.document.save) as save:
            _process_template(
                self.document,
                {0: self.page},
                self.template,
                zones,
                self.dirs.scratch_dir,
            )
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "two / one")
        save.assert_called_once_with(update_fields=["title"])

    @patch("documents.zone_ocr.subprocess.run")
    def test_converts_custom_and_builtin_fields_before_saving(self, run):
        field = CustomField.objects.create(name="Paid", data_type="boolean")
        zones = [
            self.zone("Title"),
            self.zone("ASN", "asn"),
            self.zone("Created", "created"),
            self.zone("Paid", "custom_field", custom_field=field),
        ]
        run.side_effect = [
            MagicMock(stdout=value)
            for value in [
                "New title",
                "ASN 42",
                "2026-04-13",
                "no",
            ]
        ]
        _process_template(
            self.document,
            {0: self.page},
            self.template,
            zones,
            self.dirs.scratch_dir,
        )
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "New title")
        self.assertEqual(self.document.archive_serial_number, 42)
        self.assertEqual(self.document.created, date(2026, 4, 13))
        self.assertFalse(self.document.custom_fields.get(field=field).value)

    @patch("documents.zone_ocr.subprocess.run")
    def test_invalid_field_values_preserve_existing_values(self, run):
        field = CustomField.objects.create(name="Number", data_type="integer")
        CustomFieldInstance.objects.create(
            document=self.document,
            field=field,
            value_int=12,
        )
        zones = [
            self.zone("Title"),
            self.zone("ASN", "asn"),
            self.zone("Created", "created"),
            self.zone("Number", "custom_field", custom_field=field),
            self.zone("Unassigned", "custom_field"),
        ]
        original_created = self.document.created
        run.side_effect = [
            MagicMock(stdout=value)
            for value in [
                "Valid",
                "9999999999999999999999999999999",
                "invalid",
                "abc",
                "text",
            ]
        ]
        _process_template(
            self.document,
            {0: self.page},
            self.template,
            zones,
            self.dirs.scratch_dir,
        )
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Valid")
        self.assertIsNone(self.document.archive_serial_number)
        self.assertEqual(self.document.created, original_created)
        self.assertEqual(self.document.custom_fields.get(field=field).value, 12)

    @patch("documents.zone_ocr.subprocess.run")
    def test_write_failure_rolls_back_template_and_restores_document(self, run):
        field = CustomField.objects.create(name="Number", data_type="integer")
        zones = [
            self.zone("Title"),
            self.zone("Number", "custom_field", custom_field=field),
        ]
        run.side_effect = [MagicMock(stdout="New title"), MagicMock(stdout="42")]
        save = self.document.save

        def fail_after_save(**kwargs):
            save(**kwargs)
            raise RuntimeError("save failed")

        with patch.object(self.document, "save", side_effect=fail_after_save):
            with self.assertRaisesMessage(RuntimeError, "save failed"):
                _process_template(
                    self.document,
                    {0: self.page},
                    self.template,
                    zones,
                    self.dirs.scratch_dir,
                )
        self.assertEqual(self.document.title, "Original")
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Original")
        self.assertFalse(self.document.custom_fields.exists())

    @patch("documents.zone_ocr.subprocess.run")
    def test_last_successful_template_wins(self, run):
        self.zone("First")
        second = OcrTemplate.objects.create(
            name="Second",
            source_width=100,
            source_height=50,
        )
        self.template = second
        self.zone("Second")
        third = OcrTemplate.objects.create(
            name="Third",
            source_width=100,
            source_height=50,
        )
        self.template = third
        self.zone("Third", validation_regex="accepted")
        templates = list(OcrTemplate.objects.order_by("pk"))
        run.side_effect = [
            MagicMock(stdout=value) for value in ["First", "Second", "rejected"]
        ]
        run_zone_extraction(self.document, self.page, templates=templates)
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Second")

    @patch("documents.zone_ocr.subprocess.run")
    def test_document_run_renders_each_page_once_across_templates(self, run):
        self.document.page_count = 2
        self.zone("First", page=1)
        self.zone("Last", page=-1)
        first = self.template
        self.template = OcrTemplate.objects.create(
            name="Second",
            source_width=100,
            source_height=50,
        )
        self.zone("Last again", page=2)
        pdf = self.dirs.scratch_dir / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        rendered = []

        def execute(args, **kwargs):
            if args[0] == "pdftoppm":
                output = Path(args[-1]).with_suffix(".png")
                with Image.new("RGB", (100, 50), "white") as image:
                    image.save(output)
                rendered.append(output)
                return subprocess.CompletedProcess(args, 0)
            return subprocess.CompletedProcess(args, 0, stdout="extracted")

        run.side_effect = execute
        results = run_zone_extraction(
            self.document,
            pdf,
            templates=[first, self.template],
        )
        render_calls = [
            call for call in run.call_args_list if call.args[0][0] == "pdftoppm"
        ]
        self.assertEqual(len(render_calls), 2)
        self.assertEqual(
            [call.args[0][call.args[0].index("-f") + 1] for call in render_calls],
            ["1", "2"],
        )
        self.assertEqual([result.reason for result in results], [None, None, None])
        self.assertFalse(any(path.exists() for path in rendered))

    @patch("documents.zone_ocr.subprocess.run")
    def test_zone_dimensions_override_template_dimensions(self, run):
        zone = self.zone("Title", zone_source_width=200, zone_source_height=100)

        def read_crop(args, **kwargs):
            with Image.open(args[1]) as crop:
                self.assertEqual(crop.size, (20, 10))
            return subprocess.CompletedProcess(args, 0, stdout="extracted")

        run.side_effect = read_crop
        _process_template(
            self.document,
            {0: self.page},
            self.template,
            [zone],
            self.dirs.scratch_dir,
        )
        self.assertEqual(self.document.title, "extracted")

    def test_missing_page_returns_skipped_result(self):
        zone = self.zone("Last", page=-1)
        results = _process_template(
            self.document,
            {},
            self.template,
            [zone],
            self.dirs.scratch_dir,
        )
        self.assertEqual(results[0].reason, "missing_page")
        self.assertIsNone(results[0].value)

    def test_missing_document_file_returns_skipped_results(self):
        self.zone("Title")
        results = run_zone_extraction(self.document, None, templates=[self.template])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].reason, "missing_file")
        self.assertIsNone(results[0].value)

    @patch("documents.zone_ocr.subprocess.run")
    def test_empty_combination_cannot_clear_a_field(self, run):
        zone = self.zone("Title")
        self.template.combine_formats = {"title": "{Unknown}"}
        run.return_value.stdout = "extracted"
        results = _process_template(
            self.document,
            {0: self.page},
            self.template,
            [zone],
            self.dirs.scratch_dir,
        )
        self.assertEqual(results[0].reason, "invalid_value")
        self.assertIsNone(results[0].value)
        self.assertEqual(self.document.title, "Original")

    @patch("documents.zone_ocr.subprocess.run")
    def test_skipped_results_never_report_existing_document_values(self, run):
        zones = [
            self.zone("Empty"),
            self.zone("Rejected", validation_regex="accepted"),
            self.zone("Invalid", "asn"),
            self.zone("Unassigned", "custom_field"),
        ]
        run.side_effect = [
            MagicMock(stdout=value) for value in ["", "rejected", "abc", "orphan"]
        ]
        results = _process_template(
            self.document,
            {0: self.page},
            self.template,
            zones,
            self.dirs.scratch_dir,
        )
        self.assertEqual(
            [result.reason for result in results],
            [
                "no_value",
                "regex_mismatch",
                "invalid_value",
                "unassigned",
            ],
        )
        self.assertEqual([result.value for result in results], [None] * 4)
        self.assertEqual(self.document.title, "Original")

    @patch("documents.zone_ocr.subprocess.run")
    def test_failed_template_reports_rollback_and_next_template_still_runs(self, run):
        DocumentFactory(archive_serial_number=42)
        self.zone("Title")
        self.zone("Conflict", "asn")
        second = OcrTemplate.objects.create(
            name="Second",
            source_width=100,
            source_height=50,
        )
        first = self.template
        self.template = second
        self.zone("Second")
        run.side_effect = [
            MagicMock(stdout=value) for value in ["Rolled back", "42", "Applied"]
        ]
        results = run_zone_extraction(
            self.document,
            self.page,
            templates=[first, second],
        )
        self.assertEqual(
            [result.reason for result in results],
            ["template_failed", "template_failed", None],
        )
        self.assertEqual([result.value for result in results], [None, None, "Applied"])
        self.document.refresh_from_db()
        self.assertEqual(self.document.title, "Applied")
        self.assertIsNone(self.document.archive_serial_number)

    @patch("documents.zone_ocr.subprocess.run")
    def test_literal_format_does_not_write_when_every_zone_failed(self, run):
        zone = self.zone("Title")
        self.template.combine_formats = {"title": "Invoice {Title}"}
        run.return_value.stdout = ""
        results = _process_template(
            self.document,
            {0: self.page},
            self.template,
            [zone],
            self.dirs.scratch_dir,
        )
        self.assertEqual(results[0].reason, "no_value")
        self.assertIsNone(results[0].value)
        self.assertEqual(self.document.title, "Original")

    @patch("documents.zone_ocr.subprocess.run")
    def test_saved_extraction_matches_preview_and_rejects_invalid_value(self, run):
        zone = self.zone(
            "Title",
            transform="uppercase",
            validation_regex="ACCOUNT [A-Z]+",
        )
        for raw_text, expected_title in [
            ("account abc", "ACCOUNT ABC"),
            ("invalid", "ACCOUNT ABC"),
        ]:
            with self.subTest(raw_text=raw_text):
                run.return_value.stdout = raw_text
                preview = extract_zone_preview(self.page, zone, 100, 50, 1)
                self.assertEqual(preview["raw_text"], raw_text)
                self.assertEqual(preview["value"], raw_text.upper())
                _process_template(
                    self.document,
                    {0: self.page},
                    self.template,
                    [zone],
                    self.dirs.scratch_dir,
                )
                self.document.refresh_from_db()
                self.assertEqual(self.document.title, expected_title)


class TestCombineFieldValue(SimpleTestCase):
    def test_default_format_preserves_zone_order_and_duplicate_names(self):
        zones = [("Same", value) for value in ["one", None, "two"]]
        self.assertEqual(_combine_field_value("", zones), "one two")

    def test_format_preserves_existing_missing_token_cleanup(self):
        zones = [
            ("First", "one"),
            ("Second", None),
        ]
        self.assertEqual(
            _combine_field_value("{ First } / {Second} / {Unknown}", zones),
            "one",
        )


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

    def test_strip_punctuation(self):
        self.assertEqual(
            _apply_transform(" -- Account #123. -- ", "strip_punctuation"),
            "Account #123",
        )

    def test_invalid_iso_date_is_not_transformed(self):
        self.assertEqual(_apply_transform("2026-13-32", "date"), "2026-13-32")

    @patch("documents.zone_ocr.dateparser.parse", side_effect=OverflowError)
    def test_unparseable_date_preserves_text(self, parse):
        self.assertEqual(_apply_transform("unparsable", "date"), "unparsable")

    def test_unknown_target_cannot_produce_a_field_update(self):
        self.assertIsNone(
            _prepare_field_update(OcrTemplateZone(target="unknown"), "value"),
        )


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

    def test_numeric_types_reject_malformed_numbers(self):
        for data_type in [
            CustomField.FieldDataType.FLOAT,
            CustomField.FieldDataType.MONETARY,
        ]:
            for value in ["1.2.3", "--12", "12-34", "", ".", "-", "not numeric"]:
                with self.subTest(data_type=data_type, value=value):
                    self.assertIsNone(_convert_value(value, data_type))

    def test_float_overflow_is_not_stored_as_infinity(self):
        self.assertIsNone(_convert_value("9" * 400, CustomField.FieldDataType.FLOAT))

    def test_monetary_conversion_preserves_decimal_precision(self):
        value = "12345678901234567890,12345678901234567890"
        self.assertEqual(
            _convert_value(value, CustomField.FieldDataType.MONETARY),
            value.replace(",", "."),
        )


class TestRenderPages(SimpleTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name)
        self.pdf = self.tmp_path / "document.pdf"
        self.pdf.write_bytes(b"%PDF-1.4")

    @patch("documents.zone_ocr.subprocess.run")
    def test_renders_requested_pages_in_order_and_skips_out_of_range(self, run):
        def render(args, **kwargs):
            Path(args[-1]).with_suffix(".png").write_bytes(b"rendered")

        run.side_effect = render
        pages = _render_pages(self.pdf, {-1, 0, 2, 3}, self.tmp_path, 3)
        self.assertEqual(list(pages), [0, 2])
        self.assertEqual(run.call_count, 2)
        for page, call in zip([1, 3], run.call_args_list, strict=True):
            args = call.args[0]
            self.assertIn("-singlefile", args)
            self.assertEqual(args[args.index("-f") + 1], str(page))
            self.assertEqual(args[args.index("-l") + 1], str(page))
            self.assertEqual(call.kwargs["timeout"], 60)
            self.assertTrue(call.kwargs["check"])

    @patch("documents.zone_ocr.subprocess.run")
    def test_missing_render_output_is_not_a_page(self, run):
        self.assertEqual(_render_pages(self.pdf, {0}, self.tmp_path, None), {})

    @patch("documents.zone_ocr.subprocess.run")
    def test_render_failure_does_not_prevent_other_pages(self, run):
        for error in [
            subprocess.TimeoutExpired("pdftoppm", 60),
            subprocess.CalledProcessError(1, "pdftoppm", stderr=b"failure"),
            subprocess.CalledProcessError(1, "pdftoppm"),
        ]:
            with self.subTest(error=type(error).__name__):

                def render(args, **kwargs):
                    if args[args.index("-f") + 1] == "1":
                        raise error
                    Path(args[-1]).with_suffix(".png").write_bytes(b"rendered")

                run.side_effect = render
                self.assertEqual(
                    list(_render_pages(self.pdf, {0, 1}, self.tmp_path, 2)),
                    [1],
                )

    @patch(
        "documents.zone_ocr.subprocess.run",
        side_effect=FileNotFoundError("pdftoppm"),
    )
    def test_missing_renderer_stops_without_retrying_every_page(self, run):
        self.assertEqual(_render_pages(self.pdf, {0, 1}, self.tmp_path, 2), {})
        run.assert_called_once()

    @patch("documents.zone_ocr.subprocess.run")
    def test_image_is_used_directly_only_for_first_page(self, run):
        image_path = self.tmp_path / "image.png"
        with Image.new("RGB", (10, 10)) as image:
            image.save(image_path)
        self.assertEqual(
            _render_pages(image_path, {0}, self.tmp_path, 1),
            {0: image_path},
        )
        self.assertEqual(_render_pages(image_path, {1}, self.tmp_path, 1), {})
        run.assert_not_called()


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

    def test_prefers_archive_and_falls_back_to_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.pdf"
            archive = Path(directory) / "archive.pdf"
            source.touch()
            archive.touch()
            document = MagicMock(
                has_archive_version=True,
                archive_path=archive,
                source_path=source,
            )
            self.assertEqual(_resolve_doc_path(document, None), archive)
            archive.unlink()
            self.assertEqual(_resolve_doc_path(document, None), source)

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
