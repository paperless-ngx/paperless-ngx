"""An unterminated ``[`` date range bracket at the API level.

``created:[2020`` (with or without a dangling ``to <value>``) now raises
BAD_DATE and the search endpoint returns HTTP 400, where it used to parse
past the missing ``]`` and silently pass the malformed range through.
A 400 is correct: malformed input should fail loudly rather than silently
matching an unintended query. Pinned at the API level -- the layer a user
or client actually sees -- rather than only against the parser directly.

The properly closed decoy proves the bracket is what matters, not
whoosh-compat's date grammar generally: ``created:[2020 to 2021]`` parses
and searches cleanly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework import status

from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from rest_framework.test import APIClient

    from documents.models import Document

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("_search_index")]


@pytest.fixture
def indexed_document() -> Document:
    from documents.search import get_backend

    doc = DocumentFactory.create(title="quarterly invoice", content="acme corp")
    get_backend().add_or_update(doc)
    return doc


class TestUnterminatedBracketReturnsA400:
    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("created:[2020", id="missing_upper_bound_and_bracket"),
            pytest.param("created:[2020 to 2021", id="missing_closing_bracket"),
        ],
    )
    def test_unterminated_bracket_is_a_400(
        self,
        admin_client: APIClient,
        indexed_document: Document,
        query: str,
    ) -> None:
        response = admin_client.get(f"/api/documents/?query={query}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "created" in str(response.data["query"])

    def test_properly_closed_bracket_still_searches_cleanly(
        self,
        admin_client: APIClient,
        indexed_document: Document,
    ) -> None:
        response = admin_client.get(
            "/api/documents/?query=created:[2020 to 2021]",
        )
        assert response.status_code == status.HTTP_200_OK
