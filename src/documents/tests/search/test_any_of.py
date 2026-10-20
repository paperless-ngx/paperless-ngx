"""_any_of, the clause-list helper.

One test, for the empty-list case its callers never produce but which the
helper still has to answer for.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from documents.search._query import _any_of

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestAnyOf:
    def test_an_empty_clause_list_matches_nothing(
        self,
        backend: TantivyBackend,
        index_document: Callable[..., Document],
    ) -> None:
        """
        GIVEN:
            - An indexed document, and no clauses at all
        WHEN:
            - _any_of is called with an empty list and the result is run
        THEN:
            - It matches no documents, rather than raising or matching
              everything
        """
        index_document(title="x", content="x")

        results = backend._index.searcher().search(_any_of([]), limit=10)

        assert len(results.hits) == 0
