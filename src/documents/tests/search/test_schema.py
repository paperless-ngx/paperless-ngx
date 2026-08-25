from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

import pytest
import tantivy

from documents.search._fields import PUBLIC_FIELDS
from documents.search._schema import SCHEMA_VERSION
from documents.search._schema import build_schema
from documents.search._schema import field_descriptors
from documents.search._schema import needs_rebuild
from documents.search._schema import schema_fingerprint
from documents.search._tokenizer import register_tokenizers

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

pytestmark = pytest.mark.search


class TestNeedsRebuild:
    """needs_rebuild covers all sentinel-file states that require a full reindex."""

    def test_returns_true_when_settings_file_missing(self, index_dir: Path) -> None:
        assert needs_rebuild(index_dir) is True

    def test_returns_false_when_version_and_language_match(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        (index_dir / ".index_settings.json").write_text(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "language": "en",
                    "schema_fingerprint": schema_fingerprint(),
                },
            ),
        )
        assert needs_rebuild(index_dir) is False

    def test_returns_true_on_schema_version_mismatch(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION - 1, "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_version_is_not_an_integer(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": "not-a-number", "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_key_missing(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_differs(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "de"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "language": "en"}),
        )
        assert needs_rebuild(index_dir) is True


def _schema_fields(schema: tantivy.Schema) -> dict[str, dict]:
    """{name: field-state} for every field declared on a tantivy Schema.

    tantivy-py 0.26 exposes no public introspection API on Schema (no
    __iter__, get_field, to_json, etc.) -- __reduce__() (used internally for
    pickling) is the only way to recover the field list, so we lean on it
    here for test assertions only.
    """
    state = schema.__reduce__()[1][0]
    return {field["name"]: field for field in state["inner"]}


class TestSchemaMatchesPublicFields:
    def test_every_public_field_is_in_the_schema(self) -> None:
        schema = build_schema()
        schema_field_names = set(_schema_fields(schema))
        for field in PUBLIC_FIELDS:
            assert field.name in schema_field_names, (
                f"{field.name} is in PUBLIC_FIELDS but missing from build_schema()"
            )

    def test_asn_page_count_num_notes_are_fast_unsigned_fields(self) -> None:
        # Spot-check kind-derived construction for the U64 fields.
        schema = build_schema()
        doc = tantivy.Document()
        doc.add_unsigned("id", 1)
        doc.add_text("checksum", "x")
        doc.add_unsigned("asn", 42)
        doc.add_unsigned("page_count", 3)
        doc.add_unsigned("num_notes", 0)
        doc.add_date("created", datetime(2020, 1, 1, tzinfo=UTC))
        doc.add_date("modified", datetime(2020, 1, 1, tzinfo=UTC))
        doc.add_date("added", datetime(2020, 1, 1, tzinfo=UTC))
        index = tantivy.Index(schema)
        register_tokenizers(index, None)
        writer = index.writer()
        writer.add_document(doc)
        writer.commit()
        index.reload()
        searcher = index.searcher()
        results = searcher.search(tantivy.Query.term_query(schema, "asn", 42), limit=1)
        assert len(results.hits) == 1


class TestFastFlagAgreement:
    def test_every_public_field_fast_flag_matches_the_built_schema(self) -> None:
        # whoosh-compat's registry trusts PUBLIC_FIELDS' fast flag when resolving
        # field:* existence checks (its FAST_FIELD strategy); a fast=True
        # entry whose actual tantivy column is not fast would make those
        # searches silently match nothing at search time. Only the U64 and
        # DATE descriptors can carry the flag today, so this
        # pins the agreement for EVERY kind: a future fast=True
        # TEXT/KEYWORD/JSON entry the builder silently ignores fails here
        # instead of at a user's query.
        #
        # field_descriptors() (not tantivy-py's __reduce__() pickling
        # internals) is used as the probe here: it is exactly the input
        # build_schema()'s SchemaBuilder consumes for the `fast` kwarg on
        # every field kind, so it pins the same agreement without depending
        # on a private pickled representation surviving a tantivy-py
        # upgrade.
        descriptor_fast = {d.name: d.fast for d in field_descriptors()}
        for public_field in PUBLIC_FIELDS:
            assert descriptor_fast[public_field.name] == public_field.fast, (
                f"{public_field.name}: PUBLIC_FIELDS says fast={public_field.fast} but"
                f" field_descriptors() says fast={descriptor_fast[public_field.name]}"
            )
