"""Date keyword phrases (``today``, etc.) resolved in a non-UTC timezone,
end to end.

paperless's own ``tz=get_current_timezone()`` plumbing
(``TantivyBackend._parse_query``) is exercised elsewhere only for
relative *ranges* (``added:[-1 week to now]``, in
documents/tests/test_api_search.py). This covers a date *keyword*
(``today``), whose day boundary depends on the active timezone the same
way but goes through whoosh-compat's DateParserPlugin resolution instead
of an explicit range.

Discriminating shape: frozen at 2026-06-15T02:00 UTC, which is
2026-06-14T22:00 in America/New_York -- still "today" (06-14) there, but
already "today" (06-15) in UTC. Two documents pin both directions of the
mistake a hardcoded-UTC bug would make:

- ``in_ny_today`` (added 2026-06-14T20:00 UTC = 2026-06-14T16:00 NY) is
  inside New York's "today" window and outside a naive UTC-calendar-day
  window. A ``tz``-ignoring bug would miss it.
- ``in_utc_calendar_day_only`` (added 2026-06-15T10:00 UTC =
  2026-06-15T06:00 NY) is inside a naive UTC-calendar-day window but
  outside New York's actual "today" window. A ``tz``-ignoring bug would
  wrongly match it.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import time_machine

from documents.models import Document

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper

    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

FROZEN_NOW = datetime(2026, 6, 15, 2, 0, tzinfo=UTC)


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


class TestDateKeywordUsesTheActiveTimezone:
    def test_today_matches_the_new_york_calendar_day_not_the_utc_one(
        self,
        backend: TantivyBackend,
        settings: SettingsWrapper,
    ) -> None:
        settings.TIME_ZONE = "America/New_York"
        with time_machine.travel(FROZEN_NOW, tick=False):
            in_ny_today = _index(
                backend,
                title="NY today",
                content="x",
                checksum="tz-keyword-ny-today",
                added=datetime(2026, 6, 14, 20, 0, tzinfo=UTC),
            )
            # Not captured: the exact-set assertion below already proves
            # this document (inside a naive UTC-calendar-day window, but
            # outside New York's actual "today") does not match.
            _index(
                backend,
                title="UTC calendar day only",
                content="x",
                checksum="tz-keyword-utc-calendar-day-only",
                added=datetime(2026, 6, 15, 10, 0, tzinfo=UTC),
            )

            assert _matched_ids(backend, "added:today") == {in_ny_today.pk}
