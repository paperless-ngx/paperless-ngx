"""SCHEMA_VERSION must change whenever build_schema()'s field list or order does.

tantivy compares schemas by *ordered* field list. ``Index.open()`` loads the
schema from the index's own ``meta.json``, so reads against an index built by an
older release keep working after a field reorder. Writes do not:
``WriteBatch.__enter__`` calls ``tantivy.Index(build_schema(), path=...)``, an
open-or-create that raises ``ValueError`` on any schema difference. Nothing
catches that ValueError, so consumption, index_document and bulk edit all
hard-fail while ``/api/status/`` still reports the index healthy.

The only thing that saves such an install is ``needs_rebuild()`` noticing the
version stamped in ``.index_settings.json`` is stale.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
import tantivy
from django.conf import settings as django_settings

from documents.search._schema import build_schema
from documents.search._schema import needs_rebuild
from documents.search._schema import open_or_rebuild_index

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.search]

RELEASED_V1_SCHEMA_VERSION = 1


def _build_released_v1_schema() -> tantivy.Schema:
    """Frozen copy of build_schema() as shipped in v3.0.x (schema version 1).

    Deliberately duplicated rather than imported: it must keep describing the
    on-disk layout of already-deployed indexes even as build_schema() evolves.
    """
    sb = tantivy.SchemaBuilder()

    sb.add_unsigned_field("id", stored=True, indexed=True, fast=True)
    sb.add_text_field("checksum", stored=True, tokenizer_name="raw")

    for field in (
        "title",
        "correspondent",
        "document_type",
        "storage_path",
        "original_filename",
        "content",
    ):
        sb.add_text_field(field, stored=True, tokenizer_name="paperless_text")

    for field in ("title_sort", "correspondent_sort", "type_sort"):
        sb.add_text_field(
            field,
            stored=False,
            tokenizer_name="simple_analyzer",
            fast=True,
        )

    for field in (
        "bigram_content",
        "bigram_title",
        "bigram_correspondent",
        "bigram_document_type",
        "bigram_tag",
    ):
        sb.add_text_field(field, stored=False, tokenizer_name="bigram_analyzer")

    for field in ("simple_title", "simple_content"):
        sb.add_text_field(field, stored=False, tokenizer_name="simple_search_analyzer")

    sb.add_text_field("autocomplete_word", stored=False, tokenizer_name="raw")
    sb.add_text_field("tag", stored=True, tokenizer_name="paperless_text")

    sb.add_json_field("notes", stored=True, tokenizer_name="paperless_text")
    sb.add_text_field("notes_text", stored=True, tokenizer_name="paperless_text")
    sb.add_json_field("custom_fields", stored=True, tokenizer_name="paperless_text")

    for field in (
        "correspondent_id",
        "document_type_id",
        "storage_path_id",
        "tag_id",
        "owner_id",
        "viewer_id",
        "viewer_group_id",
    ):
        sb.add_unsigned_field(field, stored=False, indexed=True, fast=True)

    for field in ("created", "modified", "added"):
        sb.add_date_field(field, stored=True, indexed=True, fast=True)

    for field in ("asn", "page_count", "num_notes"):
        sb.add_unsigned_field(field, stored=True, indexed=True, fast=True)

    return sb.build()


@pytest.fixture
def released_v1_index(tmp_path: Path) -> Path:
    """An index directory as a v3.0.x install would leave it on disk."""
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    tantivy.Index(_build_released_v1_schema(), path=str(index_dir))
    (index_dir / ".index_settings.json").write_text(
        json.dumps(
            {
                "schema_version": RELEASED_V1_SCHEMA_VERSION,
                "language": django_settings.SEARCH_LANGUAGE,
            },
        ),
    )
    return index_dir


class TestUpgradeFromReleasedV1Index:
    def test_released_v1_index_is_flagged_for_rebuild(
        self,
        released_v1_index: Path,
    ) -> None:
        """The current schema differs from v1's, so the sentinel must be stale.

        If this fails, `document_index reindex --if-needed` prints "Search index
        is up to date" and skips, leaving the mismatched index in place.
        """
        assert needs_rebuild(released_v1_index) is True

    def test_v1_index_rejects_writes_against_the_current_schema(
        self,
        released_v1_index: Path,
    ) -> None:
        """The failure mode the version bump exists to prevent.

        This is exactly what WriteBatch.__enter__ does on every index write.
        """
        with pytest.raises(ValueError, match="schema does not match"):
            tantivy.Index(build_schema(), path=str(released_v1_index))

    def test_opening_a_v1_index_leaves_it_writable(
        self,
        released_v1_index: Path,
    ) -> None:
        """End to end: open_or_rebuild_index must hand back an index that the
        write path can reopen. Before the version bump, needs_rebuild() returned
        False here, the stale directory survived untouched, and every subsequent
        write raised the ValueError above."""
        open_or_rebuild_index(released_v1_index)

        tantivy.Index(build_schema(), path=str(released_v1_index))

    def test_rebuilt_index_is_not_rebuilt_again(
        self,
        released_v1_index: Path,
    ) -> None:
        """The rebuild must stamp the version it actually wrote, otherwise every
        startup wipes and reindexes the whole corpus."""
        open_or_rebuild_index(released_v1_index)

        assert needs_rebuild(released_v1_index) is False
