from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING

import tantivy
from django.conf import settings

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("paperless.search")

SCHEMA_VERSION = 1


def build_schema() -> tantivy.Schema:
    """Build the Tantivy schema for the paperless document index."""
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

    # Shadow sort fields - fast, not stored/indexed
    for field in ("title_sort", "correspondent_sort", "type_sort"):
        sb.add_text_field(
            field,
            stored=False,
            tokenizer_name="simple_analyzer",
            fast=True,
        )

    # CJK support - not stored, indexed only
    sb.add_text_field("bigram_content", stored=False, tokenizer_name="bigram_analyzer")

    # Autocomplete prefix scan - stored, not indexed
    sb.add_text_field("autocomplete_word", stored=True, tokenizer_name="raw")

    sb.add_text_field("tag", stored=True, tokenizer_name="paperless_text")

    # JSON fields — structured queries: notes.user:alice, custom_fields.name:invoice
    # tantivy-py 0.25 does not support dotted paths in parse_query default_field_names,
    # so companion text fields (note, custom_field) carry content for default full-text search.
    sb.add_json_field("notes", stored=True, tokenizer_name="paperless_text")
    sb.add_json_field("custom_fields", stored=True, tokenizer_name="paperless_text")

    # Companion text fields for default full-text search (not stored — no extra disk cost)
    sb.add_text_field("note", stored=False, tokenizer_name="paperless_text")
    sb.add_text_field("custom_field", stored=False, tokenizer_name="paperless_text")

    for field in (
        "correspondent_id",
        "document_type_id",
        "storage_path_id",
        "tag_id",
        "owner_id",
        "viewer_id",
    ):
        sb.add_unsigned_field(field, stored=False, indexed=True, fast=True)

    for field in ("created", "modified", "added"):
        sb.add_date_field(field, stored=True, indexed=True, fast=True)

    for field in ("asn", "page_count", "num_notes"):
        sb.add_unsigned_field(field, stored=True, indexed=True, fast=True)

    return sb.build()


def _needs_rebuild(index_dir: Path) -> bool:
    """Check if the search index needs rebuilding by comparing schema version and language sentinel files."""
    version_file = index_dir / ".schema_version"
    if not version_file.exists():
        return True
    try:
        if int(version_file.read_text().strip()) != SCHEMA_VERSION:
            logger.info("Search index schema version mismatch - rebuilding.")
            return True
    except ValueError:
        return True

    language_file = index_dir / ".schema_language"
    if not language_file.exists():
        logger.info("Search index language sentinel missing - rebuilding.")
        return True
    if language_file.read_text().strip() != settings.SEARCH_LANGUAGE:
        logger.info("Search index language changed - rebuilding.")
        return True

    return False


def wipe_index(index_dir: Path) -> None:
    """Delete all children in the index directory to prepare for rebuild."""
    for child in list(index_dir.iterdir()):
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_sentinels(index_dir: Path) -> None:
    """Write schema version and language sentinel files so the next index open can skip rebuilding."""
    (index_dir / ".schema_version").write_text(str(SCHEMA_VERSION))
    (index_dir / ".schema_language").write_text(settings.SEARCH_LANGUAGE)


def open_or_rebuild_index() -> tantivy.Index:
    """
    Open the Tantivy index at settings.INDEX_DIR, creating or rebuilding as needed.
    Caller must register custom tokenizers after receiving the Index.
    """
    index_dir: Path = settings.INDEX_DIR
    if _needs_rebuild(index_dir):
        wipe_index(index_dir)
        idx = tantivy.Index(build_schema(), path=str(index_dir))
        _write_sentinels(index_dir)
        return idx
    return tantivy.Index.open(str(index_dir))
