"""Bare notes:/custom_fields: prefix resolution.

"notes:foo"/"custom_fields:foo" were valid fielded searches before the
whoosh-compat migration. The registry only exposes them as JSON subpaths, so
each JSON FieldSpec declares a default subpath (SubpathSpec(default=True)):
notes: resolves to notes.note:, custom_fields: resolves to
custom_fields.value:. This replaced an earlier regex-based rewrite
(_rewrite_bare_json_field_prefixes) that ran on the raw query string before
parsing and was blind to quoting, so a phrase like
content:"payment notes: none" was silently corrupted into a notes-field
search and matched nothing. Resolving the default subpath inside the parser
instead means quoting is already understood by the time it happens.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django.contrib.auth.models import User

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


def _matched_ids(backend: TantivyBackend, query: str) -> set[int]:
    return set(backend.search_ids(query, user=None))


def _index(backend: TantivyBackend, **kwargs: object) -> Document:
    doc = Document.objects.create(**kwargs)
    backend.add_or_update(doc)
    return doc


class TestBareJsonFieldPrefixes:
    def test_bare_notes_prefix_searches_note_text(
        self,
        backend: TantivyBackend,
    ) -> None:
        alice = User.objects.create_user(username="alice")
        with_note = Document.objects.create(
            title="Has note",
            content="x",
            checksum="bare-notes-with",
        )
        Note.objects.create(document=with_note, user=alice, note="crocodile")
        backend.add_or_update(with_note)
        # This document's CONTENT contains the words a demoted text search
        # would match; it must NOT match once the prefix addresses notes.
        _index(
            backend,
            title="Notes about things",
            content="notes crocodile mention",
            checksum="bare-notes-decoy",
        )
        assert _matched_ids(backend, "notes:crocodile") == {with_note.pk}

    def test_bare_custom_fields_prefix_searches_values(
        self,
        backend: TantivyBackend,
    ) -> None:
        field = CustomField.objects.create(
            name="Policy Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        with_value = Document.objects.create(
            title="Has field",
            content="x",
            checksum="bare-cf-with",
        )
        CustomFieldInstance.objects.create(
            document=with_value,
            field=field,
            value_text="crocodile",
        )
        backend.add_or_update(with_value)
        _index(
            backend,
            title="Custom things",
            content="custom fields crocodile",
            checksum="bare-cf-decoy",
        )
        assert _matched_ids(backend, "custom_fields:crocodile") == {with_value.pk}

    def test_subpath_spellings_are_untouched(
        self,
        backend: TantivyBackend,
    ) -> None:
        bob = User.objects.create_user(username="bob")
        doc = Document.objects.create(
            title="Bob note",
            content="x",
            checksum="bare-subpath",
        )
        Note.objects.create(document=doc, user=bob, note="remark")
        backend.add_or_update(doc)
        assert _matched_ids(backend, "notes.user:bob") == {doc.pk}
        assert _matched_ids(backend, "notes.note:remark") == {doc.pk}


class TestQuotedPhraseContainingNotesColonIsNotCorrupted:
    """The regex rewrite this migration removes was blind to quoting: it
    matched "notes:" anywhere in the raw query string, including inside an
    already-quoted phrase on an unrelated field, silently turning
    content:"payment notes: none" into a notes-field search that matched
    nothing. Resolving the default subpath during parsing (which is
    quote-aware) fixes this."""

    def test_quoted_phrase_with_notes_colon_matches_by_content(
        self,
        backend: TantivyBackend,
    ) -> None:
        target = _index(
            backend,
            title="Statement",
            content="payment notes: none",
            checksum="quoted-phrase-notes-colon",
        )
        assert _matched_ids(
            backend,
            'content:"payment notes: none"',
        ) == {target.pk}

    def test_quoted_phrase_matches_the_same_document_unquoted(
        self,
        backend: TantivyBackend,
    ) -> None:
        # Same document, phrasing without the colon: this proves the fix is
        # about quote-awareness, not about the words themselves being
        # unsearchable.
        target = _index(
            backend,
            title="Statement",
            content="payment notes none",
            checksum="quoted-phrase-no-colon",
        )
        assert _matched_ids(
            backend,
            'content:"payment notes none"',
        ) == {target.pk}
