"""Every declared JSON subpath must actually be written to the index.

PUBLIC_FIELDS declares each JSON field's subpaths (e.g. ``notes`` ->
{"user", "note"}), but nothing coupled that declaration to what
``_backend.py``'s document builder actually writes into the JSON blob at
index time. A subpath declared but never written would be
queryable-but-always-empty -- syntactically valid, silently matching
nothing -- with no test failure anywhere.

This indexes one real document carrying values for every JSON field
(a Note, a CustomFieldInstance) and inspects the document's own stored
JSON payload, rather than running field-specific queries: that way a
future JSON field's subpaths are covered automatically, without a new
per-subpath query having to be added by hand each time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tantivy
from django.contrib.auth.models import User
from whoosh_compat import FieldKind

from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.search._fields import PUBLIC_FIELDS

if TYPE_CHECKING:
    from documents.search._backend import TantivyBackend

pytestmark = [pytest.mark.search, pytest.mark.django_db]


class TestJsonSubpathsAreWrittenAtIndexTime:
    def test_every_declared_json_subpath_appears_in_the_stored_document(
        self,
        backend: TantivyBackend,
    ) -> None:
        user = User.objects.create_user(username="completeness-user")
        field = CustomField.objects.create(
            name="Completeness Field",
            data_type=CustomField.FieldDataType.STRING,
        )
        doc = Document.objects.create(
            title="Completeness doc",
            content="x",
            checksum="json-subpath-completeness",
        )
        Note.objects.create(document=doc, user=user, note="a note")
        CustomFieldInstance.objects.create(
            document=doc,
            field=field,
            value_text="a value",
        )
        backend.add_or_update(doc)

        index = backend._index
        searcher = index.searcher()
        hits = searcher.search(
            tantivy.Query.term_query(index.schema, "id", doc.pk),
            limit=1,
        ).hits
        assert hits, "the document was not indexed"
        stored = searcher.doc(hits[0][1]).to_dict()

        json_fields = [f for f in PUBLIC_FIELDS if f.kind is FieldKind.JSON]
        assert json_fields, "no JSON fields declared - fixture is stale"
        for field_spec in json_fields:
            stored_values = stored.get(field_spec.name)
            assert stored_values, (
                f"{field_spec.name} was not written to the index at all"
            )
            written_keys = stored_values[0].keys()
            for subpath in field_spec.subpaths:
                assert subpath in written_keys, (
                    f"{field_spec.name}.{subpath} is declared in PUBLIC_FIELDS "
                    "but _backend.py's document builder never writes it - it "
                    "would be queryable but always empty"
                )
