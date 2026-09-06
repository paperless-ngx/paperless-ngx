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


def test_favicon_file_is_safari_compatible() -> None:
    """
    Safari's icon loader silently rejects any ICO with more than 6 images and
    then caches the rejection, so the shipped favicon must stay at 6 entries.
    Every embedded PNG must also match the size its directory entry declares.
    """
    favicon = (
        Path(__file__).parents[1] / "static" / "paperless" / "img" / "favicon.ico"
    ).read_bytes()

    entry_count = int.from_bytes(favicon[4:6], "little")
    assert 0 < entry_count <= 6

    for i in range(entry_count):
        entry = favicon[6 + i * 16 : 6 + (i + 1) * 16]
        declared = (entry[0] or 256, entry[1] or 256)
        offset = int.from_bytes(entry[12:16], "little")
        image = favicon[offset : offset + int.from_bytes(entry[8:12], "little")]
        if image.startswith(b"\x89PNG\r\n\x1a\n"):
            actual = (
                int.from_bytes(image[16:20], "big"),
                int.from_bytes(image[20:24], "big"),
            )
            assert actual == declared, f"entry {i}: PNG {actual} in {declared} slot"
