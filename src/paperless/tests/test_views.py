import json
from pathlib import Path

import pytest
from django.test import Client
from pytest_django.fixtures import SettingsWrapper

from paperless.models import ApplicationConfiguration


def test_favicon_view(
    client: Client,
    tmp_path: Path,
    settings: SettingsWrapper,
) -> None:
    favicon_path = tmp_path / "paperless" / "img" / "favicon.ico"
    favicon_path.parent.mkdir(parents=True)
    favicon_path.write_bytes(b"FAKE ICON DATA")

    settings.STATIC_ROOT = tmp_path

    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response["Content-Type"] == "image/x-icon"
    assert b"".join(response.streaming_content) == b"FAKE ICON DATA"


def test_favicon_view_missing_file(
    client: Client,
    tmp_path: Path,
    settings: SettingsWrapper,
) -> None:
    settings.STATIC_ROOT = tmp_path
    response = client.get("/favicon.ico")
    assert response.status_code == 404


@pytest.mark.django_db
def test_manifest_view_default_title(
    client: Client,
) -> None:
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/manifest+json"
    data = json.loads(response.content)
    assert data["name"] == "Paperless-ngx"
    assert data["short_name"] == "Paperless-ngx"
    assert data["display"] == "standalone"


@pytest.mark.django_db
def test_manifest_view_custom_title_from_settings(
    client: Client,
    settings: SettingsWrapper,
) -> None:
    settings.APP_TITLE = "My Custom App"
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert data["name"] == "My Custom App"
    assert data["short_name"] == "My Custom App"


@pytest.mark.django_db
def test_manifest_view_custom_title_from_db(
    client: Client,
) -> None:
    ApplicationConfiguration.objects.update_or_create(
        pk=1,
        defaults={"app_title": "DB Custom Title"},
    )
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert data["name"] == "DB Custom Title"
    assert data["short_name"] == "DB Custom Title"


@pytest.mark.django_db
def test_manifest_view_locale_prefixed_path(
    client: Client,
) -> None:
    response = client.get("/en-US/manifest.webmanifest")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/manifest+json"
