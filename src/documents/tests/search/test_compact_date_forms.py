"""Whoosh's compact, separator-free date spelling, resolved end to end.

whoosh-compat owns both widths of this spelling and asserts both of each
form's bounds directly: ``test_compact_numeric_datetime`` pins the 8-digit
form as a whole calendar day (lower bound, upper bound and exclusivity), and
``test_compact_numeric_datetime_full_width_is_a_single_second_instant`` pins
the 14-digit form as one instant. The 14-digit form is kept here as the single
representative because it is the one that exercises paperless's ``added``
DATETIME fast field at full precision: the corpus separates a document at
the named instant from one on the same calendar day at another hour and one
on the next day at the same hour, so a query that degrades into a whole-day
window, or drops the time of day, matches the wrong set rather than passing
on a corpus that could not tell the difference.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

from documents.models import Document

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


@pytest.fixture
def docs(backend: TantivyBackend) -> dict[str, int]:
    return {
        "instant": _index(
            backend,
            title="On the instant",
            content="x",
            checksum="compact-date-instant",
            added=datetime(2005, 3, 4, 15, 30, tzinfo=UTC),
        ).pk,
        "same_day": _index(
            backend,
            title="Same day, other hour",
            content="x",
            checksum="compact-date-same-day",
            added=datetime(2005, 3, 4, 9, 0, tzinfo=UTC),
        ).pk,
        "next_day": _index(
            backend,
            title="Next day, same hour",
            content="x",
            checksum="compact-date-next-day",
            added=datetime(2005, 3, 5, 15, 30, tzinfo=UTC),
        ).pk,
    }


def test_fourteen_digits_is_a_single_instant(
    backend: TantivyBackend,
    docs: dict[str, int],
) -> None:
    # same_day is what tells this apart from the 8-digit day-window form,
    # next_day from a form that ignored the time altogether.
    assert _matched_ids(backend, "added:20050304153000") == {docs["instant"]}
