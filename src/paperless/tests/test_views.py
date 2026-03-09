from pathlib import Path

from django.test import Client
from pytest_django.fixtures import SettingsWrapper


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
