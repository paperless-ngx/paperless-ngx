"""Tests for the zone-based OCR extraction engine."""

import subprocess
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.test import TestCase
from PIL import Image
from pytest_mock import MockerFixture

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


class TestCombineFieldValue:
    @pytest.mark.parametrize(
        ("fmt", "zones", "expected"),
        [
            pytest.param(
                "",
                [("Same", "one"), ("Same", None), ("Same", "two")],
                "one two",
                id="default-format-preserves-zone-order-and-duplicate-names",
            ),
            pytest.param(
                "{ First } / {Second} / {Unknown}",
                [("First", "one"), ("Second", None)],
                "one",
                id="format-preserves-existing-missing-token-cleanup",
            ),
        ],
    )
    def test_combine_field_value(
        self,
        fmt: str,
        zones: list[tuple[str, str | None]],
        expected: str,
    ) -> None:
        """
        GIVEN:
            - A combine format and a list of (zone name, extracted value) pairs
        WHEN:
            - The zone values are combined into a single field value
        THEN:
            - The combined string matches the expected result
        """
        assert _combine_field_value(fmt, zones) == expected


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

    def test_matching_uses_the_selected_files_content(self):
        version = DocumentFactory(root_document=self.document, content="Contoso")
        contoso = self.template("Contoso", match="Contoso")

        self.assertCountEqual(
            get_templates_for_document(self.document),
            [self.mine, self.unowned],
        )
        self.assertEqual(get_templates_for_document(version), [contoso])

    def test_superuser_owner_can_use_all_visible_templates(self):
        self.owner.is_superuser = True
        self.assertCountEqual(
            get_templates_for_document(self.document),
            [self.mine, self.unowned, self.private],
        )

    def test_requester_limits_the_owners_templates(self):
        """
        GIVEN:
            - Templates owned by the document owner, unowned, private to
              another user, and owned by the owner but shared with the requester
        WHEN:
            - Templates are selected for a manual run by the requester
        THEN:
            - Only templates both the owner and the requester can view are used
        """
        shared = self.template("Shared", owner=self.owner)
        grant_object(self.other, shared, "view_ocrtemplate")

        self.assertCountEqual(
            get_templates_for_document(self.document, requester=self.other),
            [self.unowned, shared],
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


class TestApplyTransform:
    """Tests for the _apply_transform function."""

    @pytest.mark.parametrize(
        ("text", "transform", "date_format", "expected"),
        [
            pytest.param("  hello  ", "strip", "", "hello", id="strip"),
            pytest.param("  hello  ", "none", "", "hello", id="none-transform"),
            pytest.param(
                "hello world",
                "uppercase",
                "",
                "HELLO WORLD",
                id="uppercase",
            ),
            pytest.param(
                "HELLO WORLD",
                "lowercase",
                "",
                "hello world",
                id="lowercase",
            ),
            pytest.param(
                "Invoice 2026-001",
                "numeric",
                "",
                "2026-001",
                id="numeric-basic",
            ),
            pytest.param(
                "\u20ac1,234.56",
                "numeric",
                "",
                "1,234.56",
                id="numeric-with-currency",
            ),
            pytest.param(
                "abc",
                "numeric",
                "",
                "abc",
                id="numeric-empty-result-falls-back",
            ),
            pytest.param(
                "13.04.2026",
                "date",
                "%d.%m.%Y",
                "2026-04-13",
                id="date-with-format-dotted",
            ),
            pytest.param(
                "01/12/2025",
                "date",
                "%d/%m/%Y",
                "2025-12-01",
                id="date-with-format-slashed",
            ),
            pytest.param(
                "13.04.26",
                "date",
                "%d.%m.%y",
                "2026-04-13",
                id="date-two-digit-year",
            ),
            pytest.param(
                "2026-04-13",
                "date",
                "",
                "2026-04-13",
                id="date-auto-detect-iso",
            ),
            pytest.param(
                "2026/04/13",
                "date",
                "",
                "2026-04-13",
                id="date-auto-detect-slashed",
            ),
            pytest.param(
                "13 April 2026",
                "date",
                "",
                "2026-04-13",
                id="date-auto-detect-month-name",
            ),
            pytest.param(
                "2026-04-13",
                "date",
                "%d.%m.%Y",
                "2026-04-13",
                id="date-format-mismatch-falls-back-to-auto-detect",
            ),
            pytest.param(
                "32.13.2026",
                "date",
                "%d.%m.%Y",
                "32.13.2026",
                id="date-invalid-with-format-returns-text",
            ),
            pytest.param(
                "2026-13-32",
                "date",
                "",
                "2026-13-32",
                id="date-invalid-auto-detect-returns-text",
            ),
            pytest.param(
                "not a date",
                "date",
                "",
                "not a date",
                id="date-not-a-date-returns-text",
            ),
            pytest.param("", "strip", "", "", id="empty-string"),
            pytest.param("   ", "strip", "", "", id="whitespace-only"),
            pytest.param(
                "  hello  ",
                "unknown",
                "",
                "hello",
                id="unknown-transform-strips",
            ),
            pytest.param(
                " -- Account #123. -- ",
                "strip_punctuation",
                "",
                "Account #123",
                id="strip-punctuation",
            ),
            pytest.param(
                "2026-13-32",
                "date",
                "",
                "2026-13-32",
                id="invalid-iso-date-is-not-transformed",
            ),
        ],
    )
    def test_apply_transform(
        self,
        text: str,
        transform: str,
        date_format: str,
        expected: str,
    ) -> None:
        """
        GIVEN:
            - Extracted text, a transform name and an optional date format
        WHEN:
            - The transform is applied
        THEN:
            - The transformed text matches the expected result
        """
        assert _apply_transform(text, transform, date_format) == expected

    def test_unparseable_date_preserves_text(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - dateparser raises OverflowError for the input
        WHEN:
            - A date transform is applied
        THEN:
            - The original text is returned unchanged
        """
        mocker.patch("documents.zone_ocr.dateparser.parse", side_effect=OverflowError)
        assert _apply_transform("unparsable", "date") == "unparsable"

    def test_unknown_target_cannot_produce_a_field_update(self) -> None:
        """
        GIVEN:
            - A zone whose target is not a known target
        WHEN:
            - A field update is prepared for it
        THEN:
            - No field update is produced
        """
        assert _prepare_field_update(OcrTemplateZone(target="unknown"), "value") is None


class TestConvertValue:
    """Tests for the _convert_value function."""

    @pytest.mark.parametrize(
        ("value", "data_type", "expected"),
        [
            pytest.param(
                "Hello",
                CustomField.FieldDataType.STRING,
                "Hello",
                id="string",
            ),
            pytest.param(
                "https://example.com",
                CustomField.FieldDataType.URL,
                "https://example.com",
                id="url",
            ),
            pytest.param(
                "x" * 500,
                CustomField.FieldDataType.LONG_TEXT,
                "x" * 500,
                id="long-text",
            ),
            pytest.param("42", CustomField.FieldDataType.INT, 42, id="int-simple"),
            pytest.param(
                "INV-123",
                CustomField.FieldDataType.INT,
                123,
                id="int-with-noise",
            ),
            pytest.param("-42", CustomField.FieldDataType.INT, -42, id="int-negative"),
            pytest.param(
                "2026-04-13",
                CustomField.FieldDataType.DATE,
                "2026-04-13",
                id="date-iso",
            ),
            pytest.param(
                "123.45",
                CustomField.FieldDataType.MONETARY,
                "123.45",
                id="monetary-simple",
            ),
            pytest.param(
                "1.234,56",
                CustomField.FieldDataType.MONETARY,
                "1234.56",
                id="monetary-european",
            ),
            pytest.param(
                "\u20ac1,234.56",
                CustomField.FieldDataType.MONETARY,
                "1234.56",
                id="monetary-with-currency-symbol",
            ),
            pytest.param(
                "12345678901234567890,12345678901234567890",
                CustomField.FieldDataType.MONETARY,
                "12345678901234567890.12345678901234567890",
                id="monetary-preserves-decimal-precision",
            ),
        ],
    )
    def test_converts_to_exact_value(
        self,
        value: str,
        data_type: str,
        expected: object,
    ) -> None:
        """
        GIVEN:
            - An extracted string and a custom field data type
        WHEN:
            - The value is converted
        THEN:
            - The converted value equals the expected value exactly
        """
        assert _convert_value(value, data_type) == expected

    def test_string_truncation(self) -> None:
        """
        GIVEN:
            - An extracted string longer than the string field limit
        WHEN:
            - The value is converted to a STRING field value
        THEN:
            - The result is truncated to 128 characters
        """
        result = _convert_value("x" * 200, CustomField.FieldDataType.STRING)
        assert isinstance(result, str)
        assert len(result) == 128

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("1234.56", 1234.56, id="float-simple"),
            pytest.param("1.234,56", 1234.56, id="float-european-format"),
            pytest.param("1,234.56", 1234.56, id="float-us-format"),
            pytest.param("1234,56", 1234.56, id="float-comma-only"),
        ],
    )
    def test_float_conversion(self, value: str, expected: float) -> None:
        """
        GIVEN:
            - A numeric string in one of several decimal formats
        WHEN:
            - The value is converted to a FLOAT field value
        THEN:
            - The result is the expected float
        """
        assert _convert_value(value, CustomField.FieldDataType.FLOAT) == expected

    @pytest.mark.parametrize(
        ("value", "data_type"),
        [
            pytest.param(
                "abc",
                CustomField.FieldDataType.INT,
                id="int-empty-returns-none",
            ),
            pytest.param(
                "-",
                CustomField.FieldDataType.INT,
                id="int-only-dash-returns-none",
            ),
            pytest.param(
                "abc",
                CustomField.FieldDataType.FLOAT,
                id="float-empty-returns-none",
            ),
            pytest.param(
                ",",
                CustomField.FieldDataType.FLOAT,
                id="float-only-separator-returns-none",
            ),
            pytest.param(
                "not a date",
                CustomField.FieldDataType.DATE,
                id="date-invalid-returns-none",
            ),
            pytest.param(
                "2026-13-32",
                CustomField.FieldDataType.DATE,
                id="date-invalid-values-returns-none",
            ),
            pytest.param(
                "CHF",
                CustomField.FieldDataType.MONETARY,
                id="monetary-empty-returns-none",
            ),
            pytest.param(
                "maybe",
                CustomField.FieldDataType.BOOL,
                id="bool-unknown-returns-none",
            ),
            pytest.param(
                "test",
                CustomField.FieldDataType.DOCUMENTLINK,
                id="unsupported-type-documentlink-returns-none",
            ),
            pytest.param(
                "test",
                CustomField.FieldDataType.SELECT,
                id="unsupported-type-select-returns-none",
            ),
            pytest.param(
                "",
                CustomField.FieldDataType.STRING,
                id="empty-string-returns-none",
            ),
            pytest.param(
                "9" * 400,
                CustomField.FieldDataType.FLOAT,
                id="float-overflow-is-not-stored-as-infinity",
            ),
        ],
    )
    def test_returns_none(self, value: str, data_type: str) -> None:
        """
        GIVEN:
            - A value that cannot be converted to the given data type
        WHEN:
            - The value is converted
        THEN:
            - None is returned
        """
        assert _convert_value(value, data_type) is None

    @pytest.mark.parametrize(
        "data_type",
        [
            pytest.param(CustomField.FieldDataType.FLOAT, id="float"),
            pytest.param(CustomField.FieldDataType.MONETARY, id="monetary"),
        ],
    )
    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("1.2.3", id="multiple-dots"),
            pytest.param("--12", id="double-leading-dash"),
            pytest.param("12-34", id="embedded-dash"),
            pytest.param("", id="empty"),
            pytest.param(".", id="only-dot"),
            pytest.param("-", id="only-dash"),
            pytest.param("not numeric", id="not-numeric"),
        ],
    )
    def test_numeric_types_reject_malformed_numbers(
        self,
        data_type: str,
        value: str,
    ) -> None:
        """
        GIVEN:
            - A malformed numeric string and a FLOAT or MONETARY data type
        WHEN:
            - The value is converted
        THEN:
            - None is returned
        """
        assert _convert_value(value, data_type) is None

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("true", id="true"),
            pytest.param("True", id="true-titlecase"),
            pytest.param("yes", id="yes"),
            pytest.param("1", id="one"),
            pytest.param("ja", id="ja"),
            pytest.param("x", id="x-lowercase"),
            pytest.param("X", id="x-uppercase"),
        ],
    )
    def test_bool_true(self, value: str) -> None:
        """
        GIVEN:
            - A string that represents a true boolean
        WHEN:
            - The value is converted to a BOOL field value
        THEN:
            - The result is True
        """
        assert _convert_value(value, CustomField.FieldDataType.BOOL) is True

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("false", id="false"),
            pytest.param("False", id="false-titlecase"),
            pytest.param("no", id="no"),
            pytest.param("0", id="zero"),
            pytest.param("nein", id="nein"),
        ],
    )
    def test_bool_false(self, value: str) -> None:
        """
        GIVEN:
            - A string that represents a false boolean
        WHEN:
            - The value is converted to a BOOL field value
        THEN:
            - The result is False
        """
        assert _convert_value(value, CustomField.FieldDataType.BOOL) is False


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


class TestDetectMime:
    """Tests for _detect_mime."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            pytest.param("test.pdf", "application/pdf", id="pdf-extension"),
            pytest.param("test.png", "image/png", id="png-extension"),
            pytest.param("test.jpg", "image/jpeg", id="jpg-extension"),
            pytest.param("test.xyz", None, id="unknown-extension"),
            pytest.param("test.webp", "image/webp", id="webp-extension"),
        ],
    )
    def test_detect_mime(self, filename: str, expected: str | None) -> None:
        """
        GIVEN:
            - A path with a given file extension
        WHEN:
            - The MIME type is detected
        THEN:
            - The expected MIME type, or None for an unknown extension, is returned
        """
        assert _detect_mime(Path(filename)) == expected


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
