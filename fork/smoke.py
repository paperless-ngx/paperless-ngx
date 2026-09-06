"""Exercise an isolated lab using exactly one allowlisted upstream document."""

import base64
import http.client
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

from mock_suggestions import PROPOSAL

# Intentionally no URL, credential or input-file options.
BASE_URL = "http://127.0.0.1:18080"
SAMPLE = Path(__file__).resolve().parents[1] / "src/documents/tests/samples/simple.pdf"
AUTH = base64.b64encode(b"reviewer:synthetic-review-only").decode()
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def api(path, data=None, method=None, content_type="application/json"):
    if not path.startswith("/api/"):
        raise ValueError("Only the fixed local Paperless API is allowed")
    body = json.dumps(data).encode() if isinstance(data, dict) else data
    request = urllib.request.Request(
        BASE_URL + path,
        data=body,
        method=method,
        headers={"Authorization": f"Basic {AUTH}", "Content-Type": content_type},
    )
    with OPENER.open(request, timeout=30) as response:
        return json.load(response)


def wait_for_api():
    deadline = time.monotonic() + 240
    last_error = None
    while time.monotonic() < deadline:
        try:
            api("/api/documents/?page_size=1")
            return
        except urllib.error.HTTPError as exc:
            if exc.code < 500:
                raise RuntimeError(
                    f"Lab API configuration/authentication error: HTTP {exc.code}",
                ) from exc
            last_error = exc
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ) as exc:
            last_error = exc
        time.sleep(2)
    raise RuntimeError(
        f"The isolated Paperless API did not become ready within 240s: {last_error}",
    ) from last_error


def get_or_create(kind, name):
    for item in api(f"/api/{kind}/?page_size=100")["results"]:
        if item["name"] == name:
            return item["id"]
    return api(f"/api/{kind}/", {"name": name})["id"]


def fixture_document():
    documents = api("/api/documents/?page_size=100")["results"]
    if documents:
        if len(documents) != 1 or documents[0]["title"] not in (
            "Upstream fixture",
            PROPOSAL["title"],
        ):
            raise RuntimeError("Unexpected lab contents; refusing to modify them")
        return documents[0]["id"]
    boundary = "paperless-synthetic-upload"
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="title"\r\n\r\n'
            f"Upstream fixture\r\n--{boundary}\r\n"
            'Content-Disposition: form-data; name="document"; filename="simple.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode()
        + SAMPLE.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    api(
        "/api/documents/post_document/",
        body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        documents = api("/api/documents/?page_size=100")["results"]
        if len(documents) == 1:
            return documents[0]["id"]
        time.sleep(2)
    raise RuntimeError("The upstream sample was not consumed within 180s")


def main():
    expected = subprocess.run(
        ["git", "show", "v3.1.3:src/documents/tests/samples/simple.pdf"],
        cwd=SAMPLE.parents[4],
        check=True,
        capture_output=True,
    ).stdout
    if SAMPLE.read_bytes() != expected:
        raise RuntimeError("Only the unchanged upstream sample is allowed")
    wait_for_api()
    tag = get_or_create("tags", "Fixture")
    correspondent = get_or_create("correspondents", "Example sender")
    doc_type = get_or_create("document_types", "Example document")
    document_id = fixture_document()
    path = f"/api/documents/{document_id}/"
    before = api(path)
    suggestions = api(path + "ai_suggestions/")
    assert suggestions["title"] == PROPOSAL["title"], suggestions
    assert suggestions["tags"] == [tag], suggestions
    assert suggestions["correspondents"] == [correspondent], suggestions
    assert suggestions["document_types"] == [doc_type], suggestions
    assert suggestions["dates"] == PROPOSAL["dates"], suggestions
    assert suggestions["storage_paths"] == [], suggestions
    after = api(path)
    for key in (
        "title",
        "tags",
        "correspondent",
        "document_type",
        "storage_path",
        "content",
    ):
        assert before[key] == after[key], f"Suggest unexpectedly modified {key}"
    assert api(path + "ai_suggestions/") == suggestions
    print(  # noqa: T201
        f"PASS: upstream fixture {document_id}, native AI suggestions, existing taxonomy, unchanged metadata, repeated request",
    )
    print(f"Review: {BASE_URL}/documents/{document_id}/details")  # noqa: T201


if __name__ == "__main__":
    main()
