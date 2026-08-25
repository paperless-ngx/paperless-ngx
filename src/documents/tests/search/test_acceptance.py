"""Result-level acceptance corpus: real documents indexed via build_schema(),
real queries run through parse_user_query(), matched-document-ID sets
asserted — not intermediate ASTs or query strings. This is paperless-ngx's
analogue of whoosh-compat's own tests/emitter/test_acceptance_e2e.py.

Supersedes test_query.py's TestParseUserQuery result-level cases.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import time_machine
from django.contrib.auth.models import User

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Note
from documents.models import StoragePath
from documents.search._query import parse_user_query

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]

FROZEN_NOW = datetime(2026, 6, 15, 12, 0, tzinfo=UTC)


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    """Create a Document and index it in one step, for the common case
    where nothing needs to happen between the two (no related Note/
    CustomFieldInstance to attach first)."""
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


@pytest.fixture
def indexed_documents(backend: TantivyBackend) -> dict[str, int]:
    """Index a small fixture set, return {label: doc_id} for corpus queries."""
    docs = {
        "invoice_2020": _index(
            backend,
            title="Invoice 2020",
            content="invoice total due",
            checksum="acc-invoice-2020",
            archive_serial_number=100,
        ),
        "invoice_2021": _index(
            backend,
            title="Invoice 2021",
            content="invoice total due",
            checksum="acc-invoice-2021",
            archive_serial_number=101,
        ),
        "invoice_2023": _index(
            backend,
            title="Invoice 2023",
            content="invoice total due",
            checksum="acc-invoice-2023",
            archive_serial_number=102,
        ),
        "receipt_2022": _index(
            backend,
            title="Receipt 2022",
            content="receipt total due",
            checksum="acc-receipt-2022",
            archive_serial_number=103,
        ),
    }
    return {label: doc.pk for label, doc in docs.items()}


class TestIssue13568BracketWildcard:
    """paperless-ngx#13568: title:202[0-3]* must keep its character class,
    not fold to a prefix query that silently drops it."""

    def test_bracket_class_wildcard_matches_only_in_range_years(
        self,
        backend: TantivyBackend,
        indexed_documents: dict[str, int],
    ) -> None:
        # [0-1] (not [0-3]) is deliberate: the fixture's four years are
        # 2020/2021/2022/2023, i.e. their trailing digit is 0/1/2/3
        # respectively - a [0-3] class would match all four and the test
        # would pass even if the character class were silently dropped and
        # folded to an unconstrained "202*" prefix. [0-1] partitions the
        # fixture into a genuine in-range/out-of-range split.
        matched = _matched_ids(backend, "title:202[0-1]*")
        expected = {
            indexed_documents["invoice_2020"],
            indexed_documents["invoice_2021"],
        }
        assert matched == expected, (
            "title:202[0-1]* must match 2020/2021 titles and exclude 2022/2023 "
            "- if this matches everything, the wildcard's character class was "
            "silently dropped (issue #13568's original bug)"
        )


class TestFieldBoosts:
    def test_title_boost_ranks_title_match_above_content_only_match(
        self,
        backend: TantivyBackend,
    ) -> None:
        title_match = _index(
            backend,
            title="urgent",
            content="nothing else relevant",
            checksum="acc-boost-title",
        )
        _index(
            backend,
            title="nothing",
            content="urgent matter here",
            checksum="acc-boost-content",
        )
        query = parse_user_query(backend._index, "urgent", UTC)
        searcher = backend._index.searcher()
        results = searcher.search(query, limit=10)
        ranked_ids = [
            searcher.doc(addr).to_dict()["id"][0] for _score, addr in results.hits
        ]
        assert ranked_ids[0] == title_match.pk


class TestJsonSubpaths:
    def test_notes_user_matches_document_with_that_note_author(
        self,
        backend: TantivyBackend,
    ) -> None:
        alice = User.objects.create_user(username="alice")
        doc_with_note = Document.objects.create(
            title="Has note",
            content="x",
            checksum="acc-note-with",
        )
        Note.objects.create(document=doc_with_note, user=alice, note="reminder")
        backend.add_or_update(doc_with_note)
        _index(backend, title="No note", content="x", checksum="acc-note-without")
        matched = _matched_ids(backend, "notes.user:alice")
        assert matched == {doc_with_note.pk}

    def test_custom_fields_name_and_value_combine(
        self,
        backend: TantivyBackend,
    ) -> None:
        field = CustomField.objects.create(
            name="Contract Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        other_field = CustomField.objects.create(
            name="Other Field",
            data_type=CustomField.FieldDataType.STRING,
        )
        matching = Document.objects.create(
            title="Matching",
            content="x",
            checksum="acc-cf-matching",
        )
        CustomFieldInstance.objects.create(
            document=matching,
            field=field,
            value_text="policy",
        )
        backend.add_or_update(matching)
        non_matching = Document.objects.create(
            title="Non-matching",
            content="x",
            checksum="acc-cf-nonmatching",
        )
        CustomFieldInstance.objects.create(
            document=non_matching,
            field=other_field,
            value_text="policy",
        )
        backend.add_or_update(non_matching)
        matched = _matched_ids(
            backend,
            'custom_fields.name:"Contract Number" custom_fields.value:policy',
        )
        assert matched == {matching.pk}


class TestUnregisteredIdFieldFoldsToLiteralText:
    """tag_id, owner_id, etc. are intentionally excluded from the
    FieldRegistry - always internal index columns, never meant to be
    query-addressable. Prove an unregistered field folds to a literal
    text search that matches nothing, rather than erroring."""

    def test_tag_id_query_matches_nothing(
        self,
        backend: TantivyBackend,
        indexed_documents: dict[str, int],
    ) -> None:
        matched = _matched_ids(backend, "tag_id:5")
        assert matched == set()


class TestFuzzyBlendSurvivesWhooshGrammar:
    """A query mixing whoosh-only grammar (a date keyword) with a typo'd
    free-text word must still fuzzy-match the intended document when
    ADVANCED_FUZZY_SEARCH_THRESHOLD is enabled. The fuzzy clause is built
    from the parsed query's free-text tokens (whoosh_compat's
    free_text_tokens), never from the raw query string, so whoosh grammar
    that tantivy's own parser rejects cannot knock the fuzzy clause out."""

    def test_typo_fuzzy_matches_alongside_date_keyword(
        self,
        backend: TantivyBackend,
        settings,
    ) -> None:
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.5
        with time_machine.travel(FROZEN_NOW, tick=False):
            doc = _index(
                backend,
                title="Receipt March",
                content="receipt total due",
                checksum="fuzzy-blend-1",
                archive_serial_number=900,
            )
            # Sanity: the exact spelling matches through the exact clause.
            assert doc.pk in _matched_ids(backend, "added:today receipt")
            # The regression: the misspelling (one transposition) only
            # matches via the fuzzy clause, and "added:today" is
            # whoosh-only grammar tantivy's parser rejects, so raw-string
            # fuzzy parsing skips the clause entirely and this returns
            # nothing. The typo is deliberate; keep codespell away from it.
            typo_query = "added:today reciept"  # codespell:ignore reciept
            assert doc.pk in _matched_ids(backend, typo_query)

    def test_negated_words_do_not_fuzzy_match(
        self,
        backend: TantivyBackend,
        settings,
    ) -> None:
        # A term the user excluded must not resurface through the fuzzy
        # clause. The shape is chosen so this genuinely discriminates: the
        # indexed document contains the NOT'd word but NOT the positive
        # word, so nothing matches the exact clause, and a fuzzy string
        # naively built from ALL words (including the NOT'd one) would
        # make this document the sole hit, normalize its score to 1.0,
        # and survive any threshold. (A shape with an exact-matching
        # sibling document does NOT discriminate: normalization ranks the
        # resurfaced doc far below the exact match and the threshold cuts
        # it even for a naive implementation.)
        settings.ADVANCED_FUZZY_SEARCH_THRESHOLD = 0.5
        with time_machine.travel(FROZEN_NOW, tick=False):
            _index(
                backend,
                title="Receipt Archive",
                content="receipt archived stack",
                checksum="fuzzy-blend-2",
                archive_serial_number=901,
            )
            assert _matched_ids(backend, "added:today total NOT receipt") == set()


class TestUnquotedDateKeywordPhrases:
    """The unquoted spelling (added:previous month) is honored natively by
    whoosh-compat's own grammar for this closed phrase vocabulary — no
    app-level rewrite is involved. Pins that the historically supported
    spelling keeps working now that paperless no longer pre-quotes it."""

    @pytest.fixture
    def period_documents(self, backend: TantivyBackend) -> dict[str, int]:
        with time_machine.travel(FROZEN_NOW, tick=False):
            in_may = _index(
                backend,
                title="May Doc",
                content="statement",
                checksum="kw-may",
                archive_serial_number=910,
                added=datetime(2026, 5, 20, 12, 0, tzinfo=UTC),
            )
            in_june = _index(
                backend,
                title="June Doc",
                content="statement",
                checksum="kw-june",
                archive_serial_number=911,
                added=datetime(2026, 6, 10, 12, 0, tzinfo=UTC),
            )
        return {"in_may": in_may.pk, "in_june": in_june.pk}

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("added:previous month", id="unquoted"),
            pytest.param('added:"previous month"', id="quoted"),
            pytest.param("added:Previous Month", id="unquoted-mixed-case"),
        ],
    )
    def test_unquoted_matches_the_same_documents_as_quoted(
        self,
        backend: TantivyBackend,
        period_documents: dict[str, int],
        query: str,
    ) -> None:
        with time_machine.travel(FROZEN_NOW, tick=False):
            assert _matched_ids(backend, query) == {period_documents["in_may"]}

    @pytest.mark.parametrize(
        "query",
        [
            pytest.param("added:this month", id="this-month"),
            pytest.param("added:this year", id="this-year"),
            pytest.param("added:previous week", id="previous-week"),
            pytest.param("added:previous quarter", id="previous-quarter"),
            pytest.param("added:previous year", id="previous-year"),
            pytest.param("created:previous month", id="created-field"),
            pytest.param("modified:previous month", id="modified-field"),
        ],
    )
    def test_every_phrase_and_date_field_parses_without_error(
        self,
        backend: TantivyBackend,
        period_documents: dict[str, int],
        query: str,
    ) -> None:
        # The whole vocabulary times every date field must at least parse
        # and search cleanly (no SearchQueryError -> no HTTP 400); exact
        # window semantics are whoosh-compat's, pinned in its own suite.
        with time_machine.travel(FROZEN_NOW, tick=False):
            _matched_ids(backend, query)

    def test_text_field_keyword_words_are_ordinary_text(
        self,
        backend: TantivyBackend,
        period_documents: dict[str, int],
    ) -> None:
        # "previous month" after a TEXT field (or unfielded) is ordinary
        # text, not a date phrase: a title actually containing the words
        # matches, and the date-window documents do not.
        with time_machine.travel(FROZEN_NOW, tick=False):
            wordy = _index(
                backend,
                title="Notes from the previous month",
                content="meeting notes",
                checksum="kw-text",
                archive_serial_number=912,
            )
            assert _matched_ids(backend, "title:previous month") == {wordy.pk}


class TestFieldAliases:
    """type:/path: are registry aliases for document_type:/storage_path:.
    The only other alias coverage is parse-shape; these prove resolution
    end-to-end against a real index."""

    def test_type_alias_and_canonical_name_match_the_same_document(
        self,
        backend: TantivyBackend,
    ) -> None:
        invoice_type = DocumentType.objects.create(name="invoice")
        # Discriminating shape: document_type is itself a default search
        # field, so if alias resolution ever broke and "type:invoice"
        # demoted to unfielded text, the token would STILL match the typed
        # document through the field value. The decoy carries the query
        # word in content, so a demoted search matches BOTH documents and
        # the exact-set assertions fail. (The title avoids stemming to
        # "type": english stems Typed -> type.)
        typed = _index(
            backend,
            title="First",
            content="quarterly statement",
            checksum="alias-type-1",
            document_type=invoice_type,
        )
        _index(
            backend,
            title="Second",
            content="invoice mentioned in body",
            checksum="alias-type-2",
        )
        assert _matched_ids(backend, "type:invoice") == {typed.pk}
        assert _matched_ids(backend, "document_type:invoice") == {typed.pk}

    def test_path_alias_and_canonical_name_match_the_same_document(
        self,
        backend: TantivyBackend,
    ) -> None:
        archive = StoragePath.objects.create(name="archive", path="archive/{title}")
        stored = _index(
            backend,
            title="Stored",
            content="quarterly statement",
            checksum="alias-path-1",
            storage_path=archive,
        )
        # storage_path is NOT a default search field today, so a demoted
        # "path:archive" already matches nothing; the content decoy keeps
        # this test discriminating even if it ever joins the defaults.
        _index(
            backend,
            title="Loose",
            content="archive mentioned in body",
            checksum="alias-path-2",
        )
        assert _matched_ids(backend, "path:archive") == {stored.pk}
        assert _matched_ids(backend, "storage_path:archive") == {stored.pk}
