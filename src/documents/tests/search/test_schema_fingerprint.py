"""The schema fingerprint stamped into .index_settings.json.

tantivy compares schemas by *ordered* field list, and `tantivy.Index(schema,
path=...)` (what every write path does) raises on any difference. SCHEMA_VERSION
is the manual guard against that, but build_schema() is edited for *parser*
reasons - adding an alias, flipping fast=True, adding a subpath - by people not
thinking about the on-disk index, and forgetting the bump is exactly how this
branch's bug happened.

The fingerprint is the automatic guard: it hashes the field descriptor list that
build_schema() itself iterates, so any change to a field's name, kind, options
or *position* forces a rebuild on its own.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

import pytest
import tantivy

from documents.search import _schema
from documents.search._schema import SCHEMA_VERSION
from documents.search._schema import FieldDescriptor
from documents.search._schema import _write_sentinels
from documents.search._schema import build_schema
from documents.search._schema import field_descriptors
from documents.search._schema import needs_rebuild
from documents.search._schema import schema_fingerprint

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_django.fixtures import SettingsWrapper

pytestmark = pytest.mark.search

# The on-disk field layout of a v2 index, pinned as data. Any edit here is an
# index-format change: it must come with a rebuild, which the fingerprint now
# forces automatically. Reproduced from build_schema()'s output as it stood
# before the descriptor refactor, so it also pins that the refactor changed
# nothing.
PINNED_DESCRIPTORS: tuple[FieldDescriptor, ...] = (
    FieldDescriptor("id", "u64", stored=True, indexed=True, fast=True, tokenizer=None),
    FieldDescriptor(
        "title",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "content",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "correspondent",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "document_type",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "storage_path",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "original_filename",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "tag",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "checksum",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="raw",
    ),
    FieldDescriptor("asn", "u64", stored=True, indexed=True, fast=True, tokenizer=None),
    FieldDescriptor(
        "page_count",
        "u64",
        stored=True,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "num_notes",
        "u64",
        stored=True,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "created",
        "date",
        stored=True,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "modified",
        "date",
        stored=True,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "added",
        "date",
        stored=True,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "notes",
        "json",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "notes_text",
        "text",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "custom_fields",
        "json",
        stored=True,
        indexed=True,
        fast=False,
        tokenizer="paperless_text",
    ),
    FieldDescriptor(
        "title_sort",
        "text",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer="simple_analyzer",
    ),
    FieldDescriptor(
        "correspondent_sort",
        "text",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer="simple_analyzer",
    ),
    FieldDescriptor(
        "type_sort",
        "text",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer="simple_analyzer",
    ),
    FieldDescriptor(
        "bigram_content",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="bigram_analyzer",
    ),
    FieldDescriptor(
        "bigram_title",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="bigram_analyzer",
    ),
    FieldDescriptor(
        "bigram_correspondent",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="bigram_analyzer",
    ),
    FieldDescriptor(
        "bigram_document_type",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="bigram_analyzer",
    ),
    FieldDescriptor(
        "bigram_tag",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="bigram_analyzer",
    ),
    FieldDescriptor(
        "simple_title",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="simple_search_analyzer",
    ),
    FieldDescriptor(
        "simple_content",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="simple_search_analyzer",
    ),
    FieldDescriptor(
        "autocomplete_word",
        "text",
        stored=False,
        indexed=True,
        fast=False,
        tokenizer="raw",
    ),
    FieldDescriptor(
        "owner_id",
        "u64",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "viewer_id",
        "u64",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
    FieldDescriptor(
        "viewer_group_id",
        "u64",
        stored=False,
        indexed=True,
        fast=True,
        tokenizer=None,
    ),
)


def _schema_fields(schema: tantivy.Schema) -> list[dict]:
    """The tantivy-level field list, in declaration order.

    tantivy-py 0.26 exposes no public introspection API on Schema, so
    __reduce__() (its pickling hook) is the only way to recover the field list.
    It is used here, in a test, precisely because it is the representation the
    persisted fingerprint must NOT depend on.
    """
    return schema.__reduce__()[1][0]["inner"]


def _sentinels(index_dir: Path, **overrides: object) -> None:
    data = {
        "schema_version": SCHEMA_VERSION,
        "language": None,
        "schema_fingerprint": schema_fingerprint(),
    }
    data.update(overrides)
    (index_dir / ".index_settings.json").write_text(json.dumps(data))


class TestDescriptorsDescribeTheBuiltSchema:
    def test_descriptors_match_the_pinned_field_layout(self) -> None:
        assert tuple(field_descriptors()) == PINNED_DESCRIPTORS

    def test_built_schema_matches_the_descriptors(self) -> None:
        """The descriptors are not a parallel description - they are the input.

        Reading the built schema back proves the loop honours every option, so
        a descriptor edit cannot claim a shape the SchemaBuilder did not build.
        """
        kinds = {"text": "text", "json": "json_object", "u64": "u64", "date": "date"}
        built = [
            (
                field["name"],
                field["type"],
                field["options"]["stored"],
                bool(field["options"].get("fast")),
                (field["options"].get("indexing") or {}).get("tokenizer"),
            )
            for field in _schema_fields(build_schema())
        ]
        expected = [
            (
                descriptor.name,
                kinds[descriptor.kind],
                descriptor.stored,
                descriptor.fast,
                descriptor.tokenizer,
            )
            for descriptor in field_descriptors()
        ]
        assert built == expected


class TestFingerprintSensitivity:
    def test_a_field_option_change_moves_the_fingerprint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        before = schema_fingerprint()
        changed = field_descriptors()
        changed[1] = changed[1]._replace(fast=True)
        monkeypatch.setattr(_schema, "field_descriptors", lambda: changed)

        assert schema_fingerprint() != before

    def test_reordering_alone_moves_the_fingerprint(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The original bug: same fields, different declaration order.

        A set- or dict-based fingerprint would be blind to this, and tantivy
        would reject every write against the existing index.
        """
        before = schema_fingerprint()
        swapped = field_descriptors()
        swapped[1], swapped[2] = swapped[2], swapped[1]
        monkeypatch.setattr(_schema, "field_descriptors", lambda: swapped)

        assert schema_fingerprint() != before

    def test_repeated_calls_agree(self) -> None:
        assert schema_fingerprint() == schema_fingerprint()


class TestFingerprintIsIndependentOfTantivy:
    def test_a_tantivy_option_key_addition_would_not_move_it(self) -> None:
        """A tantivy-py upgrade must not force a global reindex.

        Hashing schema.__reduce__() would do exactly that: the simulated new
        option key below changes that payload for every user with no schema
        change at all.
        """
        fields = _schema_fields(build_schema())
        upgraded = [
            {**field, "options": {**field["options"], "coerce": True}}
            for field in fields
        ]
        assert _hash(upgraded) != _hash(fields)
        assert schema_fingerprint() == _fingerprint_of(field_descriptors())

    def test_fingerprint_never_touches_the_schema_builder(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        before = schema_fingerprint()

        class _RemovedSchemaBuilder:
            def __init__(self) -> None:
                raise AssertionError("tantivy.SchemaBuilder was consulted")

        monkeypatch.setattr(tantivy, "SchemaBuilder", _RemovedSchemaBuilder)
        with pytest.raises(AssertionError):
            build_schema()

        assert schema_fingerprint() == before


def _hash(payload: object) -> str:
    return hashlib.blake2b(json.dumps(payload).encode()).hexdigest()


def _fingerprint_of(descriptors: list[FieldDescriptor]) -> str:
    return _hash([list(descriptor) for descriptor in descriptors])


class TestNeedsRebuildOnFingerprint:
    def test_matching_fingerprint_does_not_rebuild(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        _sentinels(index_dir)

        assert needs_rebuild(index_dir) is False

    def test_stale_fingerprint_rebuilds_despite_a_matching_version(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The failure this task exists to prevent: schema edited, version not
        bumped. Without the fingerprint check, `reindex --if-needed` reports the
        index up to date and every write then raises."""
        settings.SEARCH_LANGUAGE = None
        _sentinels(index_dir)
        extended = [
            *field_descriptors(),
            FieldDescriptor(
                "new_field",
                "u64",
                stored=False,
                indexed=True,
                fast=True,
                tokenizer=None,
            ),
        ]
        monkeypatch.setattr(_schema, "field_descriptors", lambda: extended)

        assert needs_rebuild(index_dir) is True

    def test_reordered_schema_rebuilds(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        settings.SEARCH_LANGUAGE = None
        _sentinels(index_dir)
        reordered = field_descriptors()
        reordered[1], reordered[2] = reordered[2], reordered[1]
        monkeypatch.setattr(_schema, "field_descriptors", lambda: reordered)

        assert needs_rebuild(index_dir) is True

    def test_missing_fingerprint_rebuilds(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        """No seeding: an index whose schema shape nobody recorded is rebuilt
        rather than trusted."""
        settings.SEARCH_LANGUAGE = None
        (index_dir / ".index_settings.json").write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, "language": None}),
        )

        assert needs_rebuild(index_dir) is True

    def test_written_sentinels_satisfy_the_check(
        self,
        index_dir: Path,
        settings: SettingsWrapper,
    ) -> None:
        settings.SEARCH_LANGUAGE = "en"
        _write_sentinels(index_dir)

        assert needs_rebuild(index_dir) is False
