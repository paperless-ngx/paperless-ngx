"""Tests for the OCR Template API."""

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.db import IntegrityError
from rest_framework import status
from rest_framework.test import APITestCase

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import MatchingModel
from documents.models import OcrTemplate
from documents.models import OcrTemplateZone
from paperless_testing.dirs import DirectoriesMixin
from paperless_testing.factories import DocumentFactory
from paperless_testing.permissions import grant_global
from paperless_testing.permissions import grant_object

CONTENT = "Northwind Power & Light statement"


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
        self.custom_field_int = CustomField.objects.create(
            name="Amount",
            data_type=CustomField.FieldDataType.INT,
        )
        self.custom_field_doclink = CustomField.objects.create(
            name="Related Docs",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )

        return super().setUp()

    def _make_template_data(self, **overrides):
        data = {
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

    def _make_zone_data(self, **overrides):
        data = {
            "name": "Zone 1",
            "custom_field": self.custom_field_text.pk,
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

    # --- Create ---

    def test_create_template(self):
        """
        GIVEN:
            - A document type and custom fields exist
        WHEN:
            - API request to create an OCR template with one zone
        THEN:
            - The template and zone are created
        """
        data = self._make_template_data(
            zones=[
                self._make_zone_data(
                    name="Invoice Number",
                    x=1500,
                    y=200,
                    width=800,
                    height=100,
                ),
            ],
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        result = resp.json()
        self.assertEqual(result["name"], "Invoice Template")
        self.assertEqual(result["match"], "Northwind")
        self.assertEqual(result["matching_algorithm"], MatchingModel.MATCH_ANY)
        self.assertEqual(len(result["zones"]), 1)
        self.assertEqual(result["zones"][0]["name"], "Invoice Number")
        self.assertEqual(OcrTemplate.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.count(), 1)

    def test_create_template_sets_owner(self):
        """
        GIVEN:
            - A user creating an OCR template
        WHEN:
            - API request to create it without an owner
        THEN:
            - The requesting user owns the template
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(self._make_template_data()),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OcrTemplate.objects.get().owner, self.user)

    def test_list_only_shows_permitted_templates(self):
        """
        GIVEN:
            - Templates that are unowned, owned by the user, owned by another
              user, and owned by another user but shared with the user
        WHEN:
            - The user lists OCR templates
        THEN:
            - Only the unowned, owned and shared templates are returned
        """
        other = User.objects.create_user(username="other")
        user = User.objects.create_user(username="template_viewer")
        user.user_permissions.add(Permission.objects.get(codename="view_ocrtemplate"))

        def template(name, owner=None):
            return OcrTemplate.objects.create(
                name=name,
                match="Northwind",
                source_width=1000,
                source_height=1000,
                owner=owner,
            )

        template("Unowned")
        template("Mine", owner=user)
        template("Private", owner=other)
        grant_object(user, template("Shared", owner=other), "view_ocrtemplate")
        self.client.force_authenticate(user=user)

        response = self.client.get(self.ENDPOINT)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertCountEqual(
            [t["name"] for t in response.json()["results"]],
            ["Unowned", "Mine", "Shared"],
        )

    def test_cannot_change_another_users_template(self):
        """
        GIVEN:
            - A template owned by another user
        WHEN:
            - A user with global change permission tries to update it
        THEN:
            - The update is refused until the user is granted change on it
        """
        other = User.objects.create_user(username="other")
        user = User.objects.create_user(username="template_editor")
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=["view_ocrtemplate", "change_ocrtemplate"],
            ),
        )
        template = OcrTemplate.objects.create(
            name="Private",
            match="Northwind",
            source_width=1000,
            source_height=1000,
            owner=other,
        )
        grant_object(user, template, "view_ocrtemplate")
        self.client.force_authenticate(user=user)
        url = f"{self.ENDPOINT}{template.pk}/"

        response = self.client.patch(url, {"name": "Renamed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        grant_object(user, template, "change_ocrtemplate")
        response = self.client.patch(url, {"name": "Renamed"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        template.refresh_from_db()
        self.assertEqual(template.name, "Renamed")
        self.assertEqual(template.owner, other)

    def test_create_template_rejects_automatic_matching(self):
        """
        GIVEN:
            - A template payload with automatic matching
        WHEN:
            - API request to create it
        THEN:
            - The request is rejected, automatic matching needs assigned
              documents to learn from
        """
        response = self.client.post(
            self.ENDPOINT,
            json.dumps(
                self._make_template_data(matching_algorithm=MatchingModel.MATCH_AUTO),
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OcrTemplate.objects.count(), 0)

    def test_create_template_multiple_zones(self):
        """
        GIVEN:
            - Multiple custom fields exist
        WHEN:
            - A template with multiple zones is created
        THEN:
            - All zones are created
        """
        data = self._make_template_data(
            zones=[
                self._make_zone_data(
                    name="Invoice Number",
                    custom_field=self.custom_field_text.pk,
                ),
                self._make_zone_data(
                    name="Invoice Date",
                    custom_field=self.custom_field_date.pk,
                    order=1,
                ),
            ],
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.json()["zones"]), 2)
        self.assertEqual(OcrTemplateZone.objects.count(), 2)

    def test_create_template_no_zones(self):
        """
        GIVEN:
            - Valid template data without zones
        WHEN:
            - Template is created
        THEN:
            - Template is created with no zones
        """
        data = self._make_template_data()
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(resp.json()["zones"]), 0)

    # --- Validation ---

    def test_create_template_zero_source_width_rejected(self):
        """
        GIVEN:
            - Template data with source_width=0
        WHEN:
            - Create is attempted
        THEN:
            - 400 error is returned
        """
        data = self._make_template_data(source_width=0)
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_template_zero_source_height_rejected(self):
        data = self._make_template_data(source_height=0)
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_zero_width_rejected(self):
        data = self._make_template_data(
            zones=[self._make_zone_data(width=0)],
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_zero_height_rejected(self):
        data = self._make_template_data(
            zones=[self._make_zone_data(height=0)],
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_exceeds_source_width_rejected(self):
        """Zone that extends beyond the source image width should be rejected."""
        data = self._make_template_data(
            source_width=1000,
            zones=[self._make_zone_data(x=800, width=300)],  # 800+300 > 1000
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_exceeds_source_height_rejected(self):
        data = self._make_template_data(
            source_height=1000,
            zones=[self._make_zone_data(y=900, height=200)],  # 900+200 > 1000
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_zone_unsupported_custom_field_type_rejected(self):
        """DOCUMENTLINK and SELECT fields can't be populated via OCR."""
        data = self._make_template_data(
            zones=[self._make_zone_data(custom_field=self.custom_field_doclink.pk)],
        )
        resp = self.client.post(
            self.ENDPOINT,
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zone_bounds_use_the_zones_own_source_dimensions(self):
        data = self._make_template_data(
            source_width=500,
            source_height=500,
            zones=[
                self._make_zone_data(
                    x=700,
                    y=600,
                    width=200,
                    height=100,
                    zone_source_width=1000,
                    zone_source_height=1000,
                ),
            ],
        )
        response = self.client.post(self.ENDPOINT, data, format="json")
        self.assertEqual(response.status_code, 201)
        data["name"] = "Invalid bounds"
        data["zones"][0]["zone_source_width"] = 800
        response = self.client.post(self.ENDPOINT, data, format="json")
        self.assertEqual(response.status_code, 400)

    def test_changing_source_dimensions_checks_existing_zones(self):
        response = self.client.post(
            self.ENDPOINT,
            self._make_template_data(zones=[self._make_zone_data()]),
            format="json",
        )
        url = f"{self.ENDPOINT}{response.json()['id']}/"
        response = self.client.patch(url, {"source_width": 200}, format="json")
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(url, {"source_width": 1000}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_partial_zone_replacement_uses_saved_dimensions(self):
        template = OcrTemplate.objects.create(
            name="Test",
            owner=self.user,
            source_width=1000,
            source_height=1000,
        )
        url = f"{self.ENDPOINT}{template.pk}/"
        for changes in [{"x": 900, "width": 200}, {"y": 990, "height": 50}]:
            with self.subTest(changes=changes):
                response = self.client.patch(
                    url,
                    {"zones": [self._make_zone_data(**changes)]},
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
        response = self.client.patch(
            url,
            {"zones": [self._make_zone_data()]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

    def test_partial_zone_replacement_requires_complete_zones(self):
        template = OcrTemplate.objects.create(
            name="Test",
            owner=self.user,
            source_width=1000,
            source_height=1000,
        )
        zone = OcrTemplateZone.objects.create(
            template=template,
            name="Original",
            x=0,
            y=0,
            width=10,
            height=10,
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            {"zones": [{"name": "Incomplete"}]},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(list(template.zones.all()), [zone])

    def test_custom_and_builtin_zones_can_have_no_custom_field(self):
        data = self._make_template_data(
            zones=[
                self._make_zone_data(custom_field=None),
                self._make_zone_data(name="Title", target="title", custom_field=None),
            ],
        )
        response = self.client.post(self.ENDPOINT, data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            [z["custom_field"] for z in response.json()["zones"]],
            [None, None],
        )
        zone = OcrTemplateZone.objects.get(name="Title")
        self.assertEqual(str(zone), f"{zone.template.name} -> Title")

    def test_invalid_page_numbers_are_rejected(self):
        for page in [0, -2, "invalid"]:
            with self.subTest(page=page):
                response = self.client.post(
                    self.ENDPOINT,
                    self._make_template_data(zones=[self._make_zone_data(page=page)]),
                    format="json",
                )
                self.assertEqual(response.status_code, 400)

    def test_combine_formats_must_map_keys_to_strings(self):
        for formats in [[], "invalid", {"title": []}, {"title": None}]:
            with self.subTest(formats=formats):
                response = self.client.post(
                    self.ENDPOINT,
                    self._make_template_data(combine_formats=formats),
                    format="json",
                )
                self.assertEqual(response.status_code, 400)
        response = self.client.post(
            self.ENDPOINT,
            self._make_template_data(combine_formats={"title": " {A} - {B} "}),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["combine_formats"], {"title": " {A} - {B} "})

    def test_template_creation_rolls_back_when_a_zone_cannot_be_saved(self):
        data = self._make_template_data(
            zones=[self._make_zone_data(), self._make_zone_data(name="Broken")],
        )
        create = OcrTemplateZone.objects.create

        def create_zone(**kwargs):
            if kwargs["name"] == "Broken":
                raise IntegrityError("Zone save failed")
            return create(**kwargs)

        with patch(
            "documents.serialisers.OcrTemplateZone.objects.create",
            side_effect=create_zone,
        ):
            with self.assertRaises(IntegrityError):
                self.client.post(self.ENDPOINT, data, format="json")
        self.assertEqual(OcrTemplate.objects.count(), 0)
        self.assertEqual(OcrTemplateZone.objects.count(), 0)

    def test_template_update_rolls_back_without_losing_previous_zones(self):
        template = OcrTemplate.objects.create(
            name="Original",
            owner=self.user,
            source_width=1000,
            source_height=1000,
        )
        zone = OcrTemplateZone.objects.create(
            template=template,
            name="Original zone",
            x=0,
            y=0,
            width=10,
            height=10,
        )
        data = self._make_template_data(name="Changed", zones=[self._make_zone_data()])
        with patch(
            "documents.serialisers.OcrTemplateZone.objects.create",
            side_effect=IntegrityError("Zone save failed"),
        ):
            with self.assertRaises(IntegrityError):
                self.client.put(f"{self.ENDPOINT}{template.pk}/", data, format="json")
        template.refresh_from_db()
        self.assertEqual(template.name, "Original")
        self.assertEqual(list(template.zones.all()), [zone])

    def test_explicit_empty_zones_removes_all_zones(self):
        template = OcrTemplate.objects.create(
            name="Test",
            owner=self.user,
            source_width=1000,
            source_height=1000,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone",
            x=0,
            y=0,
            width=10,
            height=10,
        )
        response = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            {"zones": []},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(template.zones.exists())

    # --- List ---

    def test_list_templates(self):
        template = OcrTemplate.objects.create(
            name="Test Template",
            match="Northwind",
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone 1",
            custom_field=self.custom_field_text,
            x=100,
            y=100,
            width=200,
            height=50,
        )

        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["results"][0]["zones"]), 1)

    def test_list_empty(self):
        resp = self.client.get(self.ENDPOINT)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["count"], 0)

    # --- Update ---

    def test_update_template_replaces_zones(self):
        """PUT should replace all zones with the new set."""
        template = OcrTemplate.objects.create(
            name="Old Name",
            match="Northwind",
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Old Zone",
            custom_field=self.custom_field_text,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        data = self._make_template_data(
            name="New Name",
            zones=[
                self._make_zone_data(
                    name="New Zone",
                    custom_field=self.custom_field_date.pk,
                ),
            ],
        )
        resp = self.client.put(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps(data),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        template.refresh_from_db()
        self.assertEqual(template.name, "New Name")
        self.assertEqual(OcrTemplateZone.objects.count(), 1)
        self.assertEqual(OcrTemplateZone.objects.first().name, "New Zone")

    # --- Delete ---

    def test_delete_template_cascades_zones(self):
        template = OcrTemplate.objects.create(
            name="To Delete",
            match="Northwind",
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Zone",
            custom_field=self.custom_field_text,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = self.client.delete(f"{self.ENDPOINT}{template.pk}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OcrTemplate.objects.count(), 0)
        self.assertEqual(OcrTemplateZone.objects.count(), 0)

    def test_delete_nonexistent_returns_404(self):
        resp = self.client.delete(f"{self.ENDPOINT}99999/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # --- Patch ---

    def test_patch_toggle_enabled(self):
        template = OcrTemplate.objects.create(
            name="Toggle Test",
            match="Northwind",
            source_width=2480,
            source_height=3508,
            enabled=True,
        )

        resp = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps({"enabled": False}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        template.refresh_from_db()
        self.assertFalse(template.enabled)

    def test_patch_preserves_zones(self):
        """PATCH without zones field should not delete existing zones."""
        template = OcrTemplate.objects.create(
            name="Patch Test",
            match="Northwind",
            source_width=2480,
            source_height=3508,
        )
        OcrTemplateZone.objects.create(
            template=template,
            name="Existing Zone",
            custom_field=self.custom_field_text,
            x=0,
            y=0,
            width=100,
            height=100,
        )

        resp = self.client.patch(
            f"{self.ENDPOINT}{template.pk}/",
            data=json.dumps({"name": "Updated Name"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(OcrTemplateZone.objects.count(), 1)

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
        extract.assert_called_once_with(document, None, templates=[template])

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
        user.user_permissions.add(Permission.objects.get(codename="view_ocrtemplate"))
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
        user.user_permissions.add(Permission.objects.get(codename="add_ocrtemplate"))
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

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_reports_only_templates_visible_to_the_document_owner(
        self,
        extract,
    ):
        owner = User.objects.create_user(username="document_owner")
        document = DocumentFactory(content=CONTENT, owner=owner)
        document.source_path.write_bytes(b"test PDF")
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
        extract.assert_called_once()

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

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_reports_completed_results(self, extract):
        document = DocumentFactory(
            content=CONTENT,
            mime_type="application/pdf",
        )
        document.source_path.write_bytes(b"test PDF")
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
                        "value": document.title,
                    },
                ],
            },
        )
        extract.assert_called_once()

    @patch("documents.zone_ocr.run_zone_extraction")
    def test_run_zone_ocr_reports_all_target_types_and_missing_values(self, extract):
        document = DocumentFactory(content=CONTENT, archive_serial_number=123)
        document.source_path.write_bytes(b"test PDF")
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
                "Present": "INV-123",
                "Missing": None,
                "Unassigned": None,
                "Title": document.title,
                "ASN": 123,
                "Created": document.created.isoformat(),
            },
        )


class TestOcrTemplatePreviewAPI(DirectoriesMixin, APITestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username="template_editor")
        grant_global(self.user, "view_ocrtemplate", "add_ocrtemplate")
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
