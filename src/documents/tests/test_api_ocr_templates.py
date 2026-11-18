"""Tests for the OCR Template API."""

from __future__ import annotations

import functools
import subprocess
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import MatchingModel
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from documents.search import get_backend
from documents.signals import document_consumption_finished
from documents.tasks import extract_zones
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.factories import OcrTemplateFactory
from paperless_testing.factories import OcrTemplateZoneFactory
from paperless_testing.factories import UserFactory
from paperless_testing.permissions import grant_global
from paperless_testing.permissions import grant_object

if TYPE_CHECKING:
    from collections.abc import Callable

    from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
    from pytest_mock import MockerFixture
    from rest_framework.test import APIClient

CONTENT = "Northwind Power & Light statement"

ENDPOINT = "/api/ocr_templates/"


def make_template_data(**overrides: Any) -> dict[str, Any]:
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


def make_zone_data(custom_field_id: int | None, **overrides: Any) -> dict[str, Any]:
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
    return CustomField.objects.create(
        name="Invoice Number",
        data_type=CustomField.FieldDataType.STRING,
    )


@pytest.fixture
def date_field(db: None) -> CustomField:
    return CustomField.objects.create(
        name="Invoice Date",
        data_type=CustomField.FieldDataType.DATE,
    )


@pytest.fixture
def doclink_field(db: None) -> CustomField:
    return CustomField.objects.create(
        name="Related Docs",
        data_type=CustomField.FieldDataType.DOCUMENTLINK,
    )


@pytest.fixture
def make_zone(text_field: CustomField) -> Callable[..., dict[str, Any]]:
    """Zone payload builder whose custom field defaults to the text field."""
    return functools.partial(make_zone_data, text_field.pk)


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestZoneOcrIndexing:
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
        mocker: MockerFixture,
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
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(file_document.source_path, format="PNG")
        template = OcrTemplateFactory(
            name="Invoice template",
            match="Northwind",
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=100,
            source_height=100,
        )
        field = CustomField.objects.create(name="Invoice code", data_type="string")
        OcrTemplateZoneFactory(
            template=template,
            name="Title",
            target=OcrTemplateZone.TargetType.TITLE,
            page=-1,
            x=0,
            y=0,
            width=50,
            height=50,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Invoice code",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=field,
            page=-1,
            x=0,
            y=50,
            width=50,
            height=50,
            order=1,
        )
        mocker.patch(
            "documents.zone_ocr.subprocess.run",
            side_effect=[mocker.Mock(stdout="After OCR"), mocker.Mock(stdout="INV42")],
        )

        backend = get_backend()
        if entry_point != "ingestion":
            backend.add_or_update(document)
            assert backend.search_ids("title:before", user=None) == [document.pk]

        with django_capture_on_commit_callbacks(execute=True):
            if entry_point == "ingestion":
                document_consumption_finished.send(sender=None, document=file_document)
            elif entry_point == "single":
                response = admin_client.post(
                    f"/api/documents/{document.pk}/run-zone-ocr/",
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
    def test_create_template(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A document type and custom fields exist
        WHEN:
            - API request to create an OCR template with one zone
        THEN:
            - The template and zone are created
        """
        data = make_template_data(
            zones=[
                make_zone(
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

    def test_create_template_sets_owner(
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
        response = admin_client.post(ENDPOINT, make_template_data(), format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert OcrTemplate.objects.get().owner == admin_user

    def test_create_template_multiple_zones(
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
        data = make_template_data(
            zones=[
                make_zone_data(text_field.pk, name="Invoice Number"),
                make_zone_data(date_field.pk, name="Invoice Date", order=1),
            ],
        )
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["zones"]) == 2
        assert OcrTemplateZone.objects.count() == 2

    def test_create_template_no_zones(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - Valid template data without zones
        WHEN:
            - Template is created
        THEN:
            - Template is created with no zones
        """
        resp = admin_client.post(ENDPOINT, make_template_data(), format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert len(resp.json()["zones"]) == 0

    def test_custom_and_builtin_zones_can_have_no_custom_field(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
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
        data = make_template_data(
            zones=[
                make_zone(custom_field=None),
                make_zone(name="Title", target="title", custom_field=None),
            ],
        )
        response = admin_client.post(ENDPOINT, data, format="json")
        assert response.status_code == 201
        assert [z["custom_field"] for z in response.json()["zones"]] == [None, None]
        zone = OcrTemplateZone.objects.get(name="Title")
        assert str(zone) == f"{zone.template.name} -> Title"

    def test_template_creation_rolls_back_when_a_zone_cannot_be_saved(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
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
        data = make_template_data(zones=[make_zone(), make_zone(name="Broken")])
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
    def test_list_only_shows_permitted_templates(
        self,
        rest_api_client: APIClient,
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
        user = UserFactory()
        grant_global(user, "view_ocrtemplate")

        def template(name: str, owner: User | None = None) -> OcrTemplate:
            return OcrTemplateFactory(
                name=name,
                match="Northwind",
                matching_algorithm=MatchingModel.MATCH_ANY,
                source_width=1000,
                source_height=1000,
                owner=owner,
            )

        template("Unowned")
        template("Mine", owner=user)
        template("Private", owner=other)
        grant_object(user, template("Shared", owner=other), "view_ocrtemplate")
        rest_api_client.force_authenticate(user=user)

        response = rest_api_client.get(ENDPOINT)

        assert response.status_code == status.HTTP_200_OK
        assert sorted(t["name"] for t in response.json()["results"]) == [
            "Mine",
            "Shared",
            "Unowned",
        ]

    def test_cannot_change_another_users_template(
        self,
        rest_api_client: APIClient,
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
        user = UserFactory()
        grant_global(user, "view_ocrtemplate", "change_ocrtemplate")
        template = OcrTemplateFactory(
            name="Private",
            match="Northwind",
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=1000,
            source_height=1000,
            owner=other,
        )
        grant_object(user, template, "view_ocrtemplate")
        rest_api_client.force_authenticate(user=user)
        url = f"{ENDPOINT}{template.pk}/"

        response = rest_api_client.patch(url, {"name": "Renamed"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

        grant_object(user, template, "change_ocrtemplate")
        response = rest_api_client.patch(url, {"name": "Renamed"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        template.refresh_from_db()
        assert template.name == "Renamed"
        assert template.owner == other


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateValidation:
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
    def test_create_template_rejects_invalid_dimensions(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
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
        zones = [] if zone_overrides is None else [make_zone(**zone_overrides)]
        data = make_template_data(zones=zones, **template_overrides)
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_create_template_rejects_automatic_matching(
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
            make_template_data(matching_algorithm=MatchingModel.MATCH_AUTO),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert OcrTemplate.objects.count() == 0

    def test_create_zone_unsupported_custom_field_type_rejected(
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
        data = make_template_data(zones=[make_zone_data(doclink_field.pk)])
        resp = admin_client.post(ENDPOINT, data, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_zone_bounds_use_the_zones_own_source_dimensions(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
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
        data = make_template_data(
            source_width=500,
            source_height=500,
            zones=[
                make_zone(
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
        assert response.status_code == 201
        data["name"] = "Invalid bounds"
        data["zones"][0]["zone_source_width"] = 800
        response = admin_client.post(ENDPOINT, data, format="json")
        assert response.status_code == 400

    def test_changing_source_dimensions_checks_existing_zones(
        self,
        admin_client: APIClient,
        make_zone: Callable[..., dict[str, Any]],
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
            make_template_data(zones=[make_zone()]),
            format="json",
        )
        url = f"{ENDPOINT}{response.json()['id']}/"
        response = admin_client.patch(url, {"source_width": 200}, format="json")
        assert response.status_code == 400
        response = admin_client.patch(url, {"source_width": 1000}, format="json")
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "changes",
        [
            pytest.param({"x": 900, "width": 200}, id="exceeds-width"),
            pytest.param({"y": 990, "height": 50}, id="exceeds-height"),
        ],
    )
    def test_partial_zone_replacement_uses_saved_dimensions(
        self,
        admin_client: APIClient,
        admin_user: User,
        make_zone: Callable[..., dict[str, Any]],
        changes: dict[str, int],
    ) -> None:
        """
        GIVEN:
            - A saved 1000x1000 template
        WHEN:
            - A PATCH replaces zones with one extending beyond the saved
              source dimensions
        THEN:
            - The request is rejected
        """
        template = OcrTemplateFactory(
            name="Test",
            matching_algorithm=MatchingModel.MATCH_ANY,
            owner=admin_user,
            source_width=1000,
            source_height=1000,
        )
        response = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
            {"zones": [make_zone(**changes)]},
            format="json",
        )
        assert response.status_code == 400

    def test_partial_zone_replacement_within_saved_dimensions_accepted(
        self,
        admin_client: APIClient,
        admin_user: User,
        make_zone: Callable[..., dict[str, Any]],
    ) -> None:
        """
        GIVEN:
            - A saved 1000x1000 template
        WHEN:
            - A PATCH replaces zones with one inside the saved dimensions
        THEN:
            - The request succeeds
        """
        template = OcrTemplateFactory(
            name="Test",
            matching_algorithm=MatchingModel.MATCH_ANY,
            owner=admin_user,
            source_width=1000,
            source_height=1000,
        )
        response = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
            {"zones": [make_zone()]},
            format="json",
        )
        assert response.status_code == 200

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
            matching_algorithm=MatchingModel.MATCH_ANY,
            owner=admin_user,
            source_width=1000,
            source_height=1000,
        )
        zone = OcrTemplateZoneFactory(
            template=template,
            name="Original",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            x=0,
            y=0,
            width=10,
            height=10,
        )
        response = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
            {"zones": [{"name": "Incomplete"}]},
            format="json",
        )
        assert response.status_code == 400
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
        make_zone: Callable[..., dict[str, Any]],
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
            make_template_data(zones=[make_zone(page=page)]),
            format="json",
        )
        assert response.status_code == 400

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
        formats: Any,
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
            make_template_data(combine_formats=formats),
            format="json",
        )
        assert response.status_code == 400

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
            make_template_data(combine_formats={"title": " {A} - {B} "}),
            format="json",
        )
        assert response.status_code == 201
        assert response.json()["combine_formats"] == {"title": " {A} - {B} "}


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateList:
    def test_list_templates(
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone 1",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            x=100,
            y=100,
            width=200,
            height=50,
        )

        resp = admin_client.get(ENDPOINT)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["count"] == 1
        assert len(data["results"][0]["zones"]) == 1

    def test_list_empty(self, admin_client: APIClient) -> None:
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Old Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        data = make_template_data(
            name="New Name",
            zones=[make_zone_data(date_field.pk, name="New Zone")],
        )
        resp = admin_client.put(f"{ENDPOINT}{template.pk}/", data, format="json")
        assert resp.status_code == status.HTTP_200_OK

        template.refresh_from_db()
        assert template.name == "New Name"
        assert OcrTemplateZone.objects.count() == 1
        assert OcrTemplateZone.objects.first().name == "New Zone"

    def test_template_update_rolls_back_without_losing_previous_zones(
        self,
        admin_client: APIClient,
        admin_user: User,
        make_zone: Callable[..., dict[str, Any]],
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            owner=admin_user,
            source_width=1000,
            source_height=1000,
        )
        zone = OcrTemplateZoneFactory(
            template=template,
            name="Original zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            x=0,
            y=0,
            width=10,
            height=10,
        )
        data = make_template_data(name="Changed", zones=[make_zone()])
        mocker.patch(
            "documents.serialisers.OcrTemplateZone.objects.create",
            side_effect=IntegrityError("Zone save failed"),
        )
        with pytest.raises(IntegrityError):
            admin_client.put(f"{ENDPOINT}{template.pk}/", data, format="json")
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            owner=admin_user,
            source_width=1000,
            source_height=1000,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            x=0,
            y=0,
            width=10,
            height=10,
        )
        response = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
            {"zones": []},
            format="json",
        )
        assert response.status_code == 200
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=2480,
            source_height=3508,
            enabled=True,
        )

        resp = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Existing Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = admin_client.patch(
            f"{ENDPOINT}{template.pk}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert OcrTemplateZone.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestOcrTemplateDelete:
    def test_delete_template_cascades_zones(
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
            matching_algorithm=MatchingModel.MATCH_ANY,
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZoneFactory(
            template=template,
            name="Zone",
            target=OcrTemplateZone.TargetType.CUSTOM_FIELD,
            custom_field=text_field,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = admin_client.delete(f"{ENDPOINT}{template.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert OcrTemplate.objects.count() == 0
        assert OcrTemplateZone.objects.count() == 0

    def test_delete_nonexistent_returns_404(self, admin_client: APIClient) -> None:
        """
        GIVEN:
            - No template with the requested id
        WHEN:
            - A delete request is made for it
        THEN:
            - 404 is returned
        """
        resp = admin_client.delete(f"{ENDPOINT}99999/")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


class TestOcrTemplatesAPI(DirectoriesMixin, APITestCase):
    ENDPOINT = "/api/ocr_templates/"

    def setUp(self) -> None:
        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_authenticate(user=self.user)

        self.custom_field_text = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.custom_field_date = CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )

        return super().setUp()

    # --- Auth ---

    def test_unauthenticated_rejected(self):
        self.client.logout()
        resp = self.client.get(self.ENDPOINT)
        self.assertIn(
            resp.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_without_matching_template_is_skipped(self, extract):
        document = DocumentFactory(content=CONTENT)
        OcrTemplate.objects.create(
            name="Other sender",
            match="Contoso",
            source_width=1000,
            source_height=1000,
        )

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {"status": "skipped", "reason": "no_template", "results": []},
        )
        extract.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_without_enabled_template_is_skipped(self, extract):
        document = DocumentFactory(content=CONTENT)

        for enabled in (None, False):
            with self.subTest(enabled=enabled):
                if enabled is False:
                    OcrTemplate.objects.create(
                        name="Disabled template",
                        match="Northwind",
                        source_width=1000,
                        source_height=1000,
                        enabled=False,
                    )

                response = self.client.post(
                    f"/api/documents/{document.pk}/run-zone-ocr/",
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(
                    response.json(),
                    {"status": "skipped", "reason": "no_template", "results": []},
                )
        extract.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_applies_a_chosen_template(self, extract):
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
        template = OcrTemplate.objects.create(
            name="Manual only",
            match="Contoso",
            enabled=False,
            source_width=1000,
            source_height=1000,
        )

        response = self.client.post(
            f"/api/documents/{document.pk}/run-zone-ocr/",
            {"template": template.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["status"], "completed")
        extract.assert_called_once_with(document, templates=[template], reindex=True)

    @patch("documents.zone_ocr.run_zone_extraction", return_value=[])
    def test_run_zone_ocr_matches_the_requested_file_version(self, extract):
        document = DocumentFactory(content=CONTENT)
        older = DocumentFactory(
            root_document=document,
            version_index=1,
            content=CONTENT,
        )
        DocumentFactory(root_document=document, version_index=2, content="Contoso")
        template = OcrTemplate.objects.create(
            name="Northwind",
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        url = f"/api/documents/{document.pk}/run-zone-ocr/"

        for file_document in (document, older):
            with self.subTest(version=file_document.pk):
                file_document.source_path.write_bytes(b"test PDF")
                response = self.client.post(f"{url}?version={file_document.pk}")
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.json()["status"], "completed")
                extract.assert_called_once_with(
                    file_document,
                    templates=[template],
                    reindex=True,
                )
                extract.reset_mock()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_rejects_invalid_or_unavailable_versions(self, extract):
        document = DocumentFactory()
        unrelated = DocumentFactory()
        deleted = DocumentFactory(
            root_document=document,
            version_index=1,
            deleted_at=timezone.now(),
        )

        for version in ("invalid", unrelated.pk, deleted.pk):
            with self.subTest(version=version):
                response = self.client.post(
                    f"/api/documents/{document.pk}/run-zone-ocr/?version={version}",
                )
                self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        extract.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_rejects_a_template_the_user_cannot_view(self, extract):
        user = User.objects.create_user(username="editor")
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_document", "change_document"],
            ),
        )
        document = DocumentFactory(content=CONTENT, owner=user)
        template = OcrTemplate.objects.create(
            name="Private",
            owner=User.objects.create_user(username="other"),
            source_width=1000,
            source_height=1000,
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            f"/api/documents/{document.pk}/run-zone-ocr/",
            {"template": template.pk},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        extract.assert_not_called()

    def test_run_zone_ocr_rejects_an_unknown_template(self):
        document = DocumentFactory(content=CONTENT)

        response = self.client.post(
            f"/api/documents/{document.pk}/run-zone-ocr/",
            {"template": 999},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_document_page_image_requires_view_permission_on_the_document(self):
        owner = User.objects.create_user(username="owner")
        user = User.objects.create_user(username="template_editor")
        grant_global(user, "view_ocrtemplate", "view_document")
        document = DocumentFactory(owner=owner)
        self.client.force_authenticate(user=user)
        url = f"{self.ENDPOINT}document-page-image/{document.pk}/0/"

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        grant_object(user, document, "view_document")
        response = self.client.get(url)
        # Past the permission check; the factory document has no file on disk.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_test_zone_requires_view_permission_on_the_document(self, preview):
        owner = User.objects.create_user(username="owner")
        user = User.objects.create_user(username="template_editor")
        grant_global(user, "add_ocrtemplate", "view_document")
        document = DocumentFactory(owner=owner)
        self.client.force_authenticate(user=user)
        data = {
            "document": document.pk,
            "zone": {"x": 0, "y": 0, "width": 100, "height": 100, "page": 1},
        }

        response = self.client.post(f"{self.ENDPOINT}test-zone/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        grant_object(user, document, "view_document")
        response = self.client.post(f"{self.ENDPOINT}test-zone/", data, format="json")
        # Past the permission check; the factory document has no file on disk.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        preview.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_requires_change_permission_on_the_document(
        self,
        extract,
    ):
        owner = User.objects.create_user(username="owner")
        user = User.objects.create_user(username="editor")
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_document", "change_document"],
            ),
        )
        document = DocumentFactory(content=CONTENT, owner=owner)
        self.client.force_authenticate(user=user)

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        extract.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_requires_global_change_permission(self, extract):
        user = User.objects.create_user(username="uploader")
        user.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_document", "add_document"]),
        )
        document = DocumentFactory(content=CONTENT, owner=user)
        self.client.force_authenticate(user=user)

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        extract.assert_not_called()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_does_not_require_document_upload_permission(self, extract):
        user = User.objects.create_user(username="document_editor")
        user.user_permissions.add(Permission.objects.get(codename="change_document"))
        document = DocumentFactory(owner=user, content=CONTENT)
        document.source_path.write_bytes(b"test PDF")
        OcrTemplate.objects.create(
            name="Matching",
            owner=user,
            source_width=100,
            source_height=100,
            match="Northwind",
            matching_algorithm=MatchingModel.MATCH_ANY,
        )
        self.client.force_authenticate(user)

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, 200)
        extract.assert_called_once()

    def test_run_zone_ocr_missing_document_is_an_error(self):
        response = self.client.post("/api/documents/99999/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_skips_templates_private_to_the_requester(self, extract):
        owner = User.objects.create_user(username="document_owner")
        document = DocumentFactory(content=CONTENT, owner=owner)
        OcrTemplate.objects.create(
            name="Requester's private template",
            owner=self.user,
            match="Northwind",
            source_width=100,
            source_height=100,
        )

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
                "status": "skipped",
                "reason": "no_template",
                "results": [],
            },
        )
        extract.assert_not_called()

    @patch("documents.zone_ocr.subprocess.run")
    def test_run_zone_ocr_reports_only_templates_visible_to_the_document_owner(
        self,
        run,
    ):
        owner = User.objects.create_user(username="document_owner")
        document = DocumentFactory(content=CONTENT, owner=owner)
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        run.return_value.stdout = "extracted"
        for name, template_owner in [
            ("Owned", owner),
            ("Unowned", None),
            ("Shared", self.user),
            ("Private", self.user),
        ]:
            template = OcrTemplate.objects.create(
                name=name,
                owner=template_owner,
                match="Northwind",
                source_width=100,
                source_height=100,
            )
            OcrTemplateZone.objects.create(
                template=template,
                name=name,
                target="title",
                x=0,
                y=0,
                width=20,
                height=20,
            )
            if name == "Shared":
                grant_object(owner, template, "view_ocrtemplate")

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(
            [result["template"] for result in response.json()["results"]],
            ["Owned", "Unowned", "Shared"],
        )
        self.assertEqual(run.call_count, 3)

    @patch("documents.zone_ocr.subprocess.run")
    def test_run_zone_ocr_hides_the_owners_private_templates_from_an_editor(
        self,
        run,
    ):
        """
        GIVEN:
            - A document shared for editing with another user
            - Templates private to the owner, unowned, and shared with both
        WHEN:
            - The editor runs zone OCR without choosing a template
        THEN:
            - Only templates the editor can also view run and are reported
        """
        owner = User.objects.create_user(username="document_owner")
        editor = User.objects.create_user(username="document_editor")
        editor.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_document", "change_document"],
            ),
        )
        document = DocumentFactory(content=CONTENT, owner=owner)
        grant_object(editor, document, "view_document", "change_document")
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        run.return_value.stdout = "extracted"
        for name, template_owner in [
            ("Owner private", owner),
            ("Unowned", None),
            ("Shared", owner),
        ]:
            template = OcrTemplate.objects.create(
                name=name,
                owner=template_owner,
                match="Northwind",
                source_width=100,
                source_height=100,
            )
            OcrTemplateZone.objects.create(
                template=template,
                name=name,
                target="title",
                x=0,
                y=0,
                width=20,
                height=20,
            )
            if name == "Shared":
                grant_object(editor, template, "view_ocrtemplate")
        self.client.force_authenticate(editor)

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(
            [result["template"] for result in response.json()["results"]],
            ["Unowned", "Shared"],
        )
        self.assertEqual(run.call_count, 2)

    def test_shared_editor_cannot_transfer_ownership_or_change_sharing(self):
        editor = User.objects.create_user(username="shared_editor")
        editor.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_ocrtemplate", "change_ocrtemplate"],
            ),
        )
        template = OcrTemplate.objects.create(
            name="Shared",
            owner=self.user,
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        grant_object(editor, template, "view_ocrtemplate", "change_ocrtemplate")
        self.client.force_authenticate(editor)
        for data in [
            {"owner": editor.pk},
            {"set_permissions": {"view": {"users": []}}},
        ]:
            with self.subTest(data=data):
                response = self.client.patch(
                    f"{self.ENDPOINT}{template.pk}/",
                    data,
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        template.refresh_from_db()
        self.assertEqual(template.owner, self.user)

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_missing_file_is_an_error(self, extract):
        document = DocumentFactory(content=CONTENT)
        OcrTemplate.objects.create(
            name="Template",
            match="Northwind",
            source_width=1000,
            source_height=1000,
        )

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json(), {"error": "Document file not found"})
        extract.assert_not_called()

    @patch("documents.zone_ocr.subprocess.run")
    def test_run_zone_ocr_reports_completed_results(self, run):
        document = DocumentFactory(
            content=CONTENT,
            mime_type="application/pdf",
        )
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        run.return_value.stdout = "Extracted title"
        template = OcrTemplate.objects.create(
            name="Template",
            match="Northwind",
            source_width=1000,
            source_height=1000,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Title zone",
            target="title",
            x=0,
            y=0,
            width=100,
            height=100,
        )

        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json(),
            {
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
            },
        )
        run.assert_called_once()

    @patch("documents.zone_ocr.subprocess.run")
    def test_run_zone_ocr_does_not_report_an_old_title_when_extraction_is_empty(
        self,
        run,
    ):
        document = DocumentFactory(title="Existing title", content=CONTENT)
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        template = OcrTemplate.objects.create(
            name="Template",
            match="Northwind",
            source_width=100,
            source_height=100,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Title",
            target="title",
            x=0,
            y=0,
            width=20,
            height=20,
        )
        run.return_value.stdout = ""
        response = self.client.post(f"/api/documents/{document.pk}/run-zone-ocr/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["reason"], "no_value")
        self.assertIsNone(response.json()["results"][0]["value"])
        document.refresh_from_db()
        self.assertEqual(document.title, "Existing title")

    @patch("documents.zone_ocr.subprocess.run")
    def test_run_zone_ocr_reports_all_target_types_and_missing_values(self, run):
        document = DocumentFactory(content=CONTENT, archive_serial_number=123)
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
        run.side_effect = [
            subprocess.CompletedProcess([], 0, stdout=value)
            for value in [
                "New invoice",
                "",
                "orphan",
                "New title",
                "456",
                "2026-04-13",
            ]
        ]
        template = OcrTemplate.objects.create(
            name="Test",
            source_width=100,
            source_height=100,
        )
        CustomFieldInstance.objects.create(
            document=document,
            field=self.custom_field_text,
            value_text="INV-123",
        )
        for name, target, field in [
            ("Present", "custom_field", self.custom_field_text),
            ("Missing", "custom_field", self.custom_field_date),
            ("Unassigned", "custom_field", None),
            ("Title", "title", None),
            ("ASN", "asn", None),
            ("Created", "created", None),
        ]:
            OcrTemplateZone.objects.create(
                template=template,
                name=name,
                target=target,
                custom_field=field,
                x=0,
                y=0,
                width=10,
                height=10,
            )
        response = self.client.post(
            f"/api/documents/{document.pk}/run-zone-ocr/",
            {"template": template.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        values = {
            result["zone"]: result["value"] for result in response.json()["results"]
        }
        self.assertEqual(
            values,
            {
                "Present": "New invoice",
                "Missing": None,
                "Unassigned": None,
                "Title": "New title",
                "ASN": 456,
                "Created": "2026-04-13",
            },
        )


class TestOcrTemplatePreviewAPI(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="template_editor")
        grant_global(self.user, "view_ocrtemplate", "add_ocrtemplate", "view_document")
        self.client.force_authenticate(self.user)
        self.document = DocumentFactory(
            owner=self.user,
            page_count=3,
            mime_type="application/pdf",
        )
        self.document.source_path.write_bytes(b"test document")

    def preview_url(self, document=None, page=0):
        document = document or self.document
        return f"/api/ocr_templates/document-page-image/{document.pk}/{page}/"

    def preview_zone(self, **zone):
        return self.client.post(
            "/api/ocr_templates/test-zone/",
            {
                "document": self.document.pk,
                "zone": {"width": 100, "height": 50, **zone},
            },
            format="json",
        )

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_previews_require_global_document_view_permission(self, extract):
        user = User.objects.create_user(username="template_only")
        grant_global(user, "view_ocrtemplate", "add_ocrtemplate")
        self.client.force_authenticate(user)
        document = DocumentFactory(owner=None, mime_type="image/png")
        document.source_path.write_bytes(b"document contents")
        extract.return_value = {"raw_text": "document contents", "value": None}

        with self.subTest(action="document-page-image"):
            response = self.client.get(self.preview_url(document))
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        with self.subTest(action="test-zone"):
            response = self.client.post(
                "/api/ocr_templates/test-zone/",
                {"document": document.pk, "zone": {"width": 100, "height": 50}},
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        extract.assert_not_called()

    def test_missing_document_and_out_of_range_pages(self):
        response = self.client.get("/api/ocr_templates/document-page-image/99999/0/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(self.preview_url(page=3)).status_code, 404)

    @patch("documents.views.subprocess.run")
    def test_serves_image_documents_without_running_poppler(self, render):
        document = DocumentFactory(owner=self.user, mime_type="image/png")
        document.source_path.write_bytes(b"image contents")
        response = self.client.get(self.preview_url(document))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, b"image contents")
        render.assert_not_called()

    def test_renders_pdf_archive_for_an_image_upload(self):
        document = DocumentFactory(
            owner=self.user,
            mime_type="image/png",
            archive_filename="archived-image.pdf",
            page_count=1,
        )
        with Image.new("RGB", (100, 100), "white") as image:
            image.save(document.source_path, format="PNG")
            image.save(document.archive_path, format="PDF")

        response = self.client.get(self.preview_url(document))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertNotEqual(response.content, document.source_path.read_bytes())
        with Image.open(BytesIO(response.content)) as rendered:
            self.assertEqual(rendered.format, "PNG")
            rendered.verify()

    @patch("documents.views.subprocess.run")
    def test_renders_the_requested_pdf_page(self, render):
        def render_page(command, **kwargs):
            Path(command[-1] + "-2.png").write_bytes(b"rendered page")

        render.side_effect = render_page
        response = self.client.get(self.preview_url(page=1))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content, b"rendered page")
        command = render.call_args.args[0]
        self.assertEqual(
            command[:9],
            [
                "pdftoppm",
                "-png",
                "-r",
                "150",
                "-f",
                "2",
                "-l",
                "2",
                str(self.document.source_path),
            ],
        )
        self.assertEqual(
            render.call_args.kwargs,
            {"check": True, "capture_output": True, "timeout": 30},
        )
        self.assertFalse(Path(command[-1]).parent.exists())

    @patch("documents.views.subprocess.run")
    def test_render_failures_are_controlled_and_do_not_expose_paths(self, render):
        for error in [
            subprocess.CalledProcessError(
                1,
                ["pdftoppm"],
                stderr=b"sensitive server path",
            ),
            subprocess.TimeoutExpired(["pdftoppm"], 30),
            FileNotFoundError("pdftoppm"),
        ]:
            with self.subTest(error=error):
                render.side_effect = error
                response = self.client.get(self.preview_url())
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("sensitive server path", str(response.content))

    @patch("documents.views.subprocess.run")
    def test_missing_render_output_returns_not_found(self, render):
        self.assertEqual(self.client.get(self.preview_url()).status_code, 404)

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_zone_preview_uses_validated_settings_and_does_not_write(self, extract):
        extract.return_value = {"raw_text": " 123 ", "value": "123"}
        response = self.preview_zone(
            x="10",
            y="20",
            page=-1,
            transform="numeric",
            ocr_language="deu+eng",
            validation_regex=r"\d+",
            zone_source_width="1000",
            zone_source_height=1500,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"raw_text": " 123 ", "value": "123", "regex": r"\d+", "regex_match": True},
        )
        path, zone, width, height, page_count = extract.call_args.args
        self.assertEqual(path, self.document.source_path)
        self.assertEqual(
            (zone.x, zone.y, zone.width, zone.height, zone.page),
            (10, 20, 100, 50, -1),
        )
        self.assertEqual(zone.name, "test")
        self.assertEqual(zone.ocr_language, "deu+eng")
        self.assertEqual(zone.transform, "numeric")
        self.assertEqual((width, height, page_count), (1000, 1500, 3))
        self.assertEqual(OcrTemplateZone.objects.count(), 0)

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_zone_preview_reports_regex_failures_and_empty_results(self, extract):
        for regex, value, expected in [
            ("", "123", None),
            (r"\d+", "abc", False),
            (r"\d+", None, None),
            ("[invalid", "123", False),
        ]:
            with self.subTest(regex=regex, value=value):
                extract.return_value = {"raw_text": value, "value": value}
                response = self.preview_zone(validation_regex=regex)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["regex_match"], expected)
        self.assertEqual(extract.call_args.args[2:4], (0, 0))

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_zone_preview_rejects_invalid_settings_before_extraction(self, extract):
        for zone in [
            {"width": 1},
            {"height": 0},
            {"x": -1},
            {"y": -1},
            {"width": "invalid"},
            {"page": "invalid"},
            {"page": 0},
            {"page": -2},
            {"transform": "invalid"},
            {"ocr_language": "x" * 21},
            {"zone_source_width": "invalid"},
            {"zone_source_height": 0},
        ]:
            with self.subTest(zone=zone):
                self.assertEqual(self.preview_zone(**zone).status_code, 400)
        extract.assert_not_called()

    @patch("documents.zone_ocr.extract_zone_preview")
    def test_zone_preview_rejects_malformed_requests(self, extract):
        for data in [
            {},
            {"document": "invalid", "zone": {}},
            {"document": 99999, "zone": {}},
            {"document": self.document.pk, "zone": None},
            {"document": self.document.pk, "zone": []},
        ]:
            with self.subTest(data=data):
                response = self.client.post(
                    "/api/ocr_templates/test-zone/",
                    data,
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
        extract.assert_not_called()

    @patch("documents.zone_ocr.extract_zone_preview")
    @patch("documents.views.subprocess.run")
    def test_versions_are_authorized_through_the_root_document(self, render, extract):
        other = User.objects.create_user(username="private_owner")
        root = DocumentFactory(owner=other)
        version = DocumentFactory(
            root_document=root,
            owner=self.user,
            mime_type="image/png",
        )
        version.source_path.write_bytes(b"private version")
        data = {"document": version.pk, "zone": {"width": 100, "height": 50}}
        self.assertEqual(self.client.get(self.preview_url(version)).status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/ocr_templates/test-zone/",
                data,
                format="json",
            ).status_code,
            403,
        )
        render.assert_not_called()
        extract.assert_not_called()
        grant_object(self.user, root, "view_document")
        extract.return_value = {"raw_text": None, "value": None}
        self.assertEqual(self.client.get(self.preview_url(version)).status_code, 200)
        self.assertEqual(
            self.client.post(
                "/api/ocr_templates/test-zone/",
                data,
                format="json",
            ).status_code,
            200,
        )
