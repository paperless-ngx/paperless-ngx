from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from documents.search._fields import PUBLIC_FIELDS
from documents.search._schema import SCHEMA_VERSION
from documents.search._schema import build_schema
from documents.search._schema import field_descriptors
from documents.search._schema import needs_rebuild
from documents.search._schema import schema_fingerprint

if TYPE_CHECKING:
    from pathlib import Path

    import tantivy
    from pytest_django.fixtures import Settings


pytestmark = pytest.mark.search


class TestNeedsRebuild:
    """needs_rebuild covers all sentinel-file states that require a full reindex."""

    def test_returns_true_when_settings_file_missing(self, index_dir: Path) -> None:
        assert needs_rebuild(index_dir) is True

    def test_returns_false_when_version_and_language_match(
        self,
        index_dir: Path,
        settings: Settings,
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
        settings: Settings,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION - 1, "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_version_is_not_an_integer(
        self,
        index_dir: Path,
        settings: Settings,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": "not-a-number", "language": None}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_key_missing(
        self,
        index_dir: Path,
        settings: Settings,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION}),
        )
        assert needs_rebuild(index_dir) is True

    def test_returns_true_when_language_differs(
        self,
        index_dir: Path,
        settings: Settings,
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
        """
        GIVEN:
            - PUBLIC_FIELDS and the tantivy schema built by build_schema()
        WHEN:
            - Every field declared in PUBLIC_FIELDS is checked against the
              schema
        THEN:
            - Each one is present as a field in the built schema
        """
        schema = build_schema()
        schema_field_names = set(_schema_fields(schema))
        for field in PUBLIC_FIELDS:
            assert field.name in schema_field_names, (
                f"{field.name} is in PUBLIC_FIELDS but missing from build_schema()"
            )


class TestFastFlagAgreement:
    def test_every_public_field_fast_flag_matches_the_built_schema(self) -> None:
        """
        GIVEN:
            - PUBLIC_FIELDS and field_descriptors() (the latter is exactly
              the input build_schema()'s SchemaBuilder consumes for the
              `fast` kwarg on every field kind, so it pins the agreement
              without depending on a private tantivy-py pickled
              representation)
        WHEN:
            - Every PUBLIC_FIELDS entry's fast flag is compared against
              field_descriptors()' fast flag for the same field
        THEN:
            - They agree for every field, catching a fast=True
              PUBLIC_FIELDS entry the builder silently ignores here
              instead of at a user's field:* existence query, which
              whoosh-compat's registry trusts PUBLIC_FIELDS' fast flag to
              resolve
        """
        descriptor_fast = {d.name: d.fast for d in field_descriptors()}
        for public_field in PUBLIC_FIELDS:
            assert descriptor_fast[public_field.name] == public_field.fast, (
                f"{public_field.name}: PUBLIC_FIELDS says fast={public_field.fast} but"
                f" field_descriptors() says fast={descriptor_fast[public_field.name]}"
            )
