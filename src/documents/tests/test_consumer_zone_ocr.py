"""Tests for zone OCR during consumption."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Self

import pytest
from django.conf import settings
from django.db import transaction
from PIL import Image

from documents import consumer as consumer_module
from documents.consumer import ConsumerPlugin
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from paperless_testing.factories import CustomFieldFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import OcrTemplateFactory
from paperless_testing.factories import OcrTemplateZoneFactory
from paperless_testing.factories import TagFactory
from paperless_testing.factories import UserFactory
from paperless_testing.fakes.progress import FakeProgressManager
from paperless_testing.samples import SIMPLE_DIGITAL_PDF

if TYPE_CHECKING:
    from collections.abc import Callable
    from unittest.mock import MagicMock

    from pytest_django.fixtures import SettingsWrapper
    from pytest_mock import MockerFixture

    from documents.zone_ocr import TemplatePlan
    from paperless_testing.dirs import PaperlessDirs

CONTENT = "Northwind Power & Light statement"

# The text each zone's fake OCR returns, by zone name.
ZONE_TEXT = {
    "Title": "Zone title",
    "ASN": "ASN 777",
    "Created": "2024-03-05",
    "Code": "INV42",
}

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".eml": "message/rfc822",
}


class ZoneTestParser:
    """A parser returning CONTENT, with a PDF archive when one is requested."""

    name = "zone-test-parser"
    version = "0.1"
    author = "test"
    url = "test"

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        return {mime: suffix for suffix, mime in MIME_TYPES.items()}

    @classmethod
    def score(cls, mime_type: str, filename: str, path: Path | None = None) -> int:
        return 0

    @property
    def can_produce_archive(self) -> bool:
        return True

    @property
    def requires_pdf_rendition(self) -> bool:
        return False

    def __enter__(self) -> Self:
        self._tmpdir = Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR))
        self._archive: Path | None = None
        self._thumb = self._tmpdir / "thumb.webp"
        self._thumb.write_bytes(b"thumbnail")
        return self

    def __exit__(self, *args: object) -> None:
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def configure(self, context: object) -> None:
        """The test parser ignores its context."""

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        *,
        produce_archive: bool = True,
    ) -> None:
        if produce_archive:
            self._archive = self._tmpdir / "archive.pdf"
            shutil.copy(SIMPLE_DIGITAL_PDF, self._archive)

    def get_text(self) -> str:
        return CONTENT

    def get_date(self) -> None:
        return None

    def get_archive_path(self) -> Path | None:
        return self._archive

    def get_thumbnail(self, document_path: Path, mime_type: str) -> Path:
        return self._thumb

    def get_page_count(self, document_path: Path, mime_type: str) -> int:
        return 1

    def extract_metadata(self, document_path: Path, mime_type: str) -> list[Any]:
        return []


@pytest.fixture
def page_image(tmp_path: Path) -> Path:
    page = tmp_path / "page.png"
    with Image.new("RGB", (200, 200), "white") as image:
        image.save(page)
    return page


@pytest.fixture
def mock_render(mocker: MockerFixture, page_image: Path) -> MagicMock:
    """Fake page rendering, recording whether a transaction was open."""
    render = mocker.patch("documents.zone_ocr._render_pages")
    render.in_transaction = []

    def record(*args: Any, **kwargs: Any) -> dict[int, Path]:
        render.in_transaction.append(transaction.get_connection().in_atomic_block)
        return {0: page_image}

    render.side_effect = record
    return render


@pytest.fixture
def mock_ocr(mocker: MockerFixture) -> MagicMock:
    """Fake zone OCR returning ZONE_TEXT, recording whether a transaction was open."""
    ocr = mocker.patch("documents.zone_ocr._ocr_text")
    ocr.in_transaction = []

    def read(cropped: Image.Image, zone: OcrTemplateZone, tmp_dir: Path) -> str:
        ocr.in_transaction.append(transaction.get_connection().in_atomic_block)
        return ZONE_TEXT[zone.name]

    ocr.side_effect = read
    return ocr


@pytest.fixture
def consume(
    paperless_dirs: PaperlessDirs,
    mocker: MockerFixture,
) -> Callable[..., Document]:
    """Consume a file of the given suffix through the ConsumerPlugin."""
    registry = mocker.patch("documents.consumer.get_parser_registry")
    registry.return_value.get_parser_for_file.return_value = ZoneTestParser
    mocker.patch(
        "documents.consumer.magic.from_file",
        side_effect=lambda path, *, mime=False: MIME_TYPES[Path(path).suffix],
    )

    def run(
        suffix: str = ".pdf",
        overrides: DocumentMetadataOverrides | None = None,
        root_document_id: int | None = None,
    ) -> Document:
        source = paperless_dirs.scratch_dir / f"upload{suffix}"
        if suffix == ".pdf":
            shutil.copy(SIMPLE_DIGITAL_PDF, source)
        else:
            source.write_bytes(f"{suffix} {source.name}".encode())
        plugin = ConsumerPlugin(
            ConsumableDocument(
                DocumentSource.ApiUpload,
                original_file=source,
                root_document_id=root_document_id,
            ),
            overrides or DocumentMetadataOverrides(),
            FakeProgressManager(source.name, None),
            paperless_dirs.scratch_dir,
            "task-id",
        )
        plugin.setup()
        try:
            result = plugin.run()
        finally:
            plugin.cleanup()
        return Document.objects.get(pk=result["document_id"])

    return run


def make_template(
    name: str = "Invoice",
    targets: tuple[str, ...] = ("Title",),
    custom_field: CustomField | None = None,
    **kwargs: Any,
) -> OcrTemplate:
    """A template matching CONTENT with one zone per named target."""
    template = OcrTemplateFactory(
        name=name,
        match="Northwind",
        source_width=100,
        source_height=100,
        **kwargs,
    )
    zone_targets = {
        "Title": OcrTemplateZone.TargetType.TITLE,
        "ASN": OcrTemplateZone.TargetType.ASN,
        "Created": OcrTemplateZone.TargetType.CREATED,
        "Code": OcrTemplateZone.TargetType.CUSTOM_FIELD,
    }
    for order, zone_name in enumerate(targets):
        OcrTemplateZoneFactory(
            template=template,
            name=zone_name,
            target=zone_targets[zone_name],
            custom_field=custom_field if zone_name == "Code" else None,
            y=order * 20,
            width=50,
            height=20,
            order=order,
        )
    return template


def custom_field_value(document: Document, field: CustomField) -> Any:
    instance = CustomFieldInstance.objects.filter(
        document=document,
        field=field,
    ).first()
    return instance.value if instance is not None else None


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("mock_ocr")
class TestConsumerZoneOcrTransaction:
    """Zone OCR runs outside the consumer's database transaction."""

    def test_ocr_runs_before_the_transaction_opens(
        self,
        consume: Callable[..., Document],
        mock_render: MagicMock,
        mock_ocr: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A template matching the consumed document's text
        WHEN:
            - The document is consumed
        THEN:
            - Pages are rendered and zones are read with no transaction open
            - The zone value is written to the document
        """
        make_template()

        document = consume()

        assert mock_render.in_transaction == [False]
        assert mock_ocr.in_transaction == [False]
        assert document.title == "Zone title"


@pytest.mark.django_db
@pytest.mark.usefixtures("mock_ocr")
class TestConsumerZoneOcr:
    """Zone values are computed before and written during consumption."""

    @pytest.fixture
    def code_field(self) -> CustomField:
        return CustomFieldFactory(
            name="Invoice code",
            data_type=CustomField.FieldDataType.STRING,
        )

    @pytest.mark.parametrize(
        ("suffix", "generation", "expected_file"),
        [
            pytest.param(".pdf", "always", "archive.pdf", id="pdf-archive"),
            pytest.param(".eml", "always", "archive.pdf", id="mail-archive"),
            pytest.param(".pdf", "never", "upload.pdf", id="pdf-working-copy"),
            pytest.param(".png", "never", "upload.png", id="image-working-copy"),
        ],
    )
    def test_zones_are_read_from_the_archive_or_working_copy(
        self,
        consume: Callable[..., Document],
        mock_render: MagicMock,
        settings: SettingsWrapper,
        suffix: str,
        generation: str,
        expected_file: str,
    ) -> None:
        """
        GIVEN:
            - A template matching the consumed document's text
        WHEN:
            - A document is consumed with or without an archive
        THEN:
            - Zones are read from the archive when there is one, otherwise
              from the working copy of the PDF or image
        """
        settings.ARCHIVE_FILE_GENERATION = generation
        make_template()

        document = consume(suffix)

        mock_render.assert_called_once()
        assert mock_render.call_args.args[0].name == expected_file
        assert document.title == "Zone title"

    def test_mail_without_archive_is_not_rendered(
        self,
        consume: Callable[..., Document],
        mock_render: MagicMock,
        settings: SettingsWrapper,
    ) -> None:
        """
        GIVEN:
            - A template matching the consumed document's text
        WHEN:
            - An email is consumed without an archive
        THEN:
            - No page is rendered from the email file
            - The document is consumed without zone values
        """
        settings.ARCHIVE_FILE_GENERATION = "never"
        make_template()

        document = consume(".eml")

        mock_render.assert_not_called()
        assert document.title == "upload"

    @pytest.mark.usefixtures("mock_render")
    def test_values_are_written_before_document_added_workflows(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template writing a custom field
            - A DOCUMENT_ADDED workflow filtering on that custom field's value
              and assigning a tag
        WHEN:
            - A matching document is consumed
        THEN:
            - The workflow sees the zone value and assigns its tag
        """
        make_template(targets=("Code",), custom_field=code_field)
        tag = TagFactory(name="Zone matched")
        trigger = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
            filter_custom_field_query=json.dumps(
                ["AND", [[code_field.pk, "exact", "INV42"]]],
            ),
        )
        action = WorkflowAction.objects.create()
        action.assign_tags.add(tag)
        workflow = Workflow.objects.create(name="On zone value", order=0)
        workflow.triggers.add(trigger)
        workflow.actions.add(action)

        document = consume()

        assert custom_field_value(document, code_field) == "INV42"
        assert list(document.tags.all()) == [tag]

    @pytest.mark.parametrize(
        "overridden",
        [
            pytest.param("title", id="title"),
            pytest.param("asn", id="asn"),
            pytest.param("created", id="created"),
            pytest.param("custom_field", id="custom-field"),
        ],
    )
    @pytest.mark.usefixtures("mock_render")
    def test_explicit_values_are_not_overwritten(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
        overridden: str,
    ) -> None:
        """
        GIVEN:
            - A template with title, ASN, created and custom field zones
            - Metadata overrides giving one of those fields a value
        WHEN:
            - A matching document is consumed
        THEN:
            - The supplied value is kept
            - Every other zone value is written
        """
        make_template(
            targets=("Title", "ASN", "Created", "Code"),
            custom_field=code_field,
        )
        explicit = {
            "title": "Upload title",
            "asn": 123,
            "created": date(2020, 1, 2),
            "custom_field": "Given",
        }
        overrides = {
            "title": DocumentMetadataOverrides(title="Upload title"),
            "asn": DocumentMetadataOverrides(asn=123),
            "created": DocumentMetadataOverrides(created=date(2020, 1, 2)),
            "custom_field": DocumentMetadataOverrides(
                custom_fields={code_field.pk: "Given"},
            ),
        }[overridden]
        expected = {
            "title": "Zone title",
            "asn": 777,
            "created": date(2024, 3, 5),
            "custom_field": "INV42",
        } | {overridden: explicit[overridden]}

        document = consume(overrides=overrides)

        assert {
            "title": document.title,
            "asn": document.archive_serial_number,
            "created": document.created,
            "custom_field": custom_field_value(document, code_field),
        } == expected

    @pytest.mark.usefixtures("mock_render")
    def test_custom_field_listed_without_a_value_is_filled(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template with a custom field zone
            - Metadata overrides listing that custom field without a value
        WHEN:
            - A matching document is consumed
        THEN:
            - The zone value is written to the custom field
        """
        make_template(targets=("Code",), custom_field=code_field)

        document = consume(
            overrides=DocumentMetadataOverrides(custom_fields={code_field.pk: None}),
        )

        assert custom_field_value(document, code_field) == "INV42"

    @pytest.mark.usefixtures("mock_render")
    def test_custom_field_deleted_before_writing_is_skipped(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A template with title and custom field zones
            - The custom field deleted after the zone values are planned
        WHEN:
            - A matching document is consumed
        THEN:
            - The document is stored with the title
            - The custom field zone is reported as unassigned
        """
        make_template(targets=("Title", "Code"), custom_field=code_field)
        plan = consumer_module.plan_zone_extraction

        def plan_then_delete(*args: Any, **kwargs: Any) -> list[TemplatePlan]:
            plans = plan(*args, **kwargs)
            CustomField.objects.filter(pk=code_field.pk).delete()
            return plans

        mocker.patch(
            "documents.consumer.plan_zone_extraction",
            side_effect=plan_then_delete,
        )
        caplog.set_level(logging.DEBUG, logger="paperless.consumer")

        document = consume()

        assert document.title == "Zone title"
        assert not CustomFieldInstance.objects.filter(document=document).exists()
        assert "zone 'Code' for Invoice code: unassigned" in caplog.text

    @pytest.mark.parametrize(
        ("with_owner", "expected_title", "expected_code"),
        [
            pytest.param(True, "Zone title", None, id="owner-sees-own-templates"),
            pytest.param(False, "Zone title", "INV42", id="no-owner-sees-all"),
        ],
    )
    @pytest.mark.usefixtures("mock_render")
    def test_templates_are_selected_by_the_metadata_owner(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
        with_owner: bool,  # noqa: FBT001
        expected_title: str,
        expected_code: str | None,
    ) -> None:
        """
        GIVEN:
            - A template owned by the upload's owner writing the title
            - A private template of another user writing a custom field
        WHEN:
            - A matching document is consumed with or without an owner
        THEN:
            - With an owner, only the templates that owner can view apply
            - Without an owner, every template applies
        """
        owner = UserFactory()
        make_template("Mine", owner=owner)
        make_template(
            "Private",
            targets=("Code",),
            custom_field=code_field,
            owner=UserFactory(),
        )

        document = consume(
            overrides=DocumentMetadataOverrides(
                owner_id=owner.pk if with_owner else None,
            ),
        )

        assert document.title == expected_title
        assert custom_field_value(document, code_field) == expected_code

    @pytest.mark.usefixtures("mock_render")
    def test_duplicate_asn_is_checked_when_writing(
        self,
        consume: Callable[..., Document],
    ) -> None:
        """
        GIVEN:
            - A template with title and ASN zones
            - Another document already using the zone's ASN
        WHEN:
            - A matching document is consumed
        THEN:
            - The ASN is not written
            - The title from the same template is written
        """
        DocumentFactory(archive_serial_number=777)
        make_template(targets=("Title", "ASN"))

        document = consume()

        assert document.archive_serial_number is None
        assert document.title == "Zone title"

    @pytest.mark.parametrize(
        "failing",
        [
            pytest.param(
                "documents.consumer.get_templates_for_content",
                id="template-selection",
            ),
            pytest.param("documents.consumer.plan_zone_extraction", id="extraction"),
        ],
    )
    @pytest.mark.usefixtures("mock_render")
    def test_read_phase_failure_does_not_fail_consumption(
        self,
        consume: Callable[..., Document],
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
        failing: str,
    ) -> None:
        """
        GIVEN:
            - A template matching the consumed document's text
            - Template selection or zone extraction raising an error
        WHEN:
            - The document is consumed
        THEN:
            - The document is stored without zone values
            - The failure is logged
        """
        make_template()
        mocker.patch(failing, side_effect=RuntimeError("zone OCR broke"))

        document = consume()

        assert document.title == "upload"
        assert "Zone OCR failed for upload.pdf" in caplog.text

    @pytest.mark.usefixtures("mock_render")
    def test_write_failure_does_not_fail_consumption(
        self,
        consume: Callable[..., Document],
        mocker: MockerFixture,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """
        GIVEN:
            - A template matching the consumed document's text
            - Writing the template's values raising an error
        WHEN:
            - The document is consumed
        THEN:
            - The document is stored without the template's values
            - The failed template is logged
        """
        make_template()
        mocker.patch(
            "documents.zone_ocr._apply_field_updates",
            side_effect=RuntimeError("write failed"),
        )

        document = consume()

        assert document.title == "upload"
        assert "error processing template 'Invoice'" in caplog.text

    @pytest.mark.usefixtures("mock_render")
    def test_version_values_are_written_to_the_root(
        self,
        consume: Callable[..., Document],
        code_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A root document whose owner can view a template writing the title
              and a custom field
            - A private template of another user
        WHEN:
            - A new version of the root document is consumed
        THEN:
            - The zone values are written to the root document
            - The version keeps the root's previous title and gets no custom field
            - The other user's template does not apply
        """
        owner = UserFactory()
        root = DocumentFactory(title="Root title", owner=owner, content=CONTENT)
        make_template(targets=("Title", "Code"), custom_field=code_field, owner=owner)
        make_template("Private", targets=("ASN",), owner=UserFactory())

        version = consume(root_document_id=root.pk)

        root.refresh_from_db()
        assert version.root_document_id == root.pk
        assert root.title == "Zone title"
        assert custom_field_value(root, code_field) == "INV42"
        assert root.archive_serial_number is None
        assert version.title == "Root title"
        assert custom_field_value(version, code_field) is None
