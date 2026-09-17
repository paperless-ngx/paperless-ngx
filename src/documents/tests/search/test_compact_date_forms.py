"""Whoosh's compact, separator-free date spelling, resolved end to end.

whoosh-compat owns both widths of this spelling and asserts both forms'
bounds directly in its own test suite: the 8-digit form as a whole calendar
day (lower bound, upper bound and exclusivity), and the 14-digit form as a
single instant. The 14-digit form is kept here as the single representative
because it is the one that exercises paperless's ``added`` DATETIME fast
field at full precision: the corpus separates a document at the named
instant from one on the same calendar day at another hour and one on the
next day at the same hour, so a query that degrades into a whole-day
window, or drops the time of day, matches the wrong set rather than passing
on a corpus that could not tell the difference.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable

    from documents.models import Document

pytestmark = [pytest.mark.search, pytest.mark.django_db]


@pytest.fixture
def docs(index_document: Callable[..., Document]) -> dict[str, int]:
    return {
        "instant": index_document(
            title="On the instant",
            content="x",
            added=datetime(2005, 3, 4, 15, 30, tzinfo=UTC),
        ).pk,
        "same_day": index_document(
            title="Same day, other hour",
            content="x",
            added=datetime(2005, 3, 4, 9, 0, tzinfo=UTC),
        ).pk,
        "next_day": index_document(
            title="Next day, same hour",
            content="x",
            added=datetime(2005, 3, 5, 15, 30, tzinfo=UTC),
        ).pk,
    }


class TestCompactDateForms:
    def test_fourteen_digits_is_a_single_instant(
        self,
        matched_ids: Callable[[str], set[int]],
        docs: dict[str, int],
    ) -> None:
        """
        GIVEN:
            - Three documents indexed on the ``added`` DATETIME fast field:
              one at 2005-03-04T15:30:00, one on the same calendar day at a
              different hour, and one on the next day at the same hour
        WHEN:
            - Searching with the 14-digit compact date form
              ``added:20050304153000``
        THEN:
            - Only the document at that exact instant matches; the same-day
              document is what tells this apart from the 8-digit day-window
              form, and the next-day document from a form that ignored the
              time of day altogether
        """
        assert matched_ids("added:20050304153000") == {docs["instant"]}
