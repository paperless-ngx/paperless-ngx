"""Tests for the zone-based OCR extraction engine."""

from __future__ import annotations

import shutil
import subprocess
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

import pytest
from babel import Locale
from django.contrib.auth.models import Group
from PIL import Image

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import MatchingModel
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.parsers import ParseError
from documents.zone_ocr import MAX_PARSED_TEXT_LENGTH
from documents.zone_ocr import _apply_transform
from documents.zone_ocr import _combine_field_value
from documents.zone_ocr import _convert_value
from documents.zone_ocr import _crop_zone
from documents.zone_ocr import _date_rules
from documents.zone_ocr import _detect_mime
from documents.zone_ocr import _extract_zone
from documents.zone_ocr import _number_locale
from documents.zone_ocr import _parse_date
from documents.zone_ocr import _parse_monetary
from documents.zone_ocr import _parse_number
from documents.zone_ocr import _prepare_field_update
from documents.zone_ocr import _process_template
from documents.zone_ocr import _render_pages
from documents.zone_ocr import _resolve_doc_path
from documents.zone_ocr import _zone_language
from documents.zone_ocr import extract_zone_preview
from documents.zone_ocr import get_templates_for_document
from documents.zone_ocr import run_zone_extraction
from paperless_testing.factories import CustomFieldFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import OcrTemplateFactory
from paperless_testing.factories import OcrTemplateZoneFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_object

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock

    from django.contrib.auth.models import User
    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture

    from paperless_testing.dirs import PaperlessDirs


EN = Locale.parse("en")
DE = Locale.parse("de")
ENG_DATES = _date_rules("eng")
FR = Locale.parse("fr")


def make_template(name: str, **kwargs: Any) -> OcrTemplate:
    """Build a saved template, 100x50 by default."""
    kwargs.setdefault("source_width", 100)
    kwargs.setdefault("source_height", 50)
    return OcrTemplateFactory(name=name, **kwargs)


def make_zone(
    template: OcrTemplate,
    name: str,
    target: str = OcrTemplateZone.TargetType.TITLE,
    **kwargs: Any,
) -> OcrTemplateZone:
    """Build a 20x10 zone at the origin of the template."""
    return OcrTemplateZoneFactory(
        template=template,
        name=name,
        target=target,
        width=20,
        height=10,
        **kwargs,
    )


def ocr_outputs(*values: str) -> list[subprocess.CompletedProcess[str]]:
    """Build one successful fake OCR process result per extracted text."""
    return [
        subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
        for value in values
    ]


def make_visible_template(name: str, **kwargs: Any) -> OcrTemplate:
    """Build a 100x100 template matching "Northwind"."""
    kwargs.setdefault("match", "Northwind")
    kwargs.setdefault("source_height", 100)
    return make_template(name, **kwargs)


class TestZoneExtraction:
    """Tests for single-zone cropping, extraction and preview."""

    @pytest.fixture
    def page(self, tmp_path: Path) -> Path:
        page = tmp_path / "page.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.paste("black", (20, 10, 60, 30))
            image.save(page)
        return page

    @pytest.fixture
    def zone(self) -> OcrTemplateZone:
        return OcrTemplateZone(
            name="Account",
            x=10,
            y=5,
            width=20,
            height=10,
            transform="uppercase",
            ocr_language="eng",
        )

    @pytest.fixture(autouse=True)
    def scratch_dir(self, settings: SettingsWrapper, tmp_path: Path) -> None:
        settings.SCRATCH_DIR = tmp_path

    def test_crop_scales_coordinates(
        self,
        page: Path,
        zone: OcrTemplateZone,
    ) -> None:
        """
        GIVEN:
            - A zone and a page image rendered at a different size than the zone's
        WHEN:
            - The zone is cropped
        THEN:
            - The zone coordinates are scaled to the image and the crop is black
        """
        with _crop_zone(page, zone, 100, 50) as cropped:
            assert cropped.size == (40, 20)
            assert cropped.getextrema() == ((0, 0), (0, 0), (0, 0))

    def test_crop_defaults_to_image_dimensions(
        self,
        page: Path,
        zone: OcrTemplateZone,
    ) -> None:
        """
        GIVEN:
            - A zone and a page with unknown (zero) reference dimensions
        WHEN:
            - The zone is cropped
        THEN:
            - The image's own dimensions are used for the crop
        """
        with _crop_zone(page, zone, 0, 0) as cropped:
            assert cropped.size == (20, 10)
            assert cropped.getpixel((0, 0)) == (255, 255, 255)
            assert cropped.getpixel((19, 9)) == (0, 0, 0)

    def test_crop_clamps_to_image(
        self,
        page: Path,
        zone: OcrTemplateZone,
    ) -> None:
        """
        GIVEN:
            - A zone that extends past the edge of the page image
        WHEN:
            - The zone is cropped
        THEN:
            - The crop is clamped to the image bounds
        """
        zone.x, zone.y = 90, 40
        with _crop_zone(page, zone, 100, 50) as cropped:
            assert cropped.size == (20, 20)

    def test_tiny_crop_skips_reader(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A zone with zero width
        WHEN:
            - The zone is extracted
        THEN:
            - No text or value is returned and the reader is never run
        """
        zone.width = 0
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text is None
        assert result.value is None
        mock_zone_ocr_run.assert_not_called()

    def test_unreadable_image_skips_reader(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A page file that is not a valid image
        WHEN:
            - The zone is extracted
        THEN:
            - No text or value is returned and the reader is never run
        """
        page.write_bytes(b"not an image")
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text is None
        assert result.value is None
        mock_zone_ocr_run.assert_not_called()

    def test_text_extraction_retains_raw_text_and_transforms(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A zone with an uppercase transform and a reader returning padded text
        WHEN:
            - The zone is extracted
        THEN:
            - The reader receives the cropped image with the expected arguments
            - The stripped raw text is retained and the transformed value returned
        """

        def read_crop(
            args: list[str],
            **kwargs: Any,
        ) -> subprocess.CompletedProcess[str]:
            with Image.open(args[1]) as crop:
                assert crop.size == (40, 20)
                assert crop.getpixel((0, 0)) == (0, 0, 0)
            return subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="  account abc\n",
                stderr="",
            )

        mock_zone_ocr_run.side_effect = read_crop
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text == "account abc"
        assert result.value == "ACCOUNT ABC"
        assert mock_zone_ocr_run.call_args.args[0][-4:] == ["-l", "eng", "--psm", "6"]
        assert mock_zone_ocr_run.call_args.kwargs["timeout"] == 30

    def test_no_text_returns_no_value(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A reader that returns only whitespace
        WHEN:
            - The zone is extracted
        THEN:
            - No text or value is returned
        """
        mock_zone_ocr_run.return_value.stdout = " \n"
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text is None
        assert result.value is None

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(subprocess.TimeoutExpired("tesseract", 30), id="timeout"),
            pytest.param(
                subprocess.CalledProcessError(1, "tesseract", stderr="failure"),
                id="called-process-error-with-stderr",
            ),
            pytest.param(
                subprocess.CalledProcessError(1, "tesseract"),
                id="called-process-error-without-stderr",
            ),
        ],
    )
    def test_reader_failures_return_no_value(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
        error: Exception,
    ) -> None:
        """
        GIVEN:
            - A reader that fails with a timeout or process error
        WHEN:
            - The zone is extracted
        THEN:
            - No text or value is returned
        """
        mock_zone_ocr_run.side_effect = error
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text is None
        assert result.value is None

    @pytest.mark.parametrize(
        "reader_kwargs",
        [
            pytest.param(
                {"side_effect": RuntimeError("reader failed")},
                id="reader-raises",
            ),
            pytest.param({"return_value": []}, id="nothing-found"),
        ],
    )
    def test_barcode_without_value_returns_no_value(
        self,
        mocker: MockerFixture,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        reader_kwargs: dict[str, Any],
    ) -> None:
        """
        GIVEN:
            - A QR code zone and a barcode reader that either raises or finds
              no barcode
        WHEN:
            - The zone is extracted
        THEN:
            - No text or value is returned
        """
        mocker.patch("zxingcpp.read_barcodes", **reader_kwargs)
        zone.transform = "qr_code"
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text is None
        assert result.value is None

    @pytest.mark.parametrize(
        ("attribute", "value"),
        [
            pytest.param("width", 0, id="zero-width"),
            pytest.param("page", 2, id="unavailable-page"),
        ],
    )
    def test_preview_unreadable_zone_returns_empty_result(
        self,
        page: Path,
        zone: OcrTemplateZone,
        mock_zone_ocr_run: MagicMock,
        attribute: str,
        value: int,
    ) -> None:
        """
        GIVEN:
            - A zone that cannot be read, either because its crop has zero
              width or because it targets a page that is not available
        WHEN:
            - A preview is requested
        THEN:
            - An empty result is returned and the reader is never run
        """
        setattr(zone, attribute, value)
        assert extract_zone_preview(page, zone, 100, 50, 1) == {
            "raw_text": None,
            "value": None,
        }
        mock_zone_ocr_run.assert_not_called()

    def test_date_transform_uses_zone_format(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A date zone with a custom date format
        WHEN:
            - The zone is extracted from text in that format
        THEN:
            - The raw text is retained and the value is an ISO date
        """
        zone.transform = "date"
        zone.date_format = "%d/%m/%Y"
        mock_zone_ocr_run.return_value.stdout = "25/12/2025"
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text == "25/12/2025"
        assert result.value == "2025-12-25"

    @pytest.mark.parametrize(
        ("transform", "text"),
        [
            pytest.param("date", "not a date", id="date"),
            pytest.param("numeric", "abc", id="numeric"),
        ],
    )
    def test_failed_transform_yields_no_value(
        self,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
        transform: str,
        text: str,
    ) -> None:
        """
        GIVEN:
            - A date or numeric zone reading text with no date or number
        WHEN:
            - The zone is extracted
        THEN:
            - The raw text is retained for the preview and there is no value
        """
        zone.transform = transform
        mock_zone_ocr_run.return_value.stdout = text
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text == text
        assert result.value is None

    def test_barcode_extraction_bypasses_tesseract(
        self,
        mocker: MockerFixture,
        page: Path,
        zone: OcrTemplateZone,
        tmp_path: Path,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A QR code zone and a barcode reader returning padded text
        WHEN:
            - The zone is extracted
        THEN:
            - The barcode reader receives the cropped image
            - The raw text is kept as read and the value is stripped
            - The text reader is never run and the image is closed afterwards
        """
        read_barcodes = mocker.patch("zxingcpp.read_barcodes")
        zone.transform = "qr_code"

        def read_crop(image: Image.Image) -> list[MagicMock]:
            assert image.size == (40, 20)
            assert image.getpixel((0, 0)) == (0, 0, 0)
            return [mocker.MagicMock(text="  https://example.com  ")]

        read_barcodes.side_effect = read_crop
        result = _extract_zone(page, zone, 100, 50, tmp_path)
        assert result.raw_text == "  https://example.com  "
        assert result.value == "https://example.com"
        mock_zone_ocr_run.assert_not_called()
        with pytest.raises(ValueError):
            read_barcodes.call_args.args[0].getpixel((0, 0))

    def test_preview_uses_image_dimensions_without_writing(
        self,
        page: Path,
        zone: OcrTemplateZone,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A zone and a reader returning text
        WHEN:
            - A preview is requested with unknown (zero) reference dimensions
        THEN:
            - The raw text and transformed value are returned
        """
        mock_zone_ocr_run.return_value.stdout = "account abc"
        assert extract_zone_preview(page, zone, 0, 0, 1) == {
            "raw_text": "account abc",
            "value": "ACCOUNT ABC",
        }


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestSavedZoneExtraction:
    """Tests for extracting zones from a saved template and writing the results."""

    @pytest.fixture
    def page(self, paperless_dirs: PaperlessDirs) -> Path:
        page = paperless_dirs.scratch_dir / "page.png"
        with Image.new("RGB", (200, 100), "white") as image:
            image.save(page)
        return page

    @pytest.fixture
    def document(self) -> Document:
        return DocumentFactory(title="Original")

    @pytest.fixture
    def template(self) -> OcrTemplate:
        return make_template("Account")

    def test_combines_zones_and_writes_each_field_once(
        self,
        mocker: MockerFixture,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Two title zones and a combine format that joins them
        WHEN:
            - The template is processed
        THEN:
            - The combined value is written to the title with a single save
        """
        zones = [make_zone(template, "First"), make_zone(template, "Second")]
        template.combine_formats = {"title": "{Second} / {First}"}
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout="one", stderr=""),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="two", stderr=""),
        ]
        save = mocker.patch.object(document, "save", wraps=document.save)

        _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        document.refresh_from_db()
        assert document.title == "two / one"
        save.assert_called_once_with(update_fields=["title"])

    def test_failed_transform_blocks_the_combined_field(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Two title zones combined as "{Date} {Ref}", where the date zone
              reads text that is not a date
        WHEN:
            - The template is processed
        THEN:
            - The date zone is reported as transform_failed, the other zone as
              incomplete, and the title is not written
        """
        zones = [
            make_zone(template, "Date", transform="date"),
            make_zone(template, "Ref"),
        ]
        template.combine_formats = {"title": "{Date} {Ref}"}
        mock_zone_ocr_run.side_effect = ocr_outputs("not a date", "R-1")

        results = _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        assert [(result.zone, result.reason) for result in results] == [
            ("Date", "transform_failed"),
            ("Ref", "incomplete"),
        ]
        document.refresh_from_db()
        assert document.title == "Original"

    def test_converts_custom_and_builtin_fields_before_saving(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Zones for the title, ASN, created date and a boolean custom field
        WHEN:
            - The template is processed
        THEN:
            - Each raw value is converted to its field type and saved
        """
        field = CustomFieldFactory(name="Paid", data_type="boolean")
        zones = [
            make_zone(template, "Title"),
            make_zone(template, "ASN", "asn"),
            make_zone(template, "Created", "created"),
            make_zone(template, "Paid", "custom_field", custom_field=field),
        ]
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in ["New title", "ASN 42", "2026-04-13", "no"]
        ]

        _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        document.refresh_from_db()
        assert document.title == "New title"
        assert document.archive_serial_number == 42
        assert document.created == date(2026, 4, 13)
        assert not document.custom_fields.get(field=field).value

    def test_invalid_field_values_preserve_existing_values(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A document with an existing custom field value
            - Zones whose ASN, created date and custom field values are invalid
              or unassigned
        WHEN:
            - The template is processed
        THEN:
            - Only the valid title is written and the other values are preserved
        """
        field = CustomFieldFactory(name="Number", data_type="integer")
        CustomFieldInstance.objects.create(
            document=document,
            field=field,
            value_int=12,
        )
        zones = [
            make_zone(template, "Title"),
            make_zone(template, "ASN", "asn"),
            make_zone(template, "Created", "created"),
            make_zone(template, "Number", "custom_field", custom_field=field),
            make_zone(template, "Unassigned", "custom_field"),
        ]
        original_created = document.created
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in [
                "Valid",
                "9999999999999999999999999999999",
                "invalid",
                "abc",
                "text",
            ]
        ]

        _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        document.refresh_from_db()
        assert document.title == "Valid"
        assert document.archive_serial_number is None
        assert document.created == original_created
        assert document.custom_fields.get(field=field).value == 12

    def test_write_failure_rolls_back_template_and_restores_document(
        self,
        mocker: MockerFixture,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A title zone and a custom field zone
            - A document save that raises after writing
        WHEN:
            - The template is processed
        THEN:
            - The error propagates, the write is rolled back and the in-memory
              document is restored
        """
        field = CustomFieldFactory(name="Number", data_type="integer")
        zones = [
            make_zone(template, "Title"),
            make_zone(template, "Number", "custom_field", custom_field=field),
        ]
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="New title",
                stderr="",
            ),
            subprocess.CompletedProcess(args=[], returncode=0, stdout="42", stderr=""),
        ]
        save = document.save

        def fail_after_save(**kwargs: Any) -> None:
            save(**kwargs)
            raise RuntimeError("save failed")

        mocker.patch.object(document, "save", side_effect=fail_after_save)

        with pytest.raises(RuntimeError, match="save failed"):
            _process_template(
                document,
                {0: page},
                template,
                zones,
                paperless_dirs.scratch_dir,
            )

        assert document.title == "Original"
        document.refresh_from_db()
        assert document.title == "Original"
        assert not document.custom_fields.exists()

    def test_last_successful_template_wins(
        self,
        mock_zone_ocr_run: MagicMock,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Three templates writing the title, the last of which rejects its value
        WHEN:
            - Zone extraction runs over all of them
        THEN:
            - The title comes from the last template that produced a value
        """
        make_zone(template, "First")
        second = make_template("Second")
        make_zone(second, "Second")
        third = make_template("Third")
        make_zone(third, "Third", validation_regex="accepted")
        templates = list(OcrTemplate.objects.order_by("pk"))
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in ["First", "Second", "rejected"]
        ]

        run_zone_extraction(document, page, templates=templates)

        document.refresh_from_db()
        assert document.title == "Second"

    def test_document_run_renders_each_page_once_across_templates(
        self,
        mocker: MockerFixture,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Two templates with zones on the first, last and second page of a
              two page document
        WHEN:
            - Zone extraction runs over both templates
        THEN:
            - Each page is rendered only once and the rendered files are removed
        """
        document.page_count = 2
        make_zone(template, "First", page=1)
        make_zone(template, "Last", page=-1)
        second = make_template("Second")
        make_zone(second, "Last again", page=2)
        pdf = paperless_dirs.scratch_dir / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        rendered = []

        def render(in_path: Path, out_path: Path, **kwargs: Any) -> None:
            with Image.new("RGB", (100, 50), "white") as image:
                image.save(out_path)
            rendered.append(out_path)

        mock_rasterize = mocker.patch(
            "documents.zone_ocr.rasterize_pdf_page_to_png",
            side_effect=render,
        )
        mock_zone_ocr_run.return_value = subprocess.CompletedProcess(
            [],
            0,
            stdout="extracted",
        )

        results = run_zone_extraction(document, pdf, templates=[template, second])

        assert [call.kwargs["page"] for call in mock_rasterize.call_args_list] == [1, 2]
        assert [result.reason for result in results] == [None, None, None]
        assert not any(path.exists() for path in rendered)

    def test_zone_dimensions_override_template_dimensions(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A zone with its own source dimensions, differing from the template's
        WHEN:
            - The template is processed
        THEN:
            - The zone is cropped using the zone's dimensions
        """
        zone = make_zone(
            template,
            "Title",
            zone_source_width=200,
            zone_source_height=100,
        )

        def read_crop(
            args: list[str],
            **kwargs: Any,
        ) -> subprocess.CompletedProcess[str]:
            with Image.open(args[1]) as crop:
                assert crop.size == (20, 10)
            return subprocess.CompletedProcess(args, 0, stdout="extracted")

        mock_zone_ocr_run.side_effect = read_crop

        _process_template(
            document,
            {0: page},
            template,
            [zone],
            paperless_dirs.scratch_dir,
        )

        assert document.title == "extracted"

    def test_missing_page_returns_skipped_result(
        self,
        paperless_dirs: PaperlessDirs,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A zone on the last page and no rendered pages
        WHEN:
            - The template is processed
        THEN:
            - The zone result is skipped as a missing page with no value
        """
        zone = make_zone(template, "Last", page=-1)

        results = _process_template(
            document,
            {},
            template,
            [zone],
            paperless_dirs.scratch_dir,
        )

        assert results[0].reason == "missing_page"
        assert results[0].value is None

    def test_missing_document_file_returns_skipped_results(
        self,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A template with a zone and no document file
        WHEN:
            - Zone extraction runs
        THEN:
            - A single result is skipped as a missing file with no value
        """
        make_zone(template, "Title")

        results = run_zone_extraction(document, None, templates=[template])

        assert len(results) == 1
        assert results[0].reason == "missing_file"
        assert results[0].value is None

    def test_empty_combination_cannot_clear_a_field(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A combine format that references an unknown zone and so is empty
        WHEN:
            - The template is processed
        THEN:
            - The result is an invalid value and the title is not cleared
        """
        zone = make_zone(template, "Title")
        template.combine_formats = {"title": "{Unknown}"}
        mock_zone_ocr_run.return_value.stdout = "extracted"

        results = _process_template(
            document,
            {0: page},
            template,
            [zone],
            paperless_dirs.scratch_dir,
        )

        assert results[0].reason == "invalid_value"
        assert results[0].value is None
        assert document.title == "Original"

    def test_skipped_results_never_report_existing_document_values(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Zones that are empty, rejected by regex, invalid or unassigned
        WHEN:
            - The template is processed
        THEN:
            - Each result carries its skip reason and no value, and the title
              is unchanged
        """
        zones = [
            make_zone(template, "Empty"),
            make_zone(template, "Rejected", validation_regex="accepted"),
            make_zone(template, "Invalid", "asn"),
            make_zone(template, "Unassigned", "custom_field"),
        ]
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in ["", "rejected", "abc", "orphan"]
        ]

        results = _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        assert [result.reason for result in results] == [
            "no_value",
            "regex_mismatch",
            "invalid_value",
            "unassigned",
        ]
        assert [result.value for result in results] == [None] * 4
        assert document.title == "Original"

    def test_failed_template_reports_rollback_and_next_template_still_runs(
        self,
        mocker: MockerFixture,
        mock_zone_ocr_run: MagicMock,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A template whose ASN is taken by another document after the
              duplicate check passed, so saving it fails
            - A second template that would succeed
        WHEN:
            - Zone extraction runs over both templates
        THEN:
            - The first template is reported as failed and rolled back, and the
              second template is still applied
        """
        mocker.patch("documents.zone_ocr._asn_in_use", return_value=False)
        DocumentFactory(archive_serial_number=42)
        make_zone(template, "Title")
        make_zone(template, "Conflict", "asn")
        second = make_template("Second")
        make_zone(second, "Second")
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in ["Rolled back", "42", "Applied"]
        ]

        results = run_zone_extraction(document, page, templates=[template, second])

        assert [result.reason for result in results] == [
            "template_failed",
            "template_failed",
            None,
        ]
        assert [result.value for result in results] == [None, None, "Applied"]
        document.refresh_from_db()
        assert document.title == "Applied"
        assert document.archive_serial_number is None

    @pytest.mark.parametrize(
        "deleted",
        [
            pytest.param(False, id="active-document"),
            pytest.param(True, id="trashed-document"),
        ],
    )
    def test_duplicate_asn_is_dropped_and_other_fields_still_written(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
        deleted: bool,  # noqa: FBT001
    ) -> None:
        """
        GIVEN:
            - A template with a title zone and an ASN zone whose value is the
              ASN of another document, active or in the trash
        WHEN:
            - The template is processed
        THEN:
            - The ASN zone is reported as duplicate_asn and the ASN is not
              written, while the title from the same template is written
        """
        other = DocumentFactory(archive_serial_number=42)
        if deleted:
            other.delete()
        make_zone(template, "Title")
        make_zone(template, "ASN", "asn")
        mock_zone_ocr_run.side_effect = ocr_outputs("New title", "42")

        results = _process_template(
            document,
            {0: page},
            template,
            list(template.zones.all()),
            paperless_dirs.scratch_dir,
        )

        assert [(result.zone, result.value, result.reason) for result in results] == [
            ("Title", "New title", None),
            ("ASN", None, "duplicate_asn"),
        ]
        document.refresh_from_db()
        assert document.title == "New title"
        assert document.archive_serial_number is None

    def test_document_keeping_its_own_asn_is_not_a_duplicate(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A document that already has ASN 42 and an ASN zone reading 42
        WHEN:
            - The template is processed
        THEN:
            - The ASN is accepted
        """
        document.archive_serial_number = 42
        document.save()
        make_zone(template, "ASN", "asn")
        mock_zone_ocr_run.side_effect = ocr_outputs("42")

        results = _process_template(
            document,
            {0: page},
            template,
            list(template.zones.all()),
            paperless_dirs.scratch_dir,
        )

        assert [(result.value, result.reason) for result in results] == [(42, None)]
        document.refresh_from_db()
        assert document.archive_serial_number == 42

    def test_literal_format_does_not_write_when_every_zone_failed(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A combine format with literal text around a zone that reads nothing
        WHEN:
            - The template is processed
        THEN:
            - The result has no value and the title is not written
        """
        zone = make_zone(template, "Title")
        template.combine_formats = {"title": "Invoice {Title}"}
        mock_zone_ocr_run.return_value.stdout = ""

        results = _process_template(
            document,
            {0: page},
            template,
            [zone],
            paperless_dirs.scratch_dir,
        )

        assert results[0].reason == "no_value"
        assert results[0].value is None
        assert document.title == "Original"

    def test_saved_extraction_matches_preview_and_rejects_invalid_value(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A zone that uppercases its text and validates it against a regex
        WHEN:
            - A valid value and then an invalid value are previewed and saved in
              turn
        THEN:
            - The preview matches the transformed text for both, the valid value
              is saved, and the invalid value leaves the saved title unchanged
        """
        zone = make_zone(
            template,
            "Title",
            transform="uppercase",
            validation_regex="ACCOUNT [A-Z]+",
        )

        def preview_and_save(raw_text: str) -> None:
            mock_zone_ocr_run.return_value.stdout = raw_text
            preview = extract_zone_preview(page, zone, 100, 50, 1)
            assert preview["raw_text"] == raw_text
            assert preview["value"] == raw_text.upper()
            _process_template(
                document,
                {0: page},
                template,
                [zone],
                paperless_dirs.scratch_dir,
            )
            document.refresh_from_db()

        preview_and_save("account abc")
        assert document.title == "ACCOUNT ABC"
        preview_and_save("invalid")
        assert document.title == "ACCOUNT ABC"

    @pytest.mark.parametrize(
        ("failing_zone", "expected_failure"),
        [
            pytest.param(
                {"validation_regex": r"\d{2}"},
                "regex_mismatch",
                id="regex-mismatch",
            ),
            pytest.param({"page": 2}, "missing_page", id="missing-page"),
        ],
    )
    def test_failed_zone_blocks_combined_field(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
        failing_zone: dict[str, Any],
        expected_failure: str,
    ) -> None:
        """
        GIVEN:
            - Three title zones combined as a date, where the first one fails
        WHEN:
            - The template is processed
        THEN:
            - Nothing is written, the failing zone reports its own reason and
              the accepted zones report incomplete
        """
        zones = [
            make_zone(template, "Day", **failing_zone),
            make_zone(template, "Month"),
            make_zone(template, "Year"),
        ]
        template.combine_formats = {"title": "{Day}.{Month}.{Year}"}
        # A zone on a missing page is never read.
        mock_zone_ocr_run.side_effect = ocr_outputs(
            *(
                ["x", "05", "2024"]
                if "validation_regex" in failing_zone
                else ["05", "2024"]
            ),
        )

        results = _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        assert [result.reason for result in results] == [
            expected_failure,
            "incomplete",
            "incomplete",
        ]
        assert [result.value for result in results] == [None] * 3
        document.refresh_from_db()
        assert document.title == "Original"

    def test_zone_with_no_value_is_an_optional_token(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Two title zones combined with a separator, where the first reads
              nothing
        WHEN:
            - The template is processed
        THEN:
            - The remaining value is still written and reported
        """
        zones = [make_zone(template, "First"), make_zone(template, "Second")]
        template.combine_formats = {"title": "{First} / {Second}"}
        mock_zone_ocr_run.side_effect = ocr_outputs("", "two")

        results = _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        assert [result.reason for result in results] == ["no_value", None]
        assert results[1].value == "two"
        document.refresh_from_db()
        assert document.title == "two"

    def test_failed_single_zone_field_does_not_affect_other_fields(
        self,
        mock_zone_ocr_run: MagicMock,
        paperless_dirs: PaperlessDirs,
        page: Path,
        document: Document,
        template: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A title zone and a separate ASN zone, where the ASN fails its
              validation regex
        WHEN:
            - The template is processed
        THEN:
            - The title is written and the failing zone keeps regex_mismatch
        """
        zones = [
            make_zone(template, "Title"),
            make_zone(template, "ASN", "asn", validation_regex=r"\d+"),
        ]
        mock_zone_ocr_run.side_effect = ocr_outputs("New title", "abc")

        results = _process_template(
            document,
            {0: page},
            template,
            zones,
            paperless_dirs.scratch_dir,
        )

        assert [result.reason for result in results] == [None, "regex_mismatch"]
        document.refresh_from_db()
        assert document.title == "New title"


class TestCombineFieldValue:
    """Tests for combining zone values into one field value."""

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
            pytest.param(
                "{Amount}",
                [("Amount", "-12.50")],
                "-12.50",
                id="negative-amount-sign-kept",
            ),
            pytest.param(
                "{Url}",
                [("Url", "http://x.com/a//b")],
                "http://x.com/a//b",
                id="url-double-slash-kept-verbatim",
            ),
            pytest.param(
                "{Value}",
                [("Value", "A--B")],
                "A--B",
                id="repeated-punctuation-in-value-kept",
            ),
            pytest.param(
                "{Name}",
                [("Name", "Dr. Smith Jr.")],
                "Dr. Smith Jr.",
                id="trailing-period-in-value-kept",
            ),
            pytest.param(
                "{Value}",
                [("Value", "wait...")],
                "wait...",
                id="trailing-ellipsis-in-value-kept",
            ),
            pytest.param(
                "{A} / {B} / {C}",
                [("A", "a"), ("B", None), ("C", "c")],
                "a / c",
                id="middle-empty-token-drops-one-separator",
            ),
            pytest.param(
                "{A} / {B} / {C}",
                [("A", None), ("B", "b"), ("C", "c")],
                "b / c",
                id="leading-empty-token-drops-leading-separator",
            ),
            pytest.param(
                "{A} / {B} / {C}",
                [("A", "a"), ("B", "b"), ("C", None)],
                "a / b",
                id="trailing-empty-token-drops-trailing-separator",
            ),
            pytest.param(
                "{A} / {B} / {C}",
                [("A", "a"), ("B", None), ("C", None)],
                "a",
                id="trailing-run-of-empty-tokens-drops-nearest-separator",
            ),
            pytest.param(
                "Total: {A} / {B}",
                [("A", None), ("B", "b")],
                "Total: b",
                id="leading-literal-kept-before-empty-first-token",
            ),
            pytest.param(
                "- {A} {B}",
                [("A", None), ("B", "b")],
                "b",
                id="leading-separator-dropped-before-empty-first-token",
            ),
            pytest.param(
                "{Day}.{Month}.{Year}",
                [("Day", "12"), ("Month", "05"), ("Year", "2024")],
                "12.05.2024",
                id="all-tokens-present",
            ),
            pytest.param(
                "INV-{Number}",
                [("Number", "123")],
                "INV-123",
                id="literal-prefix-kept-with-value",
            ),
            pytest.param(
                "INV-{Number}",
                [("Number", None)],
                "",
                id="literal-prefix-dropped-when-every-token-empty",
            ),
            pytest.param(
                "{A} / {B}",
                [("A", None), ("B", "  ")],
                "",
                id="every-token-empty",
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


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestTemplateVisibility:
    """Tests for which templates apply to a document and its requester."""

    @pytest.fixture
    def owner(self) -> User:
        return UserFactory(username="document_owner")

    @pytest.fixture
    def other(self) -> User:
        return UserFactory(username="other_owner")

    @pytest.fixture
    def document(self, owner: User) -> Document:
        return DocumentFactory(
            owner=owner,
            content="Northwind Power & Light statement",
        )

    @pytest.fixture
    def mine(self, owner: User) -> OcrTemplate:
        return make_visible_template("Mine", owner=owner)

    @pytest.fixture
    def unowned(self) -> OcrTemplate:
        return make_visible_template("Unowned")

    @pytest.fixture
    def private(self, other: User) -> OcrTemplate:
        return make_visible_template("Private", owner=other)

    @pytest.mark.usefixtures("private")
    def test_only_matching_owned_unowned_and_shared_templates_apply(
        self,
        owner: User,
        other: User,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Templates owned by the document owner, unowned, private to another
              user, shared with the owner, disabled, for another sender and
              with no matching
        WHEN:
            - Templates are selected for the document
        THEN:
            - Only the enabled, matching, owned, unowned and shared templates apply
        """
        shared = make_visible_template("Shared", owner=other)
        grant_object(owner, shared, "view_ocrtemplate")
        make_visible_template("Disabled", owner=owner, enabled=False)
        make_visible_template("Other sender", owner=owner, match="Contoso")
        make_visible_template(
            "No matching",
            owner=owner,
            matching_algorithm=MatchingModel.MATCH_NONE,
        )

        assert Counter(get_templates_for_document(document)) == Counter(
            [mine, unowned, shared],
        )

    @pytest.mark.usefixtures("mine", "unowned")
    def test_group_sharing_applies(
        self,
        owner: User,
        document: Document,
        private: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A private template shared with a group the document owner is in
        WHEN:
            - Templates are selected for the document
        THEN:
            - The group-shared template applies
        """
        group = Group.objects.create(name="OCR users")
        owner.groups.add(group)
        grant_object(group, private, "view_ocrtemplate")

        assert private in get_templates_for_document(document)

    @pytest.mark.usefixtures("mine", "private")
    def test_unowned_documents_consider_every_template(
        self,
        other: User,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
        private: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A document with no owner
            - Templates owned by two users and an unowned template
        WHEN:
            - Templates are selected for consumption, and for a manual run by
              one of the users
        THEN:
            - Consumption considers every template
            - The manual run is limited to templates the requester can view
        """
        document.owner = None

        assert Counter(get_templates_for_document(document)) == Counter(
            [mine, unowned, private],
        )
        assert Counter(
            get_templates_for_document(document, requester=other),
        ) == Counter([unowned, private])

    @pytest.mark.usefixtures("private")
    def test_versions_use_the_root_documents_owner(
        self,
        other: User,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A version document owned by another user than its root document
        WHEN:
            - Templates are selected for the version
        THEN:
            - The root document's owner decides the visible templates
        """
        version = DocumentFactory(
            root_document=document,
            owner=other,
            content=document.content,
        )

        assert Counter(get_templates_for_document(version)) == Counter(
            [mine, unowned],
        )

    @pytest.mark.usefixtures("private")
    def test_matching_uses_the_selected_files_content(
        self,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A root document and a version with different content
            - A template matching only the version's content
        WHEN:
            - Templates are selected for each
        THEN:
            - Each is matched against its own content
        """
        version = DocumentFactory(root_document=document, content="Contoso")
        contoso = make_visible_template("Contoso", match="Contoso")

        assert Counter(get_templates_for_document(document)) == Counter(
            [mine, unowned],
        )
        assert get_templates_for_document(version) == [contoso]

    def test_superuser_owner_can_use_all_visible_templates(
        self,
        owner: User,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
        private: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - A document owned by a superuser
        WHEN:
            - Templates are selected for the document
        THEN:
            - Every matching template applies, including private ones
        """
        owner.is_superuser = True

        assert Counter(get_templates_for_document(document)) == Counter(
            [mine, unowned, private],
        )

    @pytest.mark.usefixtures("mine", "private")
    def test_requester_limits_the_owners_templates(
        self,
        owner: User,
        other: User,
        document: Document,
        unowned: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Templates owned by the document owner, unowned, private to
              another user, and owned by the owner but shared with the requester
        WHEN:
            - Templates are selected for a manual run by the requester
        THEN:
            - Only templates both the owner and the requester can view are used
        """
        shared = make_visible_template("Shared", owner=owner)
        grant_object(other, shared, "view_ocrtemplate")

        assert Counter(
            get_templates_for_document(document, requester=other),
        ) == Counter([unowned, shared])

    @pytest.mark.usefixtures("mine", "unowned", "private")
    def test_inactive_owner_has_no_templates(
        self,
        owner: User,
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A document whose owner is inactive
        WHEN:
            - Templates are selected for the document
        THEN:
            - No templates apply
        """
        owner.is_active = False

        assert get_templates_for_document(document) == []

    def test_extraction_never_processes_private_templates(
        self,
        mock_zone_ocr_run: MagicMock,
        document: Document,
        mine: OcrTemplate,
        unowned: OcrTemplate,
        private: OcrTemplate,
    ) -> None:
        """
        GIVEN:
            - Owned, unowned and private templates each with a zone
            - A blank image as the document's file
        WHEN:
            - Zone extraction runs for the document
        THEN:
            - Only the owned and unowned templates report results
        """
        for template in (mine, unowned, private):
            OcrTemplateZoneFactory(
                template=template,
                name="Title",
                width=20,
                height=20,
            )
        document.mime_type = "image/png"
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        mock_zone_ocr_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="extracted",
            stderr="",
        )

        results = run_zone_extraction(document, None)

        assert Counter(result.template for result in results) == Counter(
            [mine.name, unowned.name],
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
                "",
                id="numeric-without-digits-is-empty",
            ),
            pytest.param(
                "a-b.c",
                "numeric",
                "",
                "",
                id="numeric-punctuation-only-is-empty",
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
                "",
                id="date-invalid-with-format-is-empty",
            ),
            pytest.param(
                "2026-13-32",
                "date",
                "",
                "",
                id="date-invalid-auto-detect-is-empty",
            ),
            pytest.param(
                "not a date",
                "date",
                "",
                "",
                id="date-not-a-date-is-empty",
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
            - A zone reading English
        WHEN:
            - The transform is applied
        THEN:
            - The transformed text matches the expected result
        """
        rules = _date_rules("eng", date_format)
        assert _apply_transform(text, transform, rules) == expected

    def test_dateparser_error_gives_empty_text(self, mocker: MockerFixture) -> None:
        """
        GIVEN:
            - dateparser raises OverflowError for the input
        WHEN:
            - A date transform is applied
        THEN:
            - An empty string is returned
        """
        mocker.patch("documents.zone_ocr.dateparser.parse", side_effect=OverflowError)
        assert _apply_transform("unparsable", "date", _date_rules("eng")) == ""


class TestZoneLanguage:
    """Tests for mapping the OCR language to a dateparser language."""

    @pytest.mark.parametrize(
        ("ocr_language", "expected"),
        [
            pytest.param("deu", "de", id="single-language"),
            pytest.param("deu+eng", "de", id="first-of-several-languages"),
            pytest.param("aze_Cyrl", "az", id="script-suffix-is-dropped"),
            pytest.param("xyz", None, id="unmapped-language-is-none"),
        ],
    )
    def test_zone_language(self, ocr_language: str, expected: str | None) -> None:
        """
        GIVEN:
            - A tesseract language code, possibly several or with a script
        WHEN:
            - The zone language is derived
        THEN:
            - The first language is mapped, or None when it is unknown
        """
        assert _zone_language(ocr_language) == expected


class TestParseDate:
    """Tests for the zone date parser."""

    @pytest.mark.parametrize(
        ("text", "ocr_language", "expected"),
        [
            pytest.param("12.05.2024", "deu", date(2024, 5, 12), id="german-day-first"),
            pytest.param(
                "05/12/2024",
                "eng",
                date(2024, 5, 12),
                id="english-month-first",
            ),
            pytest.param(
                "12. Mai 2024",
                "deu",
                date(2024, 5, 12),
                id="german-month-name",
            ),
            pytest.param(
                "13 April 2026",
                "eng",
                date(2026, 4, 13),
                id="english-month-name",
            ),
            pytest.param(
                "2026/04/13",
                "eng",
                date(2026, 4, 13),
                id="year-first-slashed",
            ),
            pytest.param(
                "01.01.2999",
                "deu",
                date(2999, 1, 1),
                id="future-date-allowed",
            ),
        ],
    )
    def test_locale_decides_the_order(
        self,
        text: str,
        ocr_language: str,
        expected: date,
    ) -> None:
        """
        GIVEN:
            - A date written in the convention of the zone's language
        WHEN:
            - The date is parsed
        THEN:
            - The locale's day and month order is used
        """
        assert _parse_date(text, _date_rules(ocr_language)) == expected

    @pytest.mark.parametrize(
        ("date_order", "expected"),
        [
            pytest.param("DMY", date(2024, 5, 12), id="day-first"),
            pytest.param("MDY", date(2024, 12, 5), id="month-first"),
        ],
    )
    def test_unmapped_language_uses_the_configured_date_order(
        self,
        settings: SettingsWrapper,
        date_order: str,
        expected: date,
    ) -> None:
        """
        GIVEN:
            - A zone whose language has no dateparser mapping
            - A configured PAPERLESS_DATE_ORDER
        WHEN:
            - An ambiguous numeric date is parsed
        THEN:
            - The configured date order decides the result
        """
        settings.DATE_ORDER = date_order
        assert _parse_date("12.05.2024", _date_rules("xyz")) == expected

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("now", id="now"),
            pytest.param("yesterday", id="yesterday"),
            pytest.param("today", id="today"),
            pytest.param("in 2 days", id="relative-offset"),
            pytest.param("Mon", id="weekday"),
            pytest.param("March", id="month-only"),
            pytest.param("2024", id="year-only"),
            pytest.param("5", id="day-only"),
            pytest.param("12", id="two-digits"),
            pytest.param("not a date", id="words"),
        ],
    )
    @pytest.mark.parametrize(
        "ocr_language",
        [
            pytest.param("eng", id="mapped-language"),
            pytest.param("xyz", id="unmapped-language"),
        ],
    )
    def test_non_dates_are_rejected(self, text: str, ocr_language: str) -> None:
        """
        GIVEN:
            - Text that is not a complete calendar date
        WHEN:
            - The date is parsed
        THEN:
            - No date is returned
        """
        assert _parse_date(text, _date_rules(ocr_language)) is None

    @pytest.mark.parametrize(
        ("text", "ocr_language", "expected"),
        [
            pytest.param(
                "Datum: 13.04.2026",
                "deu",
                date(2026, 4, 13),
                id="german-label-colon",
            ),
            pytest.param(
                "Rechnungsdatum 12.05.2024",
                "deu",
                date(2024, 5, 12),
                id="german-compound-label",
            ),
            pytest.param(
                "Invoice date 05/12/2024",
                "eng",
                date(2024, 5, 12),
                id="english-label-numeric",
            ),
            pytest.param(
                "Date: 13 April 2026",
                "eng",
                date(2026, 4, 13),
                id="english-label-month-name",
            ),
            pytest.param(
                "Rechnung 2024-001 vom 12.05.2024",
                "deu",
                date(2024, 5, 12),
                id="german-label-before-invoice-number",
            ),
            pytest.param(
                "No. 12 Datum 13.04.2026",
                "deu",
                date(2026, 4, 13),
                id="german-label-after-number",
            ),
            pytest.param(
                "Kd-Nr 12345 05.06.2024",
                "deu",
                date(2024, 6, 5),
                id="german-label-after-customer-number",
            ),
            pytest.param(
                "Lieferdatum: 12. Mai 2024",
                "deu",
                date(2024, 5, 12),
                id="german-label-month-name",
            ),
            pytest.param(
                "Total 5",
                "eng",
                None,
                id="single-number-after-label",
            ),
            pytest.param(
                "Total 5 items 2024",
                "eng",
                None,
                id="number-run-without-month",
            ),
            pytest.param(
                "Page 3 of 2024",
                "eng",
                None,
                id="page-number-without-month",
            ),
            pytest.param(
                "Invoice 12.5",
                "eng",
                None,
                id="partial-numeric-date",
            ),
            pytest.param(
                "Page 3 of 12 2024",
                "eng",
                None,
                id="page-of-number-run-with-year",
            ),
            pytest.param(
                "Total 3 10 2024",
                "eng",
                None,
                id="space-separated-numbers-with-year",
            ),
            pytest.param(
                "Order 12 3 2024",
                "eng",
                None,
                id="order-numbers-with-year",
            ),
            pytest.param(
                "Ref 1 2 2024",
                "eng",
                None,
                id="ref-numbers-with-year",
            ),
            pytest.param(
                "Invoice #2024 from 5 May",
                "eng",
                None,
                id="year-token-before-day-month",
            ),
            pytest.param(
                "Page 1 of 3 03 2024",
                "eng",
                None,
                id="page-numbers-ending-in-year",
            ),
            pytest.param(
                "Version 1.2.34",
                "deu",
                None,
                id="version-number-with-two-digit-tail",
            ),
            pytest.param(
                "v1.2.24",
                "eng",
                None,
                id="short-version-number",
            ),
            pytest.param(
                "Art. 12.3.45",
                "deu",
                None,
                id="article-number",
            ),
            pytest.param(
                "Ticket 1-2-34",
                "eng",
                None,
                id="dashed-ticket-number",
            ),
        ],
    )
    def test_labelled_text_yields_the_date_after_the_label(
        self,
        text: str,
        ocr_language: str,
        expected: date | None,
    ) -> None:
        """
        GIVEN:
            - OCR text with a label before a date, or a label-like number
              with no complete date
        WHEN:
            - The date is parsed
        THEN:
            - The date after the label is returned in the zone's day/month order
            - Text without a complete date after a label returns no date
        """
        assert _parse_date(text, _date_rules(ocr_language)) == expected

    @pytest.mark.parametrize(
        ("text", "date_format", "expected"),
        [
            pytest.param(
                "12.05.2024",
                "%m.%d.%Y",
                date(2024, 12, 5),
                id="format-overrides-locale-order",
            ),
            pytest.param(
                "12.05.2024",
                "%Y/%m/%d",
                date(2024, 5, 12),
                id="invalid-format-falls-back",
            ),
        ],
    )
    def test_date_format_is_tried_first(
        self,
        text: str,
        date_format: str,
        expected: date,
    ) -> None:
        """
        GIVEN:
            - A German zone with a date format
        WHEN:
            - A date is parsed
        THEN:
            - A matching format is used, otherwise parsing falls back to the locale
        """
        assert _parse_date(text, _date_rules("deu", date_format)) == expected

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param("2024-05-06", date(2024, 5, 6), id="plain-iso"),
            pytest.param("Due 2024-05-06.", date(2024, 5, 6), id="iso-inside-text"),
            pytest.param("No. 12345-06-07", None, id="digit-before-is-not-iso"),
            pytest.param("2024-05-061", None, id="digit-after-is-not-iso"),
            pytest.param(
                "2024-13-45 and 2024-05-06",
                date(2024, 5, 6),
                id="invalid-match-is-skipped",
            ),
            pytest.param("2024-13-45", None, id="only-invalid-match"),
        ],
    )
    def test_iso_dates_are_anchored(self, text: str, expected: date | None) -> None:
        """
        GIVEN:
            - Text containing ISO-like dates, some invalid or part of longer numbers
        WHEN:
            - The date is parsed
        THEN:
            - Only whole, valid ISO dates are returned, trying every match
        """
        assert _parse_date(text, _date_rules("eng")) == expected

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("2026/04/13", id="slashed"),
            pytest.param("2026.04.13", id="dotted"),
            pytest.param("2026-04-13", id="dashed"),
        ],
    )
    @pytest.mark.parametrize(
        ("ocr_language", "date_order"),
        [
            pytest.param("xyz", "DMY", id="unmapped-language-day-first"),
            pytest.param("xyz", "MDY", id="unmapped-language-month-first"),
            pytest.param("deu", "DMY", id="mapped-language"),
        ],
    )
    def test_year_first_dates_ignore_the_date_order(
        self,
        settings: SettingsWrapper,
        text: str,
        ocr_language: str,
        date_order: str,
    ) -> None:
        """
        GIVEN:
            - A year-first date separated by a dash, slash or dot
            - A mapped or unmapped zone language and a configured date order
        WHEN:
            - The date is parsed
        THEN:
            - The date is read as year, month, day regardless of the order
        """
        settings.DATE_ORDER = date_order
        assert _parse_date(text, _date_rules(ocr_language)) == date(2026, 4, 13)

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("1.2026/04/133", id="digit-after"),
            pytest.param("12026/04/13", id="digit-before"),
            pytest.param("2026/13/45", id="invalid-month"),
        ],
    )
    def test_year_first_dates_are_anchored_and_validated(self, text: str) -> None:
        """
        GIVEN:
            - Year-first looking text that is part of longer digits or invalid
        WHEN:
            - The date is parsed
        THEN:
            - No date is returned
        """
        assert _parse_date(text, _date_rules("xyz")) is None

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("1899-12-31", id="iso"),
            pytest.param("31.12.1899", id="locale-numeric"),
        ],
    )
    def test_years_before_1900_are_rejected(self, text: str) -> None:
        """
        GIVEN:
            - A valid calendar date before the year 1900
        WHEN:
            - The date is parsed
        THEN:
            - No date is returned
        """
        assert _parse_date(text, _date_rules("deu")) is None


@pytest.mark.django_db
class TestPrepareFieldUpdate:
    """Tests for converting extracted values into field updates."""

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

    @pytest.mark.parametrize(
        ("ocr_language", "expected"),
        [
            pytest.param("deu", 1234, id="german-reads-dot-as-thousands"),
            pytest.param("eng", None, id="english-reads-dot-as-fraction"),
        ],
    )
    def test_int_field_uses_the_zone_language_for_numbers(
        self,
        ocr_language: str,
        expected: int | None,
    ) -> None:
        """
        GIVEN:
            - A zone targeting an integer custom field with a given OCR language
        WHEN:
            - A field update is prepared for the text "1.234"
        THEN:
            - A German zone reads 1234, while an English zone reads a fraction
              and produces no update
        """
        field = CustomFieldFactory(data_type=CustomField.FieldDataType.INT)
        zone = OcrTemplateZoneFactory(
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=field,
            ocr_language=ocr_language,
        )

        update = _prepare_field_update(zone, "1.234")

        assert (update.value if update else None) == expected

    @pytest.mark.parametrize(
        ("data_type", "text", "expected"),
        [
            pytest.param(
                CustomField.FieldDataType.STRING,
                "x" * 128,
                "x" * 128,
                id="string-at-the-limit",
            ),
            pytest.param(
                CustomField.FieldDataType.STRING,
                "x" * 129,
                None,
                id="string-over-the-limit",
            ),
            pytest.param(
                CustomField.FieldDataType.URL,
                "https://example.com/" + "a" * 150,
                "https://example.com/" + "a" * 150,
                id="url-longer-than-128",
            ),
            pytest.param(
                CustomField.FieldDataType.URL,
                "https://example.com/" + "a" * 200,
                None,
                id="url-over-the-limit",
            ),
            pytest.param(
                CustomField.FieldDataType.URL,
                "not a url",
                None,
                id="not-a-url",
            ),
        ],
    )
    def test_text_values_are_kept_whole_or_rejected(
        self,
        data_type: str,
        text: str,
        expected: str | None,
    ) -> None:
        """
        GIVEN:
            - A zone targeting a string or URL custom field
        WHEN:
            - A field update is prepared for text within or beyond the field's
              limits
        THEN:
            - Valid text is kept whole and invalid or too long text produces no
              update, never a truncated value
        """
        field = CustomFieldFactory(data_type=data_type)
        zone = OcrTemplateZoneFactory(
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=field,
        )

        update = _prepare_field_update(zone, text)

        assert (update.value if update else None) == expected

    @pytest.mark.parametrize(
        "target",
        [
            pytest.param(OcrTemplateZone.TargetType.CREATED, id="created"),
            pytest.param(OcrTemplateZone.TargetType.CUSTOM_FIELD, id="date-field"),
        ],
    )
    @pytest.mark.parametrize(
        ("ocr_language", "date_format", "text", "expected"),
        [
            pytest.param("deu", "", "12.05.2024", date(2024, 5, 12), id="german-order"),
            pytest.param(
                "eng",
                "",
                "05/12/2024",
                date(2024, 5, 12),
                id="english-order",
            ),
            pytest.param(
                "deu",
                "",
                "12. Mai 2024",
                date(2024, 5, 12),
                id="german-month-name",
            ),
            pytest.param(
                "deu",
                "%m.%d.%Y",
                "12.05.2024",
                date(2024, 12, 5),
                id="zone-date-format",
            ),
            pytest.param(
                "deu",
                "%Y/%m/%d",
                "12.05.2024",
                date(2024, 5, 12),
                id="invalid-format-falls-back",
            ),
            pytest.param("eng", "", "2024", None, id="year-only-is-rejected"),
        ],
    )
    def test_date_targets_parse_alike(
        self,
        target: str,
        ocr_language: str,
        date_format: str,
        text: str,
        expected: date | None,
    ) -> None:
        """
        GIVEN:
            - A zone targeting the created date or a date custom field
            - An OCR language and optionally a date format
        WHEN:
            - A field update is prepared for non-ISO date text
        THEN:
            - Both targets read the text the same way, honoring the zone's
              language and date format
        """
        field = (
            CustomFieldFactory(data_type=CustomField.FieldDataType.DATE)
            if target == OcrTemplateZone.TargetType.CUSTOM_FIELD
            else None
        )
        zone = OcrTemplateZoneFactory(
            target=target,
            custom_field=field,
            ocr_language=ocr_language,
            date_format=date_format,
        )

        update = _prepare_field_update(zone, text)

        assert (update.value if update else None) == expected


class TestNumberLocale:
    """Tests for deriving a number locale from the OCR language."""

    @pytest.mark.parametrize(
        ("ocr_language", "expected"),
        [
            pytest.param("deu", "de", id="single-language"),
            pytest.param("deu+eng", "de", id="first-of-several-languages"),
            pytest.param("aze_Cyrl", "az", id="script-suffix-is-dropped"),
            pytest.param("xyz", "en", id="unknown-language-falls-back-to-english"),
        ],
    )
    def test_number_locale(self, ocr_language: str, expected: str) -> None:
        """
        GIVEN:
            - A tesseract language code, possibly several or with a script
        WHEN:
            - The number locale is derived
        THEN:
            - The first language decides the locale, falling back to English
        """
        assert _number_locale(ocr_language) == Locale.parse(expected)


class TestParseMonetary:
    """Tests for the _parse_monetary function."""

    @pytest.mark.parametrize(
        ("value", "locale", "expected"),
        [
            pytest.param("12.50", EN, "12.50", id="plain-amount"),
            pytest.param("12", EN, "12.00", id="whole-number-gets-two-decimals"),
            pytest.param("12.500", EN, "12.50", id="trailing-zero-is-fine"),
            pytest.param("USD 12.50", EN, "USD12.50", id="code-before-amount"),
            pytest.param("12,50 EUR", DE, "EUR12.50", id="code-after-amount"),
            pytest.param("USD12.50", EN, "USD12.50", id="code-attached-to-amount"),
            pytest.param("$12.50", EN, "USD12.50", id="dollar-symbol-en"),
            pytest.param("$12.50", FR, "12.50", id="dollar-symbol-fr-has-no-code"),
            pytest.param(
                "\N{EURO SIGN}12.50",
                EN,
                "EUR12.50",
                id="euro-symbol",
            ),
            pytest.param(
                "\N{POUND SIGN}12.50",
                EN,
                "GBP12.50",
                id="pound-symbol",
            ),
            pytest.param(
                "USD $12.50",
                EN,
                "USD12.50",
                id="code-wins-over-symbol",
            ),
            pytest.param("INV 12.50", EN, "12.50", id="non-currency-word-ignored"),
            pytest.param("usd 12.50", EN, "12.50", id="lowercase-code-ignored"),
            pytest.param("(12.50)", EN, "-12.50", id="parentheses-negative"),
            pytest.param("($12.50)", EN, "USD-12.50", id="parentheses-with-symbol"),
            pytest.param("(12,50 EUR)", DE, "EUR-12.50", id="parentheses-with-code"),
            pytest.param("(0.00)", EN, "0.00", id="parentheses-zero-not-negative"),
            pytest.param("(USD) 12.50", EN, "USD12.50", id="empty-parentheses-ignored"),
            pytest.param("USD -12.50", EN, "USD-12.50", id="code-with-negative"),
            pytest.param("-12.50", EN, "-12.50", id="plain-negative"),
            pytest.param("1,234.56", EN, "1234.56", id="grouped-amount"),
            pytest.param("USD 12.50 EUR", EN, None, id="two-codes"),
            pytest.param("$12.50 \N{EURO SIGN}", EN, None, id="two-symbols"),
            pytest.param("(-12.50)", EN, None, id="parentheses-and-minus"),
            pytest.param("12.345", EN, None, id="too-many-decimals"),
            pytest.param("12345678901.12", EN, None, id="more-than-12-digits"),
            pytest.param(
                "USD 12345678901.12",
                EN,
                None,
                id="more-than-12-digits-with-code",
            ),
            pytest.param("100 (19% VAT)", EN, None, id="digits-outside-parentheses"),
            pytest.param("(12) (13)", EN, None, id="two-parenthesised-numbers"),
            pytest.param("-0.00", EN, "0.00", id="negative-zero-not-negative"),
            pytest.param("CHF 12", DE, "CHF12.00", id="code-in-german"),
            pytest.param(
                "1\N{NARROW NO-BREAK SPACE}234,56 \N{EURO SIGN}",
                FR,
                "EUR1234.56",
                id="french-space-grouping",
            ),
            pytest.param("USD", EN, None, id="code-without-amount"),
            pytest.param("garbage", EN, None, id="garbage"),
            pytest.param("", EN, None, id="empty"),
        ],
    )
    def test_parse_monetary(
        self,
        value: str,
        locale: Locale,
        expected: str | None,
    ) -> None:
        """
        GIVEN:
            - OCR text containing an amount, maybe with a currency or parentheses
        WHEN:
            - The text is parsed as a monetary value
        THEN:
            - The amount has two decimals and a leading currency code if one was
              found, or None is returned when the text is not a valid value
        """
        assert _parse_monetary(value, locale) == expected


class TestParsedTextLength:
    """Tests for the length cap on text read as a number, amount or date."""

    @pytest.mark.parametrize(
        ("parse", "value", "expected"),
        [
            pytest.param(
                lambda text: _parse_number(text, EN),
                "12.50",
                Decimal("12.50"),
                id="number",
            ),
            pytest.param(
                lambda text: _parse_monetary(text, EN),
                "USD 12.50",
                "USD12.50",
                id="monetary",
            ),
        ],
    )
    def test_text_longer_than_the_cap_is_not_read(
        self,
        parse: Callable[[str], object],
        value: str,
        expected: object,
    ) -> None:
        """
        GIVEN:
            - A valid number or amount padded with spaces to exactly the length
              cap, and the same value padded one character past it
        WHEN:
            - Each text is parsed
        THEN:
            - The text at the cap is read and the longer text is not
        """
        at_cap = value.rjust(MAX_PARSED_TEXT_LENGTH)

        assert parse(at_cap) == expected
        assert parse(f" {at_cap}") is None

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            pytest.param(
                "Datum: 13.04.2026 " + "x" * 300,
                date(2026, 4, 13),
                id="date-near-the-start",
            ),
            pytest.param(
                "x" * 300 + " Datum: 13.04.2026",
                None,
                id="date-past-the-cap",
            ),
            pytest.param(
                "x " * 118 + "xxxx Date 2026-04-131 more",
                None,
                id="token-split-by-the-cut",
            ),
            pytest.param(
                "x" * 246 + "2026-04-13" + "1" * 50,
                None,
                id="cut-inside-text-without-spaces",
            ),
            pytest.param(
                "x " * 118 + "xxxx Date 2026-04-13 more",
                date(2026, 4, 13),
                id="cut-on-a-space-keeps-the-last-word",
            ),
            pytest.param(" " * 300, None, id="whitespace-only"),
        ],
    )
    def test_long_text_is_searched_for_dates_up_to_the_cap(
        self,
        text: str,
        expected: date | None,
    ) -> None:
        """
        GIVEN:
            - Text longer than the cap with a date before it, after it, or with a
              non-date token that the cut would turn into a date
        WHEN:
            - The text is parsed as a date
        THEN:
            - Only whole words within the cap are searched
        """
        assert _parse_date(text, ENG_DATES) == expected

    @pytest.mark.parametrize(
        ("parse", "value"),
        [
            pytest.param(
                lambda text: _parse_number(text, EN),
                "- " * 128,
                id="number-dashes-without-digit",
            ),
            pytest.param(
                lambda text: _parse_number(text, EN),
                "- " * 127 + "1",
                id="number-dashes-before-digit",
            ),
            pytest.param(
                lambda text: _parse_monetary(text, EN),
                "- " * 128,
                id="monetary-dashes-without-digit",
            ),
            pytest.param(
                lambda text: _parse_monetary(text, EN),
                "(" + "1 " * 127,
                id="monetary-unclosed-parenthesis",
            ),
        ],
    )
    def test_malformed_text_at_the_cap_is_rejected(
        self,
        parse: Callable[[str], object],
        value: str,
    ) -> None:
        """
        GIVEN:
            - Malformed text at the length cap, made of dash runs or an
              unclosed parenthesis
        WHEN:
            - The text is parsed
        THEN:
            - No value is read
        """
        assert parse(value) is None


class TestConvertValue:
    """Tests for the _convert_value function."""

    @pytest.mark.parametrize(
        ("value", "data_type", "expected", "locale"),
        [
            pytest.param(
                "Hello",
                CustomField.FieldDataType.STRING,
                "Hello",
                EN,
                id="string",
            ),
            pytest.param(
                "https://example.com",
                CustomField.FieldDataType.URL,
                "https://example.com",
                EN,
                id="url",
            ),
            pytest.param(
                "x" * 500,
                CustomField.FieldDataType.LONG_TEXT,
                "x" * 500,
                EN,
                id="long-text",
            ),
            pytest.param("42", CustomField.FieldDataType.INT, 42, EN, id="int-simple"),
            pytest.param(
                "INV-123",
                CustomField.FieldDataType.INT,
                123,
                EN,
                id="int-with-noise",
            ),
            pytest.param(
                "-42",
                CustomField.FieldDataType.INT,
                -42,
                EN,
                id="int-negative",
            ),
            pytest.param(
                "\N{MINUS SIGN}5",
                CustomField.FieldDataType.INT,
                -5,
                EN,
                id="int-unicode-minus",
            ),
            pytest.param(
                "1,234",
                CustomField.FieldDataType.INT,
                1234,
                EN,
                id="int-comma-thousands",
            ),
            pytest.param(
                "1.234.567",
                CustomField.FieldDataType.INT,
                1234567,
                DE,
                id="int-dot-thousands",
            ),
            pytest.param(
                "12.00",
                CustomField.FieldDataType.INT,
                12,
                EN,
                id="int-zero-fraction",
            ),
            pytest.param(
                "1.234,00",
                CustomField.FieldDataType.INT,
                1234,
                DE,
                id="int-thousands-and-zero-fraction",
            ),
            pytest.param(
                "1234.00",
                CustomField.FieldDataType.INT,
                1234,
                EN,
                id="int-ungrouped-with-zero-fraction",
            ),
            pytest.param(
                "1.234",
                CustomField.FieldDataType.INT,
                1234,
                DE,
                id="int-dot-is-thousands-in-german",
            ),
            pytest.param(
                "1\N{NARROW NO-BREAK SPACE}234",
                CustomField.FieldDataType.INT,
                1234,
                FR,
                id="int-narrow-space-thousands-in-french",
            ),
            pytest.param(
                "2026-04-13",
                CustomField.FieldDataType.DATE,
                "2026-04-13",
                EN,
                id="date-iso",
            ),
            pytest.param(
                "123.45",
                CustomField.FieldDataType.MONETARY,
                "123.45",
                EN,
                id="monetary-simple",
            ),
            pytest.param(
                "1.234,56",
                CustomField.FieldDataType.MONETARY,
                "1234.56",
                DE,
                id="monetary-european",
            ),
            pytest.param(
                "\u20ac1,234.56",
                CustomField.FieldDataType.MONETARY,
                "EUR1234.56",
                EN,
                id="monetary-with-currency-symbol",
            ),
            pytest.param(
                "12345678901234567890,12345678901234567890",
                CustomField.FieldDataType.MONETARY,
                None,
                DE,
                id="monetary-too-precise-returns-none",
            ),
            pytest.param(
                "\u20ac-12.50",
                CustomField.FieldDataType.MONETARY,
                "EUR-12.50",
                EN,
                id="monetary-sign-after-currency-symbol",
            ),
            pytest.param(
                "-\u20ac12.50",
                CustomField.FieldDataType.MONETARY,
                "EUR-12.50",
                EN,
                id="monetary-sign-before-currency-symbol",
            ),
            pytest.param(
                "EUR -12.50",
                CustomField.FieldDataType.MONETARY,
                "EUR-12.50",
                EN,
                id="monetary-sign-after-currency-code",
            ),
            pytest.param(
                "Total: -5",
                CustomField.FieldDataType.INT,
                -5,
                EN,
                id="int-sign-after-label",
            ),
            pytest.param(
                "\u20ac-12.50",
                CustomField.FieldDataType.FLOAT,
                -12.5,
                EN,
                id="float-sign-after-currency-symbol",
            ),
            pytest.param(
                "\u0661\u0662\u0663",
                CustomField.FieldDataType.INT,
                123,
                Locale.parse("ar"),
                id="int-arabic-indic-digits",
            ),
            pytest.param(
                "\u0661\u066c\u0662\u0663\u0664\u066b\u0665",
                CustomField.FieldDataType.FLOAT,
                1234.5,
                Locale.parse("ar"),
                id="float-arabic-separators",
            ),
            pytest.param(
                "\u06f1\u06f2\u06f3",
                CustomField.FieldDataType.INT,
                123,
                Locale.parse("fa"),
                id="int-persian-digits",
            ),
            pytest.param(
                "\u0967\u0968\u0969",
                CustomField.FieldDataType.INT,
                123,
                Locale.parse("hi"),
                id="int-devanagari-digits",
            ),
            pytest.param(
                "1 234,56",
                CustomField.FieldDataType.FLOAT,
                1234.56,
                Locale.parse("ru"),
                id="float-plain-space-in-russian",
            ),
            pytest.param(
                "1\N{RIGHT SINGLE QUOTATION MARK}234.56",
                CustomField.FieldDataType.FLOAT,
                1234.56,
                Locale.parse("de_CH"),
                id="float-apostrophe-group-in-swiss-german",
            ),
        ],
    )
    def test_converts_to_exact_value(
        self,
        value: str,
        data_type: str,
        expected: object,
        locale: Locale,
    ) -> None:
        """
        GIVEN:
            - An extracted string, a custom field data type and a number locale
        WHEN:
            - The value is converted
        THEN:
            - The converted value equals the expected value exactly
        """
        assert _convert_value(value, data_type, locale, ENG_DATES) == expected

    @pytest.mark.parametrize(
        ("value", "locale", "expected"),
        [
            pytest.param("1234.56", EN, 1234.56, id="float-simple"),
            pytest.param("1.234,56", DE, 1234.56, id="float-european-format"),
            pytest.param("1,234.56", EN, 1234.56, id="float-us-format"),
            pytest.param("1234,56", DE, 1234.56, id="float-comma-only"),
            pytest.param("1,234", DE, 1.234, id="float-comma-is-decimal-in-german"),
            pytest.param("1,234", EN, 1234.0, id="float-comma-is-thousands-in-english"),
            pytest.param("1 234,56", FR, 1234.56, id="float-plain-space-in-french"),
            pytest.param(
                "1\N{NARROW NO-BREAK SPACE}234,56",
                FR,
                1234.56,
                id="float-narrow-space-in-french",
            ),
            pytest.param(
                "\N{MINUS SIGN}1.5",
                EN,
                -1.5,
                id="float-unicode-minus",
            ),
        ],
    )
    def test_float_conversion(
        self,
        value: str,
        locale: Locale,
        expected: float,
    ) -> None:
        """
        GIVEN:
            - A numeric string in one of several decimal formats and a locale
        WHEN:
            - The value is converted to a FLOAT field value
        THEN:
            - The result is the expected float
        """
        assert (
            _convert_value(value, CustomField.FieldDataType.FLOAT, locale, ENG_DATES)
            == expected
        )

    @pytest.mark.parametrize(
        ("value", "data_type", "locale"),
        [
            pytest.param(
                "abc",
                CustomField.FieldDataType.INT,
                EN,
                id="int-empty-returns-none",
            ),
            pytest.param(
                "-",
                CustomField.FieldDataType.INT,
                EN,
                id="int-only-dash-returns-none",
            ),
            pytest.param(
                "12.50",
                CustomField.FieldDataType.INT,
                EN,
                id="int-fraction-returns-none",
            ),
            pytest.param(
                "1.5",
                CustomField.FieldDataType.INT,
                EN,
                id="int-short-fraction-returns-none",
            ),
            pytest.param(
                "0.500",
                CustomField.FieldDataType.INT,
                EN,
                id="int-leading-zero-fraction-returns-none",
            ),
            pytest.param(
                "1..2",
                CustomField.FieldDataType.INT,
                EN,
                id="int-empty-group-returns-none",
            ),
            pytest.param(
                "5-3",
                CustomField.FieldDataType.INT,
                EN,
                id="int-inner-dash-returns-none",
            ),
            pytest.param(
                "1,234.567",
                CustomField.FieldDataType.INT,
                EN,
                id="int-thousands-and-fraction-returns-none",
            ),
            pytest.param(
                "12.3,00",
                CustomField.FieldDataType.INT,
                EN,
                id="int-bad-grouping-before-fraction-returns-none",
            ),
            pytest.param(
                "1,2345.00",
                CustomField.FieldDataType.INT,
                EN,
                id="int-long-group-before-fraction-returns-none",
            ),
            pytest.param(
                "abc",
                CustomField.FieldDataType.FLOAT,
                EN,
                id="float-empty-returns-none",
            ),
            pytest.param(
                ",",
                CustomField.FieldDataType.FLOAT,
                EN,
                id="float-only-separator-returns-none",
            ),
            pytest.param(
                "not a date",
                CustomField.FieldDataType.DATE,
                EN,
                id="date-invalid-returns-none",
            ),
            pytest.param(
                "2026-13-32",
                CustomField.FieldDataType.DATE,
                EN,
                id="date-invalid-values-returns-none",
            ),
            pytest.param(
                "CHF",
                CustomField.FieldDataType.MONETARY,
                EN,
                id="monetary-empty-returns-none",
            ),
            pytest.param(
                "maybe",
                CustomField.FieldDataType.BOOL,
                EN,
                id="bool-unknown-returns-none",
            ),
            pytest.param(
                "test",
                CustomField.FieldDataType.DOCUMENTLINK,
                EN,
                id="unsupported-type-documentlink-returns-none",
            ),
            pytest.param(
                "test",
                CustomField.FieldDataType.SELECT,
                EN,
                id="unsupported-type-select-returns-none",
            ),
            pytest.param(
                "",
                CustomField.FieldDataType.STRING,
                EN,
                id="empty-string-returns-none",
            ),
            pytest.param(
                "9" * 400,
                CustomField.FieldDataType.FLOAT,
                EN,
                id="float-overflow-is-not-stored-as-infinity",
            ),
            pytest.param(
                "1.234",
                CustomField.FieldDataType.INT,
                EN,
                id="int-german-thousands-is-a-fraction-in-english",
            ),
            pytest.param(
                "12.50",
                CustomField.FieldDataType.INT,
                DE,
                id="int-english-decimal-is-malformed-in-german",
            ),
            pytest.param(
                "1.234.567",
                CustomField.FieldDataType.FLOAT,
                EN,
                id="float-multiple-dots-in-english",
            ),
        ],
    )
    def test_returns_none(self, value: str, data_type: str, locale: Locale) -> None:
        """
        GIVEN:
            - A value that cannot be converted to the given data type in a locale
        WHEN:
            - The value is converted
        THEN:
            - None is returned
        """
        assert _convert_value(value, data_type, locale, ENG_DATES) is None

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
        assert _convert_value(value, data_type, EN, ENG_DATES) is None

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
        assert (
            _convert_value(value, CustomField.FieldDataType.BOOL, EN, ENG_DATES) is True
        )

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
        assert (
            _convert_value(value, CustomField.FieldDataType.BOOL, EN, ENG_DATES)
            is False
        )


class TestRenderPages:
    """Tests for _render_pages."""

    @pytest.fixture
    def pdf(self, tmp_path: Path) -> Path:
        pdf = tmp_path / "document.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        return pdf

    @pytest.fixture
    def mock_rasterize(self, mocker: MockerFixture) -> MagicMock:
        def render(in_path: Path, out_path: Path, **kwargs: Any) -> None:
            out_path.write_bytes(b"rendered")

        return mocker.patch(
            "documents.zone_ocr.rasterize_pdf_page_to_png",
            side_effect=render,
        )

    def test_renders_requested_pages_in_order_and_skips_out_of_range(
        self,
        pdf: Path,
        tmp_path: Path,
        mock_rasterize: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A 3 page PDF and requested pages including out of range indexes
        WHEN:
            - The pages are rendered
        THEN:
            - Only the in range pages are rendered, in order, as 1-based pages
              at 300 DPI with a 60 second timeout
        """
        pages = _render_pages(pdf, {-1, 0, 2, 3}, tmp_path, 3)

        assert list(pages) == [0, 2]
        assert mock_rasterize.call_count == 2
        for page, call in zip([1, 3], mock_rasterize.call_args_list, strict=True):
            assert call.args[0] == pdf
            assert call.kwargs == {"dpi": 300, "page": page, "timeout": 60}

    def test_missing_render_output_is_not_a_page(
        self,
        pdf: Path,
        tmp_path: Path,
        mock_rasterize: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A renderer that produces no output file
        WHEN:
            - A page is rendered
        THEN:
            - No pages are returned
        """
        mock_rasterize.side_effect = None

        assert _render_pages(pdf, {0}, tmp_path, None) == {}

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(ParseError("pdftoppm timed out after 60s"), id="timeout"),
            pytest.param(
                ParseError("pdftoppm failed at ['pdftoppm']"),
                id="render-failure",
            ),
        ],
    )
    def test_render_failure_does_not_prevent_other_pages(
        self,
        pdf: Path,
        tmp_path: Path,
        mock_rasterize: MagicMock,
        error: Exception,
    ) -> None:
        """
        GIVEN:
            - A renderer that fails for the first page only
        WHEN:
            - Two pages are rendered
        THEN:
            - The failing page is skipped and the other page is still rendered
        """

        def render(in_path: Path, out_path: Path, *, page: int, **kwargs: Any) -> None:
            if page == 1:
                raise error
            out_path.write_bytes(b"rendered")

        mock_rasterize.side_effect = render

        assert list(_render_pages(pdf, {0, 1}, tmp_path, 2)) == [1]

    def test_image_is_used_directly_only_for_first_page(
        self,
        tmp_path: Path,
        mock_rasterize: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A single image file
        WHEN:
            - The first page, then the second page, is requested
        THEN:
            - The image itself is returned for the first page only
            - The renderer is never run
        """
        image_path = tmp_path / "image.png"
        with Image.new("RGB", (10, 10)) as image:
            image.save(image_path)
        assert _render_pages(image_path, {0}, tmp_path, 1) == {0: image_path}
        assert _render_pages(image_path, {1}, tmp_path, 1) == {}
        mock_rasterize.assert_not_called()


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


class TestResolveDocPath:
    """Tests for _resolve_doc_path."""

    @pytest.fixture
    def document(self, mocker: MockerFixture) -> MagicMock:
        doc = mocker.MagicMock()
        doc.has_archive_version = False
        doc.source_path = Path("/nonexistent/source.pdf")
        return doc

    def test_returns_none_when_no_files_exist(self, document: MagicMock) -> None:
        """
        GIVEN:
            - A document with no archive version and a missing source file
        WHEN:
            - The document path is resolved without an original file
        THEN:
            - None is returned
        """
        assert _resolve_doc_path(document, None) is None

    def test_prefers_archive_and_falls_back_to_source(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - A document with existing archive and source files
        WHEN:
            - The path is resolved, then the archive file is removed and it is
              resolved again
        THEN:
            - The archive path is returned first, then the source path
        """
        source = tmp_path / "source.pdf"
        archive = tmp_path / "archive.pdf"
        source.touch()
        archive.touch()
        document = mocker.MagicMock(
            has_archive_version=True,
            archive_path=archive,
            source_path=source,
        )
        assert _resolve_doc_path(document, None) == archive
        archive.unlink()
        assert _resolve_doc_path(document, None) == source

    def test_returns_original_file_as_fallback(
        self,
        document: MagicMock,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - A document whose own files are missing and an existing original file
        WHEN:
            - The document path is resolved with the original file
        THEN:
            - The original file path is returned
        """
        original = tmp_path / "original.pdf"
        original.touch()
        assert _resolve_doc_path(document, original) == original

    def test_returns_none_for_missing_original_file(
        self,
        document: MagicMock,
        tmp_path: Path,
    ) -> None:
        """
        GIVEN:
            - A document whose own files are missing and an original file path
              that does not exist
        WHEN:
            - The document path is resolved with the original file
        THEN:
            - None is returned
        """
        assert _resolve_doc_path(document, tmp_path / "missing.pdf") is None


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRunZoneExtraction:
    """Tests for the full extraction pipeline."""

    @pytest.fixture
    def document(self) -> Document:
        return DocumentFactory(
            title="Test",
            content="test",
            mime_type="image/png",
        )

    @pytest.fixture
    def source(self, paperless_dirs: PaperlessDirs) -> Path:
        source = paperless_dirs.scratch_dir / "document.png"
        with Image.new("RGB", (200, 200), "white") as image:
            image.save(source)
        return source

    @pytest.fixture(autouse=True)
    def ocr_reads_text(self, mock_zone_ocr_run: MagicMock) -> None:
        mock_zone_ocr_run.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="extracted",
            stderr="",
        )

    @pytest.fixture
    def template_with_zone(self) -> Callable[..., OcrTemplate]:
        """Build a template with one default zone, matching "test" by default."""

        def _make(name: str, **kwargs: Any) -> OcrTemplate:
            kwargs.setdefault("match", "test")
            template = OcrTemplateFactory(name=name, **kwargs)
            OcrTemplateZoneFactory(template=template)
            return template

        return _make

    @pytest.mark.parametrize(
        ("template_name", "template_kwargs"),
        [
            pytest.param("Other sender", {"match": "Contoso"}, id="non-matching"),
            pytest.param("Disabled", {"enabled": False}, id="disabled"),
        ],
    )
    def test_skips_ineligible_template(
        self,
        mock_zone_ocr_run: MagicMock,
        template_with_zone: Callable[..., OcrTemplate],
        document: Document,
        source: Path,
        template_name: str,
        template_kwargs: dict[str, Any],
    ) -> None:
        """
        GIVEN:
            - A template whose match text is not in the document content, or a
              disabled template that would otherwise match
        WHEN:
            - Zone extraction runs against a real document file
        THEN:
            - No results are returned, no text is read and the title is unchanged
        """
        template_with_zone(template_name, **template_kwargs)

        results = run_zone_extraction(document, source)

        assert results == []
        mock_zone_ocr_run.assert_not_called()
        document.refresh_from_db()
        assert document.title == "Test"

    def test_skips_template_with_no_zones(
        self,
        mock_zone_ocr_run: MagicMock,
        document: Document,
        source: Path,
    ) -> None:
        """
        GIVEN:
            - An enabled matching template with no zones
        WHEN:
            - Zone extraction runs
        THEN:
            - No results are returned, no text is read and the title is unchanged
        """
        OcrTemplateFactory(
            name="Empty",
            match="test",
        )

        results = run_zone_extraction(document, source)

        assert results == []
        mock_zone_ocr_run.assert_not_called()
        document.refresh_from_db()
        assert document.title == "Test"

    def test_handles_process_exception_gracefully(
        self,
        mock_zone_ocr_run: MagicMock,
        template_with_zone: Callable[..., OcrTemplate],
        document: Document,
        source: Path,
    ) -> None:
        """
        GIVEN:
            - Two matching templates, where reading the first one's text raises
              an unexpected error
        WHEN:
            - Zone extraction runs
        THEN:
            - The error does not propagate, the failing template's zone is
              reported as template_failed and the other template still runs
        """
        mock_zone_ocr_run.side_effect = [
            RuntimeError("test error"),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="extracted",
                stderr="",
            ),
        ]
        template_with_zone("First", enabled=True)
        template_with_zone("Second", enabled=True)

        results = run_zone_extraction(document, source)

        assert Counter((r.value, r.reason) for r in results) == Counter(
            [(None, "template_failed"), ("extracted", None)],
        )
        assert {r.template for r in results} == {"First", "Second"}

    def test_handles_none_original_file(
        self,
        mock_zone_ocr_run: MagicMock,
        template_with_zone: Callable[..., OcrTemplate],
        document: Document,
    ) -> None:
        """
        GIVEN:
            - A matching template, a document with no accessible file and no
              original file
        WHEN:
            - Zone extraction runs
        THEN:
            - Each zone is reported as missing_file and no text is read
        """
        template = template_with_zone("Matching", enabled=True)
        zone = template.zones.get()

        results = run_zone_extraction(document, None)

        assert [(r.template, r.zone, r.reason) for r in results] == [
            ("Matching", zone.name, "missing_file"),
        ]
        mock_zone_ocr_run.assert_not_called()

    @pytest.mark.parametrize(
        "template_names",
        [
            pytest.param(["Active"], id="one-template"),
            pytest.param(
                ["Template 0", "Template 1", "Template 2"],
                id="three-templates",
            ),
        ],
    )
    def test_processes_every_enabled_template(
        self,
        template_with_zone: Callable[..., OcrTemplate],
        document: Document,
        source: Path,
        template_names: list[str],
    ) -> None:
        """
        GIVEN:
            - One or more enabled matching templates, each with a zone
        WHEN:
            - Zone extraction runs
        THEN:
            - Each template reports exactly one successful result
        """
        for name in template_names:
            template_with_zone(name, enabled=True)

        results = run_zone_extraction(document, source)

        assert sorted((r.template, r.reason) for r in results) == [
            (name, None) for name in sorted(template_names)
        ]


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRealZoneOcr:
    """End to end zone extraction using the real pdftoppm and tesseract."""

    @pytest.fixture
    def template(self) -> OcrTemplate:
        template = make_template("Whole page", match="test", source_height=100)
        OcrTemplateZoneFactory(
            template=template,
            name="Title",
            target=OcrTemplateZone.TargetType.TITLE,
            x=0,
            y=0,
            width=100,
            height=100,
            page=1,
        )
        return template

    @pytest.mark.usefixtures("template")
    def test_pdf_page_is_rendered_and_read(
        self,
        simple_digital_pdf_file: Path,
    ) -> None:
        """
        GIVEN:
            - A one page PDF containing text
            - A template with a title zone covering the whole page
        WHEN:
            - Zone extraction runs without any mocks
        THEN:
            - The page text is read and written to the document title
        """
        document = DocumentFactory(
            title="Original",
            content="This is a test document.",
            mime_type="application/pdf",
            page_count=1,
        )
        shutil.copy(simple_digital_pdf_file, document.source_path)

        results = run_zone_extraction(document, None)

        assert [result.reason for result in results] == [None]
        document.refresh_from_db()
        assert "This is a test document" in document.title

    @pytest.mark.usefixtures("template")
    def test_image_is_read_without_rendering(self) -> None:
        """
        GIVEN:
            - An image containing text as the document's file
            - A template with a title zone covering the whole image
        WHEN:
            - Zone extraction runs without any mocks
        THEN:
            - The image text is read and written to the document title
        """
        document = DocumentFactory(
            title="Original",
            content="This is a test document.",
            mime_type="image/png",
            page_count=1,
        )
        shutil.copy(
            Path(__file__).parent / "samples" / "simple.png",
            document.source_path,
        )

        results = run_zone_extraction(document, None)

        assert [result.reason for result in results] == [None]
        document.refresh_from_db()
        assert "This is a test document" in document.title
