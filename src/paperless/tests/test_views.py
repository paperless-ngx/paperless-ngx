import tempfile
from pathlib import Path

from django.conf import settings


def test_favicon_view(client):
    with tempfile.TemporaryDirectory() as tmpdir:
        static_dir = Path(tmpdir)
        favicon_path = static_dir / "paperless" / "img" / "favicon.ico"
        favicon_path.parent.mkdir(parents=True, exist_ok=True)
        favicon_path.write_bytes(b"FAKE ICON DATA")

        settings.STATIC_ROOT = static_dir

        response = client.get("/favicon.ico")
        assert response.status_code == 200
        assert response["Content-Type"] == "image/x-icon"
        assert b"".join(response.streaming_content) == b"FAKE ICON DATA"


def test_favicon_view_missing_file(client):
    settings.STATIC_ROOT = Path(tempfile.mkdtemp())
    response = client.get("/favicon.ico")
    assert response.status_code == 404
