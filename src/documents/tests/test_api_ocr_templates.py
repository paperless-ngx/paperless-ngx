"""Tests for the OCR Template API."""

from __future__ import annotations

import functools
import subprocess
from io import BytesIO
from typing import TYPE_CHECKING
from typing import Any

import pytest
from django.db import IntegrityError
from django.utils import timezone
from PIL import Image
from rest_framework import status

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import MatchingModel
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.parsers import ParseError
from documents.search import get_backend
from documents.signals import document_consumption_finished
from documents.tasks import extract_zones
from paperless_testing.factories import CustomFieldFactory
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import OcrTemplateFactory
from paperless_testing.factories import OcrTemplateZoneFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global
from paperless_testing.permissions import grant_object

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from unittest.mock import MagicMock

    from django.contrib.auth.models import User
    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
    from pytest_mock import MockerFixture
    from rest_framework.response import Response
    from rest_framework.test import APIClient

    from paperless_testing.dirs import PaperlessDirs

CONTENT = "Northwind Power & Light statement"

ENDPOINT = "/api/ocr_templates/"
RUN_ZONE_OCR_URL = "/api/documents/{pk}/run-zone-ocr/"
PREVIEW_ZONE_URL = f"{ENDPOINT}test-zone/"
SKIPPED_NO_TEMPLATE = {"status": "skipped", "reason": "no_template", "results": []}


def template_payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "Invoice Template",
        "match": "Northwind",
        "matching_algorithm": MatchingModel.MATCH_ANY,
        "default_page": 0,
        "source_width": 2480,
        "source_height": 3508,
        "enabled": True,
        "zones": [],
    }
    data.update(overrides)
    return data


def zone_payload(custom_field_id: int | None, **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": "Zone 1",
        "custom_field": custom_field_id,
        "x": 100,
        "y": 100,
        "width": 200,
        "height": 50,
        "ocr_language": "deu+eng",
        "transform": "strip",
        "order": 0,
    }
    data.update(overrides)
    return data


@pytest.fixture
def text_field(db: None) -> CustomField:
    return CustomFieldFactory(
        name="Invoice Number",
        data_type=CustomField.FieldDataType.STRING,
    )


@pytest.fixture
def date_field(db: None) -> CustomField:
    return CustomFieldFactory(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.DATE,
    )


@pytest.fixture
def doclink_field(db: None) -> CustomField:
    return CustomFieldFactory(
        name="Related Docs",
        data_type=CustomField.FieldDataType.DOCUMENTLINK,
    )


@pytest.fixture
def text_zone_payload(text_field: CustomField) -> Callable[..., dict[str, Any]]:
    """Zone payload builder whose custom field defaults to the text field."""
    return functools.partial(zone_payload, text_field.pk)


def write_blank_png(path: Path) -> None:
    """Write a blank 100x100 white PNG to the given path."""
    with Image.new("RGB", (100, 100), "white") as image:
        image.save(path, format="PNG")


def title_template(
    name: str,
    owner: User | None = None,
    **kwargs: Any,
) -> OcrTemplate:
    """Build a template matching "Northwind" with one 20x20 title zone."""
    template = OcrTemplateFactory(
        name=name,
        owner=owner,
        match="Northwind",
        **kwargs,
    )
    OcrTemplateZoneFactory(
        template=template,
        name=name,
        width=20,
        height=20,
    )
    return template


@pytest.fixture
def mock_extract(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("documents.zone_ocr.run_zone_extraction")


@pytest.fixture
def mock_preview(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("documents.zone_ocr.extract_zone_preview")


@pytest.fixture
def mock_render(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("documents.views.rasterize_pdf_page_to_png")


def detail_url(pk: int) -> str:
    return f"{ENDPOINT}{pk}/"


def preview_url(document: Document, page: int = 0) -> str:
    return f"{ENDPOINT}document-page-image/{document.pk}/{page}/"


def preview_zone(
    client: APIClient,
    document: Document,
    **zone: Any,
) -> Response:
    return client.post(
        PREVIEW_ZONE_URL,
        {
            "document": document.pk,
            "zone": {"width": 100, "height": 50, **zone},
        },
        format="json",
    )


@pytest.fixture
def preview_user(db: None) -> User:
    user = UserFactory()
    grant_global(user, "view_ocrtemplate", "add_ocrtemplate", "view_document")
    return user


@pytest.fixture
def preview_client(rest_api_client: APIClient, preview_user: User) -> APIClient:
    rest_api_client.force_authenticate(preview_user)
    return rest_api_client


@pytest.fixture
def preview_document(preview_user: User, paperless_dirs: PaperlessDirs) -> Document:
    document = DocumentFactory(
        owner=preview_user,
        page_count=3,
        mime_type="application/pdf",
    )
    document.source_path.write_bytes(b"test document")
    return document


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestZoneOcrIndexing:
    """Zone OCR results are reflected in the search index."""

    @pytest.mark.parametrize(
        "entry_point",
        [
            pytest.param("ingestion", id="ingestion"),
            pytest.param("single", id="single"),
            pytest.param("bulk", id="bulk"),
        ],
    )
    @pytest.mark.parametrize(
        "versioned",
        [
            pytest.param(False, id="original"),
            pytest.param(True, id="versioned"),
        ],
    )
    def test_zone_ocr_indexes_extracted_metadata(
        self,
        entry_point: str,
        versioned: bool,  # noqa: FBT001
        admin_client: APIClient,
        django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document (optionally with an uploaded version) indexed for search
            - An OCR template with a title zone and a custom field zone
        WHEN:
            - Zone OCR runs through ingestion, the single-document API or the
              bulk task
        THEN:
            - The root document title and custom field are updated
            - The search index reflects the new title and custom field value
            - A version document is left untouched
        """
        document = DocumentFactory(
            title="Before OCR",
            content="Previous layout" if versioned else CONTENT,
            mime_type="image/png",
            page_count=2 if versioned else 1,
        )
        file_document = document
        if versioned:
            file_document = DocumentFactory(
                root_document=document,
                version_index=1,
                title="Uploaded version",
                content=CONTENT,
                mime_type="image/png",
                page_count=1,
            )
        write_blank_png(file_document.source_path)
        template = OcrTemplateFactory(
            name="Invoice template",
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        field = CustomFieldFactory(name="Invoice code", data_type="string")
        OcrTemplateZoneFactory(
            template=template,
            name="Title",
            page=-1,
            width=50,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Invoice code",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=field,
            page=-1,
            y=50,
            width=50,
            order=1,
        )
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="After OCR",
                stderr="",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="INV42",
                stderr="",
            ),
        ]

        backend = get_backend()
        if entry_point != "ingestion":
            backend.add_or_update(document)
            assert backend.search_ids("title:before", user=None) == [document.pk]

        with django_capture_on_commit_callbacks(execute=True):
            if entry_point == "ingestion":
                document_consumption_finished.send(sender=None, document=file_document)
            elif entry_point == "single":
                response = admin_client.post(
                    RUN_ZONE_OCR_URL.format(pk=document.pk),
                )
                assert response.status_code == status.HTTP_200_OK
            else:
                extract_zones(document.pk, template.pk)

        document.refresh_from_db()
        assert document.title == "After OCR"
        if versioned:
            file_document.refresh_from_db()
            assert file_document.title == "Uploaded version"
            assert not file_document.custom_fields.exists()
        assert backend.search_ids("title:before", user=None) == []
        assert backend.search_ids("title:after", user=None) == [document.pk]
        assert backend.search_ids("custom_fields.value:INV42", user=None) == [
            document.pk,
        ]


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateCreate:
    """Creating OCR templates through the API."""

    def test_creates_template(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A string custom field exists for the zone
        WHEN:
            - API request to create an OCR template with one zone
        THEN:
            - The template and zone are created
        """
        data = template_payload(
            zones=[
                text_zone_payload(
                    name="Invoice Number",
                    x=1500,
                    y=200,
                    width=800,
                    height=100,
                ),
            ],
        )
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_201_CREATED

        result = resp.json()
        assert result["name"] == "Invoice Template"
        assert result["match"] == "Northwind"
        assert result["matching_algorithm"] == MatchingModel.MATCH_ANY
        assert len(result["zones"]) == 1
        assert result["zones"][0]["name"] == "Invoice Number"
        assert OcrTemplate.objects.count() == 1
        assert OcrTemplateZone.objects.count() == 1

    def test_sets_owner(
        self,
        admin_client: APIClient,
        admin_user: User,
    ) -> None:
        """
        GIVEN:
            - A user creating an OCR template
        WHEN:
            - API request to create it without an owner
        THEN:
            - The requesting user owns the template
        """
        response = admin_client.post(ENDPOINT, template_payload(), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert OcrTemplate.objects.get().owner == admin_user

    def test_multiple_zones(
        self,
        admin_client: APIClient,
        text_field: CustomField,
        date_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - Multiple custom fields exist
        WHEN:
            - A template with multiple zones is created
        THEN:
            - All zones are created
        """
        data = template_payload(
            zones=[
                zone_payload(text_field.pk, name="Invoice Number"),
                zone_payload(date_field.pk, name="Invoice Date", order=1),
            ],
        )
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["zones"]) == 2
        assert OcrTemplateZone.objects.count() == 2

    def test_no_zones(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - Valid template data without zones
        WHEN:
            - Template is created
        THEN:
            - Template is created with no zones
        """
        resp = admin_client.post(ENDPOINT, template_payload(), format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["zones"]) == 0

    def test_custom_and_builtin_zones_can_have_no_custom_field(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A payload with a custom zone and a title zone, neither with a
              custom field
        WHEN:
            - API request to create the template
        THEN:
            - Both zones are created with no custom field
            - The zone string representation names the template and zone
        """
        data = template_payload(
            zones=[
                text_zone_payload(custom_field=None),
                text_zone_payload(name="Title", target="title", custom_field=None),
            ],
        )
        response = admin_client.post(ENDPOINT, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert [z["custom_field"] for z in response.json()["zones"]] == [None, None]
        zone = OcrTemplateZone.objects.get(name="Title")
        assert str(zone) == f"{zone.template.name} -> Title"

    def test_template_creation_rolls_back_when_a_zone_cannot_be_saved(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A payload with two zones, the second of which fails to save
        WHEN:
            - API request to create the template
        THEN:
            - The error propagates
            - Neither the template nor the first zone is persisted
        """
        data = template_payload(
            zones=[text_zone_payload(), text_zone_payload(name="Broken")],
        )
        create = OcrTemplateZone.objects.create

        def create_zone(**kwargs: Any) -> OcrTemplateZone:
            if kwargs["name"] == "Broken":
                raise IntegrityError("Zone save failed")
            return create(**kwargs)

        mocker.patch(
            "documents.serialisers.OcrTemplateZone.objects.create",
            side_effect=create_zone,
        )
        with pytest.raises(IntegrityError):
            admin_client.post(ENDPOINT, data, format="json")
        assert OcrTemplate.objects.count() == 0
        assert OcrTemplateZone.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplatePermissions:
    """Visibility and modification rights for OCR templates."""

    def test_list_only_shows_permitted_templates(
        self,
        regular_user: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - Templates that are unowned, owned by the user, owned by another
              user, and owned by another user but shared with the user
        WHEN:
            - The user lists OCR templates
        THEN:
            - Only the unowned, owned and shared templates are returned
        """
        other = UserFactory()
        grant_global(regular_user, "view_ocrtemplate")

        title_template("Unowned")
        title_template("Mine", owner=regular_user)
        title_template("Private", owner=other)
        grant_object(
            regular_user,
            title_template("Shared", owner=other),
            "view_ocrtemplate",
        )

        response = user_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert sorted(t["name"] for t in response.json()["results"]) == [
            "Mine",
            "Shared",
            "Unowned",
        ]

    def test_cannot_change_another_users_template(
        self,
        regular_user: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A template owned by another user
        WHEN:
            - A user with global change permission tries to update it
        THEN:
            - The update is refused until the user is granted change on it
        """
        other = UserFactory()
        grant_global(regular_user, "view_ocrtemplate", "change_ocrtemplate")
        template = OcrTemplateFactory(
            name="Private",
            match="Northwind",
            owner=other,
        )
        grant_object(regular_user, template, "view_ocrtemplate")
        url = detail_url(template.pk)

        response = user_client.patch(url, {"name": "Renamed"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        grant_object(regular_user, template, "change_ocrtemplate")
        response = user_client.patch(url, {"name": "Renamed"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        template.refresh_from_db()
        assert template.name == "Renamed"
        assert template.owner == other

    def test_unauthenticated_rejected(self, rest_api_client: APIClient) -> None:
        """
        GIVEN:
            - An unauthenticated client
        WHEN:
            - The OCR templates are listed
        THEN:
            - The request is rejected with 401 or 403
        """
        resp = rest_api_client.get(ENDPOINT)
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.parametrize(
        "make_data",
        [
            pytest.param(lambda editor: {"owner": editor.pk}, id="transfer-ownership"),
            pytest.param(
                lambda editor: {"set_permissions": {"view": {"users": []}}},
                id="change-sharing",
            ),
        ],
    )
    def test_shared_editor_cannot_transfer_ownership_or_change_sharing(
        self,
        regular_user: User,
        user_client: APIClient,
        admin_user: User,
        make_data: Callable[[User], dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A template owned by another user and shared with an editor
        WHEN:
            - The editor tries to transfer ownership or change sharing
        THEN:
            - The request is refused and the owner is unchanged
        """
        grant_global(regular_user, "view_ocrtemplate", "change_ocrtemplate")
        template = OcrTemplateFactory(
            name="Shared",
            owner=admin_user,
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        grant_object(regular_user, template, "view_ocrtemplate", "change_ocrtemplate")

        response = user_client.patch(
            detail_url(template.pk),
            make_data(regular_user),
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        template.refresh_from_db()
        assert template.owner == admin_user


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateSampleDocument:
    """The sample document of a template is limited to what the user can see."""

    @pytest.fixture
    def editor(self, regular_user: User) -> User:
        grant_global(
            regular_user,
            "view_ocrtemplate",
            "add_ocrtemplate",
            "change_ocrtemplate",
            "view_document",
        )
        return regular_user

    @pytest.mark.usefixtures("editor")
    def test_create_rejects_an_invisible_sample_document(
        self,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user and not shared with the editor
        WHEN:
            - The editor creates a template using it as the sample document
        THEN:
            - 400 is returned on the sample_document field and no template is
              created
        """
        document = DocumentFactory(owner=UserFactory())

        response = user_client.post(
            ENDPOINT,
            template_payload(sample_document=document.pk),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sample_document" in response.json()
        assert not OcrTemplate.objects.exists()

    def test_update_rejects_an_invisible_sample_document(
        self,
        editor: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A template owned by the editor
            - A document owned by another user and not shared with the editor
        WHEN:
            - The editor patches the template to use it as the sample document
        THEN:
            - 400 is returned on the sample_document field and the template
              is unchanged
        """
        document = DocumentFactory(owner=UserFactory())
        template = OcrTemplateFactory(owner=editor, match="Northwind")

        response = user_client.patch(
            detail_url(template.pk),
            {"sample_document": document.pk},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sample_document" in response.json()
        template.refresh_from_db()
        assert template.sample_document is None

    def test_accepts_visible_sample_documents_and_clearing(
        self,
        editor: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A document owned by the editor and one shared with the editor
        WHEN:
            - The editor creates a template with the owned document, patches in
              the shared document, then clears it
        THEN:
            - Each request succeeds and the template stores the value
        """
        owned = DocumentFactory(owner=editor)
        shared = DocumentFactory(owner=UserFactory())
        grant_object(editor, shared, "view_document")

        response = user_client.post(
            ENDPOINT,
            template_payload(sample_document=owned.pk),
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["sample_document"] == owned.pk
        url = detail_url(response.json()["id"])

        for value in (shared.pk, None):
            response = user_client.patch(
                url,
                {"sample_document": value},
                format="json",
            )
            assert response.status_code == status.HTTP_200_OK
            assert response.json()["sample_document"] == value

    def test_collaborator_can_save_a_template_keeping_its_sample_document(
        self,
        editor: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A template owned by another user and shared with the editor for
              view and change, whose sample document the editor cannot see
        WHEN:
            - The editor saves the template as retrieved with a new name, and
              then tries to switch to another document they cannot see
        THEN:
            - The save succeeds and keeps the stored sample document
            - The switch is rejected with 400
        """
        owner = UserFactory()
        sample = DocumentFactory(owner=owner)
        template = OcrTemplateFactory(
            owner=owner,
            match="Northwind",
            sample_document=sample,
        )
        grant_object(editor, template, "view_ocrtemplate", "change_ocrtemplate")

        payload = user_client.get(detail_url(template.pk)).json()
        payload["name"] = "Renamed"
        response = user_client.put(detail_url(template.pk), payload, format="json")

        assert response.status_code == status.HTTP_200_OK
        template.refresh_from_db()
        assert template.name == "Renamed"
        assert template.sample_document == sample

        other = DocumentFactory(owner=owner)
        response = user_client.patch(
            detail_url(template.pk),
            {"sample_document": other.pk},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "sample_document" in response.json()
        template.refresh_from_db()
        assert template.sample_document == sample

    def test_reading_shows_a_sample_document_the_viewer_cannot_see(
        self,
        regular_user: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A template visible to the user whose stored sample document
              belongs to another user
        WHEN:
            - The user retrieves and lists templates
        THEN:
            - Both return 200 with the stored sample document pk
        """
        grant_global(regular_user, "view_ocrtemplate")
        document = DocumentFactory(owner=UserFactory())
        template = OcrTemplateFactory(
            owner=regular_user,
            match="Northwind",
            sample_document=document,
        )

        response = user_client.get(detail_url(template.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["sample_document"] == document.pk

        response = user_client.get(ENDPOINT)
        assert response.status_code == status.HTTP_200_OK
        assert [t["sample_document"] for t in response.json()["results"]] == [
            document.pk,
        ]


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateValidation:
    """Validation of OCR template and zone payloads."""

    @pytest.mark.parametrize(
        ("template_overrides", "zone_overrides"),
        [
            pytest.param({"source_width": 0}, None, id="zero-source-width"),
            pytest.param({"source_height": 0}, None, id="zero-source-height"),
            pytest.param({}, {"width": 0}, id="zero-zone-width"),
            pytest.param({}, {"height": 0}, id="zero-zone-height"),
            pytest.param(
                {"source_width": 1000},
                {"x": 800, "width": 300},  # 800+300 > 1000
                id="zone-exceeds-source-width",
            ),
            pytest.param(
                {"source_height": 1000},
                {"y": 900, "height": 200},  # 900+200 > 1000
                id="zone-exceeds-source-height",
            ),
        ],
    )
    def test_rejects_invalid_dimensions(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
        template_overrides: dict[str, Any],
        zone_overrides: dict[str, Any] | None,
    ) -> None:
        """
        GIVEN:
            - Template data with a zero source dimension, a zero zone
              dimension or a zone extending beyond the source image
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        zones = [] if zone_overrides is None else [text_zone_payload(**zone_overrides)]
        data = template_payload(zones=zones, **template_overrides)
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_rejects_automatic_matching(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A template payload with automatic matching
        WHEN:
            - API request to create it
        THEN:
            - The request is rejected, automatic matching needs assigned
              documents to learn from
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(matching_algorithm=MatchingModel.MATCH_AUTO),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert OcrTemplate.objects.count() == 0

    def test_zone_unsupported_custom_field_type_rejected(
        self,
        admin_client: APIClient,
        doclink_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A zone targeting a DOCUMENTLINK custom field, which can't be
              populated via OCR
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        data = template_payload(zones=[zone_payload(doclink_field.pk)])
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_zone_bounds_use_the_zones_own_source_dimensions(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A template with a small source size and a zone that only fits
              within its own, larger zone source size
        WHEN:
            - The template is created, then created again with a smaller zone
              source width that the zone no longer fits
        THEN:
            - The first request succeeds, the second is rejected
        """
        data = template_payload(
            source_width=500,
            source_height=500,
            zones=[
                text_zone_payload(
                    x=700,
                    y=600,
                    width=200,
                    height=100,
                    zone_source_width=1000,
                    zone_source_height=1000,
                ),
            ],
        )
        response = admin_client.post(ENDPOINT, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data["name"] = "Invalid bounds"
        data["zones"][0]["zone_source_width"] = 800
        response = admin_client.post(ENDPOINT, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_changing_source_dimensions_checks_existing_zones(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A template with a zone
        WHEN:
            - The source width is patched below, then above, the zone extent
        THEN:
            - The smaller width is rejected, the larger one accepted
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(zones=[text_zone_payload()]),
            format="json",
        )
        url = detail_url(response.json()["id"])
        response = admin_client.patch(url, {"source_width": 200}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        response = admin_client.patch(url, {"source_width": 1000}, format="json")
        assert response.status_code == status.HTTP_200_OK

    @pytest.mark.parametrize(
        ("changes", "expected_status"),
        [
            pytest.param(
                {"x": 900, "width": 200},
                status.HTTP_400_BAD_REQUEST,
                id="exceeds-width",
            ),
            pytest.param(
                {"y": 990, "height": 50},
                status.HTTP_400_BAD_REQUEST,
                id="exceeds-height",
            ),
            pytest.param({}, status.HTTP_200_OK, id="within-bounds"),
        ],
    )
    def test_partial_zone_replacement_checks_saved_dimensions(
        self,
        admin_client: APIClient,
        admin_user: User,
        text_zone_payload: Callable[..., dict[str, Any]],
        changes: dict[str, int],
        expected_status: int,
    ) -> None:
        """
        GIVEN:
            - A saved 1000x1000 template
        WHEN:
            - A PATCH replaces zones with one that either extends beyond the
              saved source dimensions or lies within them
        THEN:
            - The request is rejected when the zone is out of bounds and
              succeeds when it is within them
        """
        template = OcrTemplateFactory(
            name="Test",
            owner=admin_user,
        )
        response = admin_client.patch(
            detail_url(template.pk),
            {"zones": [text_zone_payload(**changes)]},
            format="json",
        )
        assert response.status_code == expected_status

    def test_partial_zone_replacement_requires_complete_zones(
        self,
        admin_client: APIClient,
        admin_user: User,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - A PATCH replaces zones with an incomplete zone
        THEN:
            - The request is rejected and the original zone is kept
        """
        template = OcrTemplateFactory(
            name="Test",
            owner=admin_user,
        )
        zone = OcrTemplateZoneFactory(
            template=template,
            name="Original",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            width=10,
            height=10,
        )
        response = admin_client.patch(
            detail_url(template.pk),
            {"zones": [{"name": "Incomplete"}]},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert list(template.zones.all()) == [zone]

    @pytest.mark.parametrize(
        "page",
        [
            pytest.param(0, id="zero"),
            pytest.param(-2, id="below-last-page"),
            pytest.param("invalid", id="not-a-number"),
        ],
    )
    def test_invalid_page_numbers_are_rejected(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
        page: int | str,
    ) -> None:
        """
        GIVEN:
            - A zone with an invalid page number
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(zones=[text_zone_payload(page=page)]),
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.parametrize(
        ("target", "use_field", "expected"),
        [
            pytest.param(
                "custom_field",
                True,
                status.HTTP_201_CREATED,
                id="custom-field-with-field",
            ),
            pytest.param(
                "custom_field",
                False,
                status.HTTP_201_CREATED,
                id="custom-field-unassigned",
            ),
            pytest.param("title", False, status.HTTP_201_CREATED, id="title"),
            pytest.param(
                "title",
                True,
                status.HTTP_400_BAD_REQUEST,
                id="title-with-field",
            ),
            pytest.param(
                "created",
                True,
                status.HTTP_400_BAD_REQUEST,
                id="created-with-field",
            ),
        ],
    )
    def test_only_custom_field_targets_set_a_custom_field(
        self,
        admin_client: APIClient,
        text_field: CustomField,
        target: str,
        use_field: bool,  # noqa: FBT001
        expected: int,
    ) -> None:
        """
        GIVEN:
            - A zone with a custom field or built-in target, with or without a
              custom field
        WHEN:
            - Create is attempted
        THEN:
            - A custom field target is accepted with or without a field
            - A built-in target is rejected when it sets a custom field
        """
        zone = zone_payload(text_field.pk if use_field else None, target=target)

        response = admin_client.post(
            ENDPOINT,
            template_payload(zones=[zone]),
            format="json",
        )

        assert response.status_code == expected
        if expected == status.HTTP_400_BAD_REQUEST:
            assert "custom_field" in response.json()["zones"]["0"]

    @pytest.mark.parametrize(
        ("pattern", "expected"),
        [
            pytest.param("", status.HTTP_201_CREATED, id="blank"),
            pytest.param(r"INV-\d+", status.HTTP_201_CREATED, id="valid"),
            pytest.param("INV-(", status.HTTP_400_BAD_REQUEST, id="unbalanced"),
            pytest.param("[a-", status.HTTP_400_BAD_REQUEST, id="unclosed-set"),
        ],
    )
    def test_validation_regex_must_compile(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
        pattern: str,
        expected: int,
    ) -> None:
        """
        GIVEN:
            - A zone with a blank, valid or invalid validation regex
        WHEN:
            - Create is attempted
        THEN:
            - Blank and valid patterns are accepted, invalid ones are rejected
              on the zone's validation_regex field
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(zones=[text_zone_payload(validation_regex=pattern)]),
            format="json",
        )

        assert response.status_code == expected
        if expected == status.HTTP_400_BAD_REQUEST:
            assert "validation_regex" in response.json()["zones"]["0"]

    def test_zone_preview_rejects_an_invalid_validation_regex(
        self,
        admin_client: APIClient,
        mock_preview: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A zone preview request with an invalid validation regex
        WHEN:
            - The preview is requested
        THEN:
            - 400 is returned and no extraction runs
        """
        document = DocumentFactory(mime_type="image/png")

        response = preview_zone(admin_client, document, validation_regex="INV-(")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_preview.assert_not_called()

    @pytest.mark.parametrize(
        "formats",
        [
            pytest.param([], id="empty-list"),
            pytest.param("invalid", id="string"),
            pytest.param({"title": []}, id="list-value"),
            pytest.param({"title": None}, id="null-value"),
        ],
    )
    def test_combine_formats_must_map_keys_to_strings(
        self,
        admin_client: APIClient,
        formats: object,
    ) -> None:
        """
        GIVEN:
            - combine_formats that is not a mapping of keys to strings
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(combine_formats=formats),
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_combine_formats_accepts_string_values(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - combine_formats mapping a key to a string
        WHEN:
            - Create is attempted
        THEN:
            - The template is created and the mapping is returned unchanged
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(
                zones=[
                    zone_payload(None, name="A", target="title"),
                    zone_payload(None, name="B", target="title"),
                ],
                combine_formats={"title": " {A} - {B} "},
            ),
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["combine_formats"] == {"title": " {A} - {B} "}

    def test_zone_names_must_be_unique(
        self,
        admin_client: APIClient,
        text_zone_payload: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - Two zones with the same name
        WHEN:
            - Create is attempted
        THEN:
            - 400 is returned naming the duplicate
        """
        response = admin_client.post(
            ENDPOINT,
            template_payload(
                zones=[
                    text_zone_payload(name="Total"),
                    text_zone_payload(name="Total"),
                ],
            ),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Total" in str(response.json()["zones"])

    @pytest.mark.parametrize(
        ("keys", "expected"),
        [
            pytest.param(["title"], status.HTTP_201_CREATED, id="title-zone"),
            pytest.param(["field"], status.HTTP_201_CREATED, id="custom-field-zone"),
            pytest.param(["asn"], status.HTTP_400_BAD_REQUEST, id="no-asn-zone"),
            pytest.param(["999"], status.HTTP_400_BAD_REQUEST, id="unknown-field"),
        ],
    )
    def test_combine_format_keys_must_be_zone_targets(
        self,
        admin_client: APIClient,
        text_field: CustomField,
        keys: list[str],
        expected: int,
    ) -> None:
        """
        GIVEN:
            - A template with a title zone and a custom field zone, and a
              combine format keyed by a target that may or may not be used
        WHEN:
            - Create is attempted
        THEN:
            - Keys of the zones' targets are accepted and others are rejected
              on combine_formats
        """
        formats = {
            (str(text_field.pk) if key == "field" else key): "{Title}" for key in keys
        }

        response = admin_client.post(
            ENDPOINT,
            template_payload(
                zones=[
                    zone_payload(None, name="Title", target="title"),
                    zone_payload(text_field.pk, name="Number"),
                ],
                combine_formats=formats,
            ),
            format="json",
        )

        assert response.status_code == expected
        if expected == status.HTTP_400_BAD_REQUEST:
            assert "combine_formats" in response.json()

    def test_combine_formats_patch_checks_saved_zones(
        self,
        admin_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A saved template with only a title zone
        WHEN:
            - combine_formats is patched without zones, keyed by title and then
              by asn
        THEN:
            - The title key is accepted and the asn key is rejected
        """
        template = OcrTemplateFactory(match="Northwind")
        OcrTemplateZoneFactory(template=template, target="title")

        response = admin_client.patch(
            detail_url(template.pk),
            {"combine_formats": {"title": "{A}"}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        response = admin_client.patch(
            detail_url(template.pk),
            {"combine_formats": {"asn": "{A}"}},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateList:
    """Listing OCR templates."""

    def test_lists_templates(
        self,
        admin_client: APIClient,
        text_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - The templates are listed
        THEN:
            - The template is returned with its zone
        """
        template = OcrTemplateFactory(
            name="Test Template",
            match="Northwind",
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone 1",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            x=100,
            y=100,
            width=200,
        )

        resp = admin_client.get(ENDPOINT)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["count"] == 1
        assert len(data["results"][0]["zones"]) == 1

    def test_empty(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - No templates
        WHEN:
            - The templates are listed
        THEN:
            - The count is zero
        """
        resp = admin_client.get(ENDPOINT)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["count"] == 0


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateUpdate:
    """Updating OCR templates through the API."""

    def test_update_template_replaces_zones(
        self,
        admin_client: APIClient,
        text_field: CustomField,
        date_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - PUT with a new name and a different zone
        THEN:
            - The template is renamed and its zones are replaced by the new set
        """
        template = OcrTemplateFactory(
            name="Old Name",
            match="Northwind",
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Old Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            height=100,
        )

        data = template_payload(
            name="New Name",
            zones=[zone_payload(date_field.pk, name="New Zone")],
        )
        resp = admin_client.put(detail_url(template.pk), data, format="json")
        assert resp.status_code == status.HTTP_200_OK

        template.refresh_from_db()
        assert template.name == "New Name"
        assert OcrTemplateZone.objects.count() == 1
        assert OcrTemplateZone.objects.first().name == "New Zone"

    def test_template_update_rolls_back_without_losing_previous_zones(
        self,
        admin_client: APIClient,
        admin_user: User,
        text_zone_payload: Callable[..., dict[str, Any]],
        mocker: MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A template with one zone and a zone save that fails
        WHEN:
            - PUT with a new name and zones
        THEN:
            - The error propagates
            - The template name and original zones are unchanged
        """
        template = OcrTemplateFactory(
            name="Original",
            owner=admin_user,
        )
        zone = OcrTemplateZoneFactory(
            template=template,
            name="Original zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            width=10,
            height=10,
        )
        data = template_payload(name="Changed", zones=[text_zone_payload()])
        mocker.patch(
            "documents.serialisers.OcrTemplateZone.objects.create",
            side_effect=IntegrityError("Zone save failed"),
        )
        with pytest.raises(IntegrityError):
            admin_client.put(detail_url(template.pk), data, format="json")
        template.refresh_from_db()
        assert template.name == "Original"
        assert list(template.zones.all()) == [zone]

    def test_explicit_empty_zones_removes_all_zones(
        self,
        admin_client: APIClient,
        admin_user: User,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - PATCH with an explicit empty zones list
        THEN:
            - All zones are removed
        """
        template = OcrTemplateFactory(
            name="Test",
            owner=admin_user,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            width=10,
            height=10,
        )
        response = admin_client.patch(
            detail_url(template.pk),
            {"zones": []},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert not template.zones.exists()

    def test_patch_toggle_enabled(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - An enabled template
        WHEN:
            - PATCH with enabled false
        THEN:
            - The template is disabled
        """
        template = OcrTemplateFactory(
            name="Toggle Test",
            match="Northwind",
        )

        resp = admin_client.patch(
            detail_url(template.pk),
            {"enabled": False},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        template.refresh_from_db()
        assert not template.enabled

    def test_patch_preserves_zones(
        self,
        admin_client: APIClient,
        text_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - PATCH without a zones field
        THEN:
            - The existing zone is not deleted
        """
        template = OcrTemplateFactory(
            name="Patch Test",
            match="Northwind",
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Existing Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            height=100,
        )

        resp = admin_client.patch(
            detail_url(template.pk),
            {"name": "Updated Name"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert OcrTemplateZone.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateDelete:
    """Deleting OCR templates through the API."""

    def test_cascades_zones(
        self,
        admin_client: APIClient,
        text_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A template with one zone
        WHEN:
            - The template is deleted
        THEN:
            - The template and its zone are removed
        """
        template = OcrTemplateFactory(
            name="To Delete",
            match="Northwind",
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            height=100,
        )

        resp = admin_client.delete(detail_url(template.pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert OcrTemplate.objects.count() == 0
        assert OcrTemplateZone.objects.count() == 0

    def test_nonexistent_returns_404(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - No template with the requested id
        WHEN:
            - A delete request is made for it
        THEN:
            - 404 is returned
        """
        resp = admin_client.delete(detail_url(99999))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRunZoneOcr:
    """Running zone OCR on documents through the run-zone-ocr endpoint."""

    @pytest.mark.parametrize(
        "template_kwargs_list",
        [
            pytest.param([], id="no-templates"),
            pytest.param(
                [{"name": "Disabled template", "match": "Northwind", "enabled": False}],
                id="disabled-template",
            ),
            pytest.param(
                [{"name": "Other sender", "match": "Contoso"}],
                id="non-matching-template",
            ),
        ],
    )
    def test_without_enabled_matching_template_is_skipped(
        self,
        admin_client: APIClient,
        mock_extract: MagicMock,
        template_kwargs_list: list[dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A document and either no templates, only a matching disabled
              template, or only a template that does not match the document
        WHEN:
            - Zone OCR is run on the document
        THEN:
            - The run is skipped with reason no_template and nothing is extracted
        """
        document = DocumentFactory(content=CONTENT)
        for template_kwargs in template_kwargs_list:
            OcrTemplateFactory(**template_kwargs)

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == SKIPPED_NO_TEMPLATE
        mock_extract.assert_not_called()

    def test_applies_a_chosen_template(
        self,
        admin_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A disabled template that does not match the document
        WHEN:
            - Zone OCR is run on the document with that template chosen
        THEN:
            - The template is applied anyway, since it was chosen explicitly
        """
        document = DocumentFactory(content=CONTENT, mime_type="application/pdf")
        document.source_path.write_bytes(b"test PDF")
        template = OcrTemplateFactory(
            name="Manual only",
            match="Contoso",
            enabled=False,
        )

        response = admin_client.post(
            RUN_ZONE_OCR_URL.format(pk=document.pk),
            {"template": template.pk},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "completed"
        mock_extract.assert_called_once_with(
            document,
            templates=[template],
            reindex=True,
        )

    @pytest.mark.parametrize(
        "version",
        [
            pytest.param("root", id="root-version"),
            pytest.param("older", id="older-version"),
        ],
    )
    def test_matches_the_requested_file_version(
        self,
        admin_client: APIClient,
        mock_extract: MagicMock,
        version: str,
    ) -> None:
        """
        GIVEN:
            - A document with two versions, the newest not matching the template
        WHEN:
            - Zone OCR is run for the root document or an older version
        THEN:
            - The template is applied to the requested file document
        """
        mock_extract.return_value = []
        document = DocumentFactory(content=CONTENT)
        older = DocumentFactory(
            root_document=document,
            version_index=1,
            content=CONTENT,
        )
        DocumentFactory(root_document=document, version_index=2, content="Contoso")
        template = OcrTemplateFactory(
            name="Northwind",
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        file_document = {"root": document, "older": older}[version]
        file_document.source_path.write_bytes(b"test PDF")

        response = admin_client.post(
            f"{RUN_ZONE_OCR_URL.format(pk=document.pk)}?version={file_document.pk}",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "completed"
        mock_extract.assert_called_once_with(
            file_document,
            templates=[template],
            reindex=True,
        )

    @pytest.mark.parametrize(
        "version",
        [
            pytest.param("invalid", id="not-a-number"),
            pytest.param("unrelated", id="unrelated-document"),
            pytest.param("deleted", id="deleted-version"),
        ],
    )
    def test_rejects_invalid_or_unavailable_versions(
        self,
        admin_client: APIClient,
        mock_extract: MagicMock,
        version: str,
    ) -> None:
        """
        GIVEN:
            - A document, an unrelated document and a deleted version
        WHEN:
            - Zone OCR is run with an invalid or unavailable version
        THEN:
            - 404 is returned and nothing is extracted
        """
        document = DocumentFactory()
        unrelated = DocumentFactory()
        deleted = DocumentFactory(
            root_document=document,
            version_index=1,
            deleted_at=timezone.now(),
        )
        value = {
            "invalid": "invalid",
            "unrelated": unrelated.pk,
            "deleted": deleted.pk,
        }[version]

        response = admin_client.post(
            f"{RUN_ZONE_OCR_URL.format(pk=document.pk)}?version={value}",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_extract.assert_not_called()

    def test_rejects_an_unknown_template(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - A document
        WHEN:
            - Zone OCR is run with a template id that does not exist
        THEN:
            - 400 is returned
        """
        document = DocumentFactory(content=CONTENT)

        response = admin_client.post(
            RUN_ZONE_OCR_URL.format(pk=document.pk),
            {"template": 999},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_document_is_an_error(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - No document with the requested id
        WHEN:
            - Zone OCR is run on it
        THEN:
            - 404 is returned
        """
        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=99999))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_missing_file_is_an_error(
        self,
        admin_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document with a matching template but no file on disk
        WHEN:
            - Zone OCR is run on the document
        THEN:
            - 404 is returned with a file not found error and nothing is extracted
        """
        document = DocumentFactory(content=CONTENT)
        OcrTemplateFactory(
            name="Template",
            match="Northwind",
        )

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.json() == {"error": "Document file not found"}
        mock_extract.assert_not_called()

    def test_reports_completed_results(
        self,
        admin_client: APIClient,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document and a matching template with a title zone
        WHEN:
            - Zone OCR is run on the document
        THEN:
            - The completed result lists the extracted title value
        """
        document = DocumentFactory(
            content=CONTENT,
            mime_type="application/pdf",
        )
        write_blank_png(document.source_path)
        mock_zone_ocr_run.return_value.stdout = "Extracted title"
        template = OcrTemplateFactory(
            name="Template",
            match="Northwind",
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Title zone",
            height=100,
        )

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "status": "completed",
            "results": [
                {
                    "template": template.name,
                    "zone": "Title zone",
                    "custom_field": "Title",
                    "value": "Extracted title",
                    "reason": None,
                },
            ],
        }
        mock_zone_ocr_run.assert_called_once()

    def test_does_not_report_an_old_title_when_extraction_is_empty(
        self,
        admin_client: APIClient,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document with a title and a template whose title zone extracts
              nothing
        WHEN:
            - Zone OCR is run on the document
        THEN:
            - The result has reason no_value and no value
            - The document title is unchanged
        """
        document = DocumentFactory(title="Existing title", content=CONTENT)
        write_blank_png(document.source_path)
        template = OcrTemplateFactory(
            name="Template",
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Title",
            width=20,
            height=20,
        )
        mock_zone_ocr_run.return_value.stdout = ""

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["results"][0]["reason"] == "no_value"
        assert response.json()["results"][0]["value"] is None
        document.refresh_from_db()
        assert document.title == "Existing title"

    def test_reports_all_target_types_and_missing_values(
        self,
        admin_client: APIClient,
        mock_zone_ocr_run: MagicMock,
        text_field: CustomField,
        date_field: CustomField,
    ) -> None:
        """
        GIVEN:
            - A document with an existing custom field value and ASN
            - A template with zones for every target type, some extracting nothing
        WHEN:
            - Zone OCR is run with that template chosen
        THEN:
            - Each zone reports the value for its target, or None when missing
        """
        document = DocumentFactory(content=CONTENT, archive_serial_number=123)
        write_blank_png(document.source_path)
        mock_zone_ocr_run.side_effect = [
            subprocess.CompletedProcess(args=[], returncode=0, stdout=value, stderr="")
            for value in [
                "New invoice",
                "",
                "orphan",
                "New title",
                "456",
                "2026-04-13",
            ]
        ]
        template = OcrTemplateFactory(
            name="Test",
            source_width=100,
            source_height=100,
        )
        CustomFieldInstance.objects.create(
            document=document,
            field=text_field,
            value_text="INV-123",
        )
        for name, target, field in [
            ("Present", "custom_field", text_field),
            ("Missing", "custom_field", date_field),
            ("Unassigned", "custom_field", None),
            ("Title", "title", None),
            ("ASN", "asn", None),
            ("Created", "created", None),
        ]:
            OcrTemplateZoneFactory(
                template=template,
                name=name,
                target=target,
                custom_field=field,
                width=10,
                height=10,
            )

        response = admin_client.post(
            RUN_ZONE_OCR_URL.format(pk=document.pk),
            {"template": template.pk},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        values = {
            result["zone"]: result["value"] for result in response.json()["results"]
        }
        assert values == {
            "Present": "New invoice",
            "Missing": None,
            "Unassigned": None,
            "Title": "New title",
            "ASN": 456,
            "Created": "2026-04-13",
        }


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestRunZoneOcrPermissions:
    """Permission checks for the run-zone-ocr endpoint."""

    def test_rejects_a_template_the_user_cannot_view(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - An editor owning a document
            - A template private to another user
        WHEN:
            - The editor runs zone OCR choosing that template
        THEN:
            - 400 is returned, naming the template field, and nothing is
              extracted
        """
        grant_global(regular_user, "view_document", "change_document")
        document = DocumentFactory(content=CONTENT, owner=regular_user)
        template = OcrTemplateFactory(
            name="Private",
            owner=UserFactory(),
        )

        response = user_client.post(
            RUN_ZONE_OCR_URL.format(pk=document.pk),
            {"template": template.pk},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "template" in response.json()
        mock_extract.assert_not_called()

    def test_requires_change_permission_on_the_document(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user
            - A user with global view and change document permissions only
        WHEN:
            - The user runs zone OCR on the document
        THEN:
            - 403 is returned and nothing is extracted
        """
        owner = UserFactory()
        grant_global(regular_user, "view_document", "change_document")
        document = DocumentFactory(content=CONTENT, owner=owner)

        response = user_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_extract.assert_not_called()

    def test_requires_global_change_permission(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A user owning a document but holding only view and add document
              permissions
        WHEN:
            - The user runs zone OCR on the document
        THEN:
            - 403 is returned and nothing is extracted
        """
        grant_global(regular_user, "view_document", "add_document")
        document = DocumentFactory(content=CONTENT, owner=regular_user)

        response = user_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_extract.assert_not_called()

    def test_does_not_require_document_upload_permission(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A user owning a document and a matching template, holding only
              the change document permission
        WHEN:
            - The user runs zone OCR on the document
        THEN:
            - The request succeeds and extraction runs
        """
        grant_global(regular_user, "change_document")
        document = DocumentFactory(owner=regular_user, content=CONTENT)
        document.source_path.write_bytes(b"test PDF")
        OcrTemplateFactory(
            name="Matching",
            owner=regular_user,
            source_width=100,
            source_height=100,
            match="Northwind",
        )

        response = user_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        mock_extract.assert_called_once()

    def test_skips_templates_private_to_the_requester(
        self,
        admin_client: APIClient,
        admin_user: User,
        mock_extract: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user
            - A matching template private to the requester
        WHEN:
            - The requester runs zone OCR on the document
        THEN:
            - The run is skipped with reason no_template and nothing is extracted
        """
        owner = UserFactory()
        document = DocumentFactory(content=CONTENT, owner=owner)
        OcrTemplateFactory(
            name="Requester's private template",
            owner=admin_user,
            match="Northwind",
            source_width=100,
            source_height=100,
        )

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == SKIPPED_NO_TEMPLATE
        mock_extract.assert_not_called()

    def test_reports_only_templates_visible_to_the_document_owner(
        self,
        admin_client: APIClient,
        admin_user: User,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user
            - Templates owned by the document owner, unowned, shared with the
              document owner, and private to the requester
        WHEN:
            - The requester runs zone OCR on the document
        THEN:
            - Only templates visible to the document owner run and are reported
        """
        owner = UserFactory()
        document = DocumentFactory(content=CONTENT, owner=owner)
        write_blank_png(document.source_path)
        mock_zone_ocr_run.return_value.stdout = "extracted"
        for name, template_owner in [
            ("Owned", owner),
            ("Unowned", None),
            ("Shared", admin_user),
            ("Private", admin_user),
        ]:
            template = title_template(
                name,
                template_owner,
                source_width=100,
                source_height=100,
            )
            if name == "Shared":
                grant_object(owner, template, "view_ocrtemplate")

        response = admin_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert sorted(result["template"] for result in response.json()["results"]) == [
            "Owned",
            "Shared",
            "Unowned",
        ]
        assert mock_zone_ocr_run.call_count == 3

    def test_hides_the_owners_private_templates_from_an_editor(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_zone_ocr_run: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document shared for editing with another user
            - Templates private to the owner, unowned, and shared with both
        WHEN:
            - The editor runs zone OCR without choosing a template
        THEN:
            - Only templates the editor can also view run and are reported
        """
        owner = UserFactory()
        grant_global(regular_user, "view_document", "change_document")
        document = DocumentFactory(content=CONTENT, owner=owner)
        grant_object(regular_user, document, "view_document", "change_document")
        write_blank_png(document.source_path)
        mock_zone_ocr_run.return_value.stdout = "extracted"
        for name, template_owner in [
            ("Owner private", owner),
            ("Unowned", None),
            ("Shared", owner),
        ]:
            template = title_template(
                name,
                template_owner,
                source_width=100,
                source_height=100,
            )
            if name == "Shared":
                grant_object(regular_user, template, "view_ocrtemplate")

        response = user_client.post(RUN_ZONE_OCR_URL.format(pk=document.pk))

        assert response.status_code == status.HTTP_200_OK
        assert sorted(result["template"] for result in response.json()["results"]) == [
            "Shared",
            "Unowned",
        ]
        assert mock_zone_ocr_run.call_count == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestDocumentPageImage:
    """Page image rendering through the document-page-image endpoint."""

    def test_missing_document_and_out_of_range_pages(
        self,
        preview_client: APIClient,
        preview_document: Document,
    ) -> None:
        """
        GIVEN:
            - A 3 page document
        WHEN:
            - A page image is requested for a missing document, and for page 3
        THEN:
            - 404 is returned for both
        """
        response = preview_client.get(f"{ENDPOINT}document-page-image/99999/0/")
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert (
            preview_client.get(preview_url(preview_document, 3)).status_code
            == status.HTTP_404_NOT_FOUND
        )

    def test_serves_image_documents_without_running_poppler(
        self,
        preview_client: APIClient,
        preview_user: User,
        mock_render: MagicMock,
    ) -> None:
        """
        GIVEN:
            - An image document
        WHEN:
            - Its page image is requested
        THEN:
            - The original file is served and no page is rendered
        """
        document = DocumentFactory(owner=preview_user, mime_type="image/png")
        document.source_path.write_bytes(b"image contents")

        response = preview_client.get(preview_url(document))

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert response.content == b"image contents"
        mock_render.assert_not_called()

    def test_renders_pdf_archive_for_an_image_upload(
        self,
        preview_client: APIClient,
        preview_user: User,
    ) -> None:
        """
        GIVEN:
            - An image upload with a PDF archive version
        WHEN:
            - Its page image is requested
        THEN:
            - A rendered PNG, different from the source file, is returned
        """
        document = DocumentFactory(
            owner=preview_user,
            mime_type="image/png",
            archive_filename="archived-image.pdf",
            page_count=1,
        )
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
            image.save(document.archive_path, format="PDF")

        response = preview_client.get(preview_url(document))

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert response.content != document.source_path.read_bytes()
        with Image.open(BytesIO(response.content)) as rendered:
            assert rendered.format == "PNG"
            rendered.verify()

    def test_renders_the_requested_pdf_page(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_render: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A 3 page PDF document
        WHEN:
            - The second page image is requested
        THEN:
            - The renderer is invoked for page 2 at 150 DPI with a 30 second timeout
            - The rendered page is served and the temporary directory removed
        """

        def render_page(in_path: Path, out_path: Path, **kwargs: Any) -> None:
            out_path.write_bytes(b"rendered page")

        mock_render.side_effect = render_page

        response = preview_client.get(preview_url(preview_document, 1))

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert response.content == b"rendered page"
        mock_render.assert_called_once()
        in_path, out_path = mock_render.call_args.args
        assert in_path == preview_document.source_path
        assert mock_render.call_args.kwargs == {"dpi": 150, "page": 2, "timeout": 30}
        assert not out_path.parent.exists()

    def test_render_failure_is_controlled_and_does_not_expose_paths(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_render: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A PDF document whose page render fails
        WHEN:
            - Its page image is requested
        THEN:
            - 404 is returned without leaking the renderer's error message
        """
        mock_render.side_effect = ParseError(
            "pdftoppm failed at /sensitive/server/path",
        )

        response = preview_client.get(preview_url(preview_document))

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "sensitive" not in str(response.content)

    @pytest.mark.usefixtures("mock_render")
    def test_missing_render_output_returns_not_found(
        self,
        preview_client: APIClient,
        preview_document: Document,
    ) -> None:
        """
        GIVEN:
            - A PDF document whose page render writes no output
        WHEN:
            - Its page image is requested
        THEN:
            - 404 is returned
        """

        assert (
            preview_client.get(preview_url(preview_document)).status_code
            == status.HTTP_404_NOT_FOUND
        )


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestZonePreview:
    """Zone preview extraction through the test-zone endpoint."""

    def test_uses_validated_settings_and_does_not_write(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_preview: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A 3 page document
        WHEN:
            - A zone preview is requested with string numbers and full settings
        THEN:
            - Extraction receives the validated, coerced zone and dimensions
            - The result includes the regex match
            - No zone is saved
        """
        mock_preview.return_value = {"raw_text": " 123 ", "value": "123"}

        response = preview_zone(
            preview_client,
            preview_document,
            x="10",
            y="20",
            page=-1,
            transform="numeric",
            ocr_language="deu+eng",
            validation_regex=r"\d+",
            zone_source_width="1000",
            zone_source_height=1500,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "raw_text": " 123 ",
            "value": "123",
            "regex": r"\d+",
            "regex_match": True,
        }
        path, zone, width, height, page_count = mock_preview.call_args.args
        assert path == preview_document.source_path
        assert (zone.x, zone.y, zone.width, zone.height, zone.page) == (
            10,
            20,
            100,
            50,
            -1,
        )
        assert zone.name == "test"
        assert zone.ocr_language == "deu+eng"
        assert zone.transform == "numeric"
        assert (width, height, page_count) == (1000, 1500, 3)
        assert OcrTemplateZone.objects.count() == 0

    @pytest.mark.parametrize(
        ("regex", "value", "expected"),
        [
            pytest.param("", "123", None, id="no-regex"),
            pytest.param(r"\d+", "abc", False, id="no-match"),
            pytest.param(r"\d+", None, None, id="no-value"),
        ],
    )
    def test_reports_regex_failures_and_empty_results(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_preview: MagicMock,
        regex: str,
        value: str | None,
        expected: bool | None,  # noqa: FBT001
    ) -> None:
        """
        GIVEN:
            - A zone preview with an empty, non-matching, valueless or
              invalid validation regex
        WHEN:
            - The preview is requested
        THEN:
            - regex_match reflects the outcome
            - Source dimensions default to 0
        """
        mock_preview.return_value = {"raw_text": value, "value": value}

        response = preview_zone(
            preview_client,
            preview_document,
            validation_regex=regex,
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["regex_match"] == expected
        assert mock_preview.call_args.args[2:4] == (0, 0)

    @pytest.mark.parametrize(
        "zone",
        [
            pytest.param({"width": 1}, id="width-below-minimum"),
            pytest.param({"height": 0}, id="zero-height"),
            pytest.param({"x": -1}, id="negative-x"),
            pytest.param({"y": -1}, id="negative-y"),
            pytest.param({"width": "invalid"}, id="non-numeric-width"),
            pytest.param({"page": "invalid"}, id="non-numeric-page"),
            pytest.param({"page": 0}, id="page-zero"),
            pytest.param({"page": -2}, id="page-below-last"),
            pytest.param({"transform": "invalid"}, id="unknown-transform"),
            pytest.param({"ocr_language": "x" * 21}, id="language-too-long"),
            pytest.param(
                {"zone_source_width": "invalid"},
                id="non-numeric-source-width",
            ),
            pytest.param({"zone_source_height": 0}, id="zero-source-height"),
        ],
    )
    def test_rejects_invalid_settings_before_extraction(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_preview: MagicMock,
        zone: dict[str, Any],
    ) -> None:
        """
        GIVEN:
            - A zone preview request with one invalid zone setting
        WHEN:
            - The preview is requested
        THEN:
            - 400 is returned and extraction does not run
        """

        assert (
            preview_zone(preview_client, preview_document, **zone).status_code
            == status.HTTP_400_BAD_REQUEST
        )
        mock_preview.assert_not_called()

    @pytest.mark.parametrize(
        "make_data",
        [
            pytest.param(lambda doc: {}, id="empty"),
            pytest.param(
                lambda doc: {"document": "invalid", "zone": {}},
                id="non-numeric-document",
            ),
            pytest.param(
                lambda doc: {"document": 99999, "zone": {}},
                id="unknown-document",
            ),
            pytest.param(
                lambda doc: {"document": doc.pk, "zone": None},
                id="null-zone",
            ),
            pytest.param(
                lambda doc: {"document": doc.pk, "zone": []},
                id="list-zone",
            ),
        ],
    )
    def test_rejects_malformed_requests(
        self,
        preview_client: APIClient,
        preview_document: Document,
        mock_preview: MagicMock,
        make_data: Callable[[Document], dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A malformed zone preview payload
        WHEN:
            - The preview is requested
        THEN:
            - 400 is returned and extraction does not run
        """

        response = preview_client.post(
            PREVIEW_ZONE_URL,
            make_data(preview_document),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        mock_preview.assert_not_called()


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplatePreviewPermissions:
    """Permission checks for the page image and zone preview endpoints."""

    @pytest.mark.parametrize(
        "action",
        [
            pytest.param("document-page-image", id="document-page-image"),
            pytest.param("test-zone", id="test-zone"),
        ],
    )
    def test_previews_require_global_document_view_permission(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_preview: MagicMock,
        action: str,
    ) -> None:
        """
        GIVEN:
            - A user with template permissions but no global view document
              permission
            - An unowned image document
        WHEN:
            - The user requests a page image or a zone preview
        THEN:
            - 403 is returned and no extraction runs
        """
        grant_global(regular_user, "view_ocrtemplate", "add_ocrtemplate")
        document = DocumentFactory(owner=None, mime_type="image/png")
        document.source_path.write_bytes(b"document contents")

        if action == "document-page-image":
            response = user_client.get(preview_url(document))
        else:
            response = preview_zone(user_client, document)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        mock_preview.assert_not_called()

    @pytest.mark.parametrize(
        "action",
        [
            pytest.param("document-page-image", id="document-page-image"),
            pytest.param("test-zone", id="test-zone"),
        ],
    )
    @pytest.mark.parametrize(
        ("template_perms", "expected"),
        [
            pytest.param(
                ("view_ocrtemplate",),
                status.HTTP_200_OK,
                id="view-template-is-enough",
            ),
            pytest.param(
                ("add_ocrtemplate", "change_ocrtemplate"),
                status.HTTP_403_FORBIDDEN,
                id="no-view-template",
            ),
        ],
    )
    def test_previews_require_global_template_view_permission(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_preview: MagicMock,
        action: str,
        template_perms: tuple[str, ...],
        expected: int,
    ) -> None:
        """
        GIVEN:
            - A user with global view document permission and either only view
              template permission, or add and change but not view
            - An unowned image document
        WHEN:
            - The user requests a page image or a zone preview
        THEN:
            - Viewing templates is enough for both, and without it both are
              refused
        """
        grant_global(regular_user, "view_document", *template_perms)
        document = DocumentFactory(owner=None, mime_type="image/png")
        document.source_path.write_bytes(b"document contents")
        mock_preview.return_value = {"raw_text": None, "value": None}

        if action == "document-page-image":
            response = user_client.get(preview_url(document))
        else:
            response = preview_zone(user_client, document)

        assert response.status_code == expected

    def test_versions_are_authorized_through_the_root_document(
        self,
        preview_client: APIClient,
        preview_user: User,
        mock_preview: MagicMock,
        mock_render: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A version owned by the user whose root document belongs to
              another user
        WHEN:
            - The user requests a page image and a zone preview of the version
        THEN:
            - The page image is refused with 403 and the zone preview with 400
              until the user is granted view on the root
            - Afterwards both succeed
        """
        other = UserFactory()
        root = DocumentFactory(owner=other)
        version = DocumentFactory(
            root_document=root,
            owner=preview_user,
            mime_type="image/png",
        )
        version.source_path.write_bytes(b"private version")
        assert (
            preview_client.get(preview_url(version)).status_code
            == status.HTTP_403_FORBIDDEN
        )
        assert (
            preview_zone(preview_client, version).status_code
            == status.HTTP_400_BAD_REQUEST
        )
        mock_render.assert_not_called()
        mock_preview.assert_not_called()

        grant_object(preview_user, root, "view_document")
        mock_preview.return_value = {"raw_text": None, "value": None}
        assert (
            preview_client.get(preview_url(version)).status_code == status.HTTP_200_OK
        )
        assert preview_zone(preview_client, version).status_code == status.HTTP_200_OK

    def test_document_page_image_requires_view_permission_on_the_document(
        self,
        regular_user: User,
        user_client: APIClient,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user
            - A user with global view permissions only
        WHEN:
            - The user requests a page image of the document
        THEN:
            - The request is refused until the user is granted view on the document
            - Afterwards it passes the permission check and reaches the missing file
        """
        owner = UserFactory()
        grant_global(regular_user, "view_ocrtemplate", "view_document")
        document = DocumentFactory(owner=owner)
        url = preview_url(document)

        response = user_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        grant_object(regular_user, document, "view_document")
        response = user_client.get(url)
        # Past the permission check; the factory document has no file on disk.
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_zone_preview_requires_view_permission_on_the_document(
        self,
        regular_user: User,
        user_client: APIClient,
        mock_preview: MagicMock,
    ) -> None:
        """
        GIVEN:
            - A document owned by another user
            - A user with global view template and view document permissions
        WHEN:
            - The user previews a zone on the document
        THEN:
            - The request is rejected with 400 until the user is granted view
              on the document
            - Afterwards it passes validation and reaches the missing file
            - No preview extraction runs
        """
        owner = UserFactory()
        grant_global(regular_user, "view_ocrtemplate", "view_document")
        document = DocumentFactory(owner=owner)
        response = preview_zone(user_client, document, x=0, y=0, height=100, page=1)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "document" in response.json()

        grant_object(regular_user, document, "view_document")
        response = preview_zone(user_client, document, x=0, y=0, height=100, page=1)
        # Past validation; the factory document has no file on disk.
        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_preview.assert_not_called()
