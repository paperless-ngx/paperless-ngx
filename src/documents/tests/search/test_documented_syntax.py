"""Pins the search syntax that ``docs/usage.md`` promises users.

Every query here appears verbatim, or as a direct paraphrase, in the
"Document searches" section of ``docs/usage.md``. Each case indexes real
documents and asserts on matched document IDs rather than on the parsed
query, because a query that parses cleanly is not necessarily a query that
means what the documentation says it means: ``added:now`` parses without a
single diagnostic and then matches nothing, because it resolves to an
instant rather than to a span.

The negative cases matter as much as the positive ones. They pin the
behaviours the docs explicitly warn about, so that if any of them ever
starts working the warning can be removed deliberately rather than being
left standing as a lie.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import time_machine

from documents.models import Document
from documents.models import Note
from documents.models import Tag
from documents.search._errors import InvalidDateQuery

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.contrib.auth.models import User

    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

# A Monday, so that "next monday"/"last monday" land a clean week either side.
FROZEN_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)

# The checksum used in the docs' `checksum:` example.
DOC_CHECKSUM = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


class TestLogicalExpressions:
    @pytest.fixture
    def docs(self, backend: TantivyBackend) -> dict[str, int]:
        return {
            "secret": _index(
                backend,
                title="Invoice one",
                content="invoice secret contents",
                checksum="doc-syntax-secret",
            ).pk,
            "plain": _index(
                backend,
                title="Invoice two",
                content="invoice ordinary contents",
                checksum="doc-syntax-plain",
            ).pk,
        }

    def test_not_excludes_a_term(
        self,
        backend: TantivyBackend,
        docs: dict[str, int],
    ) -> None:
        assert _matched_ids(backend, "invoice NOT secret") == {docs["plain"]}

    def test_leading_hyphen_requires_the_term_instead_of_excluding_it(
        self,
        backend: TantivyBackend,
        docs: dict[str, int],
    ) -> None:
        # The docs warn about exactly this: separators are stripped at index
        # time, so "-secret" is the term "secret" and the query is an AND.
        assert _matched_ids(backend, "invoice -secret") == {docs["secret"]}

    def test_or_inside_parentheses_matches_either_branch(
        self,
        backend: TantivyBackend,
        docs: dict[str, int],
    ) -> None:
        matched = _matched_ids(backend, "invoice AND (secret OR ordinary)")
        assert matched == {docs["secret"], docs["plain"]}


class TestPhraseSearch:
    def test_quoted_phrase_requires_the_words_in_order(
        self,
        backend: TantivyBackend,
    ) -> None:
        doc = _index(
            backend,
            title="Phrase",
            content="the quick brown fox jumps",
            checksum="doc-syntax-phrase",
        )
        assert _matched_ids(backend, '"quick brown fox"') == {doc.pk}
        assert _matched_ids(backend, '"brown quick fox"') == set()


class TestTagCommaList:
    """``tag:bills,unpaid`` is published syntax (docs/usage.md), so this checks
    that the documented spelling still returns what the docs promise: only the
    document carrying every listed tag.

    It is deliberately not proof of paperless's field configuration, and must
    not be read as such. Removing ``comma_values`` from the ``tag`` FieldSpec
    leaves this test passing, because paperless's analyzer splits the literal
    value "bills,unpaid" into the same two tokens the value-list reading
    produces, so the two readings select the same documents. The registry fact
    -- that ``tag`` opts in and no other field does -- is observable only at
    the registry, and is owned by test_registry.py's
    ``test_tag_is_comma_values``/``test_correspondent_is_not_comma_values``.
    """

    def test_comma_list_requires_every_listed_tag(
        self,
        backend: TantivyBackend,
    ) -> None:
        bills = Tag.objects.create(name="bills")
        unpaid = Tag.objects.create(name="unpaid")
        archived = Tag.objects.create(name="archived")

        both = Document.objects.create(
            title="Both tags",
            content="body",
            checksum="doc-syntax-tag-both",
        )
        both.tags.add(bills, unpaid)
        backend.add_or_update(both)

        one = Document.objects.create(
            title="One tag",
            content="body",
            checksum="doc-syntax-tag-one",
        )
        one.tags.add(bills, archived)
        backend.add_or_update(one)

        assert _matched_ids(backend, "tag:bills,unpaid") == {both.pk}
        assert _matched_ids(backend, "tag:bills") == {both.pk, one.pk}


class TestArchiveMetadataFields:
    @pytest.fixture
    def doc(self, backend: TantivyBackend, admin_user: User) -> Document:
        doc = Document.objects.create(
            title="Metadata",
            content="body",
            checksum=DOC_CHECKSUM,
            archive_serial_number=100,
            page_count=12,
            original_filename="invoice.pdf",
        )
        Note.objects.create(document=doc, user=admin_user, note="a note")
        backend.add_or_update(doc)
        return doc

    @pytest.mark.parametrize(
        "query",
        [
            "asn:100",
            "asn:[50 to 150]",
            "page_count:12",
            "page_count:[10 to 20]",
            "num_notes:1",
            "num_notes:[1 to 5]",
            "original_filename:invoice.pdf",
            f"checksum:{DOC_CHECKSUM}",
            "checksum:9f86d081*",
            # A checksum term is stored verbatim, but a checksum *pattern* is
            # lowercased before it is matched, which the docs now say outright
            # next to the "only a complete, lowercase checksum matches" rule
            # that the uppercase term in the negative list below pins.
            "checksum:9F86D081*",
        ],
    )
    def test_documented_metadata_query_matches(
        self,
        backend: TantivyBackend,
        doc: Document,
        query: str,
    ) -> None:
        assert _matched_ids(backend, query) == {doc.pk}

    @pytest.mark.parametrize(
        "query",
        [
            # The docs say only a complete, lowercase checksum matches.
            "checksum:9f86d081",
            f"checksum:{DOC_CHECKSUM.upper()}",
        ],
    )
    def test_partial_or_uppercase_checksum_matches_nothing(
        self,
        backend: TantivyBackend,
        doc: Document,
        query: str,
    ) -> None:
        assert _matched_ids(backend, query) == set()


class TestDocumentedDateForms:
    @pytest.fixture(autouse=True)
    def frozen_now(self) -> Generator[None, None, None]:
        with time_machine.travel(FROZEN_NOW, tick=False):
            yield

    @pytest.fixture
    def dated(self, backend: TantivyBackend) -> dict[str, int]:
        stamps = {
            "today": datetime(2026, 6, 15, 9, 0, tzinfo=UTC),
            "yesterday": datetime(2026, 6, 14, 9, 0, tzinfo=UTC),
            "tomorrow": datetime(2026, 6, 16, 9, 0, tzinfo=UTC),
            "next_monday": datetime(2026, 6, 22, 10, 0, tzinfo=UTC),
            "last_monday": datetime(2026, 6, 8, 10, 0, tzinfo=UTC),
            "january": datetime(2026, 1, 10, 10, 0, tzinfo=UTC),
            "old": datetime(2005, 3, 4, 15, 30, tzinfo=UTC),
        }
        return {
            label: _index(
                backend,
                title=label,
                content="dated body",
                checksum=f"doc-syntax-date-{label}",
                added=stamp,
            ).pk
            for label, stamp in stamps.items()
        }

    @pytest.mark.parametrize(
        ("query", "label"),
        [
            ("added:today", "today"),
            ("added:yesterday", "yesterday"),
            ("added:tomorrow", "tomorrow"),
            ('added:"next monday"', "next_monday"),
            ('added:"last monday"', "last_monday"),
            ("added:january", "january"),
            ("added:2005-03-04", "old"),
            ("added:2005-03", "old"),
            ("added:[2005-01-01 to 2005-12-31]", "old"),
            ("added:[2005 to 2009]", "old"),
            # A full timestamp works, but only quoted when it stands alone,
            # and only unquoted when it is a range bound. The bare standalone
            # spelling is pinned as a non-match below.
            ('added:"2005-03-04T15:30:00Z"', "old"),
            ("added:[2005-03-04T09:00:00Z to 2005-03-04T17:00:00Z]", "old"),
            # A quoted range bound works when the quotes are single ones; the
            # double-quoted spelling is pinned as an error below.
            ("added:['2005-03-04' to 2005-03-05]", "old"),
        ],
    )
    def test_documented_date_form_matches_its_day_or_month(
        self,
        backend: TantivyBackend,
        dated: dict[str, int],
        query: str,
        label: str,
    ) -> None:
        assert _matched_ids(backend, query) == {dated[label]}

    @pytest.mark.parametrize(
        "query",
        [
            # Zero-width: these resolve to a single instant, not a span, so
            # nothing in a realistic corpus lands on them. The docs warn
            # about them rather than presenting them as usable.
            "added:now",
            "added:noon",
            "added:midnight",
            # Quoting is what rescues the other multi-word date expressions,
            # so pin that it does not rescue these: the problem is the width
            # of the resulting range, not the way the value is delimited.
            # One quoted spelling is enough for that; which keyword sits
            # inside the quotes is grammar whoosh-compat owns.
            'added:"now"',
            # A relative offset, which the warning in the docs names by this
            # exact spelling. Standing alone it is an instant like the rest of
            # this list; the same offset used as a range bound is a real
            # window, pinned by the test below.
            'added:"-1 week"',
        ],
    )
    def test_forms_the_docs_warn_about_match_nothing(
        self,
        backend: TantivyBackend,
        dated: dict[str, int],
        query: str,
    ) -> None:
        assert _matched_ids(backend, query) == set()

    def test_bare_timestamp_is_rejected_rather_than_matching_nothing(
        self,
        backend: TantivyBackend,
        dated: dict[str, int],
    ) -> None:
        """The bare, unquoted spelling of a full timestamp. The quoted and
        range-bound spellings pinned above do work and match this fixture's
        document; this one is a user-fixable error rather than an empty
        result set, so the docs tell the user to quote it.

        The reported value is the whole contiguous fragment the user typed,
        not just the prefix the date grammar's tokenizer first split on.
        """
        with pytest.raises(InvalidDateQuery) as exc_info:
            _matched_ids(backend, "added:2005-03-04T15:30:00Z")
        assert exc_info.value.field == "added"
        assert exc_info.value.value == "2005-03-04T15:30:00Z"

    def test_relative_offset_as_a_range_bound_is_a_real_window(
        self,
        backend: TantivyBackend,
        dated: dict[str, int],
    ) -> None:
        """The same offset that matches nothing on its own spans the last
        seven days as a lower bound. The docs say so, next to the warning
        about the standalone form, so both readings are pinned together.

        "last_monday" is indexed at 2026-06-08T10:00, two hours before the
        window opens, so its exclusion is what shows the bound is the offset
        and not a whole-day rounding of it.
        """
        assert _matched_ids(backend, "added:['-1 week' to now]") == {
            dated["today"],
            dated["yesterday"],
        }

    def test_double_quoted_range_bound_is_rejected(
        self,
        backend: TantivyBackend,
        dated: dict[str, int],
    ) -> None:
        """Quoting a range bound is allowed, but only with single quotes: the
        double-quoted spelling reaches the date grammar with its quotes still
        attached and is not a recognizable date. The docs say so, so pin which
        of the two quote characters is the one that fails.
        """
        with pytest.raises(InvalidDateQuery) as exc_info:
            _matched_ids(backend, 'added:["2005-03-04" to 2005-03-05]')
        assert exc_info.value.value == '"2005-03-04"'
