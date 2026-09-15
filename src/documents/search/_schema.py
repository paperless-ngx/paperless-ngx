from __future__ import annotations

import hashlib
import json
import logging
import shutil
from typing import TYPE_CHECKING
from typing import Final
from typing import NamedTuple
from typing import cast

import tantivy
from django.conf import settings
from whoosh_compat import FieldKind

from documents.search._fields import PUBLIC_FIELDS

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("paperless.search")

# v1 - Initial tantivy schema format
# v2 - build_schema() derived from PUBLIC_FIELDS, changing the field declaration
#      order, and the write-only correspondent/document_type/storage_path/tag id
#      columns dropped. tantivy compares schemas by ordered field list, so an
#      index built by v1 rejects every write against the v2 schema.
SCHEMA_VERSION: Final[int] = 2


class FieldDescriptor(NamedTuple):
    """One tantivy field, in declaration order.

    The descriptor vocabulary is paperless', not tantivy-py's: it is both the
    input to the SchemaBuilder and the input to schema_fingerprint(), so the
    persisted fingerprint cannot move under a tantivy-py upgrade.
    """

    name: str
    kind: str
    stored: bool
    indexed: bool
    fast: bool
    tokenizer: str | None


# (schema kind, tokenizer) for the FieldKind -> FieldDescriptor mapping that
# doesn't need special-casing. JSON is handled separately below since it can
# emit a second, synthetic descriptor.
_KIND_TABLE: Final[dict[FieldKind, tuple[str, str | None]]] = {
    FieldKind.TEXT: ("text", "paperless_text"),
    FieldKind.KEYWORD: ("text", "raw"),
    FieldKind.U64: ("u64", None),
    FieldKind.DATE: ("date", None),
    FieldKind.DATETIME: ("date", None),
}
# Kinds whose fast-field flag follows FieldSpec.fast rather than always False.
_FAST_FROM_FIELD: Final[frozenset[FieldKind]] = frozenset(
    {FieldKind.U64, FieldKind.DATE, FieldKind.DATETIME},
)


def _public_field_descriptors() -> list[FieldDescriptor]:
    """Descriptors for the query-visible fields declared in PUBLIC_FIELDS."""
    descriptors: list[FieldDescriptor] = []
    for field in PUBLIC_FIELDS:
        if field.kind is FieldKind.JSON:
            descriptors.append(
                FieldDescriptor(
                    field.name,
                    "json",
                    stored=True,
                    indexed=True,
                    fast=False,
                    tokenizer="paperless_text",
                ),
            )
            if field.name == "notes":
                # Plain-text companion for snippet generation: tantivy's
                # SnippetGenerator does not support JSON fields. Schema-only,
                # no query-syntax meaning, not in PUBLIC_FIELDS.
                descriptors.append(
                    FieldDescriptor(
                        "notes_text",
                        "text",
                        stored=True,
                        indexed=True,
                        fast=False,
                        tokenizer="paperless_text",
                    ),
                )
            continue
        schema_kind, tokenizer = _KIND_TABLE[field.kind]
        descriptors.append(
            FieldDescriptor(
                field.name,
                schema_kind,
                stored=True,
                indexed=True,
                fast=field.fast if field.kind in _FAST_FROM_FIELD else False,
                tokenizer=tokenizer,
            ),
        )
    return descriptors


def field_descriptors() -> list[FieldDescriptor]:
    """Every field of the document index, in the order tantivy declares them.

    tantivy compares schemas by *ordered* field list, so the order here is
    part of the on-disk contract: schema_fingerprint() hashes it and
    needs_rebuild() acts on the result.
    """
    return [
        FieldDescriptor(
            "id",
            "u64",
            stored=True,
            indexed=True,
            fast=True,
            tokenizer=None,
        ),
        *_public_field_descriptors(),
        # Shadow sort fields - fast, not stored
        *(
            FieldDescriptor(
                name,
                "text",
                stored=False,
                indexed=True,
                fast=True,
                tokenizer="simple_analyzer",
            )
            for name in ("title_sort", "correspondent_sort", "type_sort")
        ),
        # CJK support - not stored, indexed only
        *(
            FieldDescriptor(
                name,
                "text",
                stored=False,
                indexed=True,
                fast=False,
                tokenizer="bigram_analyzer",
            )
            for name in (
                "bigram_content",
                "bigram_title",
                "bigram_correspondent",
                "bigram_document_type",
                "bigram_tag",
            )
        ),
        # Simple substring search support for title/content - not stored,
        # indexed only
        *(
            FieldDescriptor(
                name,
                "text",
                stored=False,
                indexed=True,
                fast=False,
                tokenizer="simple_search_analyzer",
            )
            for name in ("simple_title", "simple_content")
        ),
        # Autocomplete prefix scan via terms_with_prefix, which walks the
        # field's term dictionary - so the field must be indexed (term dict),
        # not stored. The stored value is never read back, so storing it only
        # wastes space.
        FieldDescriptor(
            "autocomplete_word",
            "text",
            stored=False,
            indexed=True,
            fast=False,
            tokenizer="raw",
        ),
        # Permission filter columns, read by build_permission_filter.
        *(
            FieldDescriptor(
                name,
                "u64",
                stored=False,
                indexed=True,
                fast=True,
                tokenizer=None,
            )
            for name in ("owner_id", "viewer_id", "viewer_group_id")
        ),
    ]


def schema_fingerprint() -> str:
    """Hash of the field descriptors, stamped into .index_settings.json.

    Changes whenever a field is added, removed, retyped, re-optioned or
    reordered, so an index built from a different schema shape is detected
    even when SCHEMA_VERSION was not bumped.
    """
    payload = json.dumps([list(descriptor) for descriptor in field_descriptors()])
    return hashlib.blake2b(payload.encode()).hexdigest()


def build_schema() -> tantivy.Schema:
    """
    Build the Tantivy schema for the paperless document index.

    Creates a comprehensive schema supporting full-text search, filtering,
    sorting, and autocomplete functionality. Includes fields for document
    content, metadata, permissions, custom fields, and notes.

    Returns:
        Configured Tantivy schema ready for index creation
    """
    sb = tantivy.SchemaBuilder()

    for descriptor in field_descriptors():
        if descriptor.kind == "text":
            sb.add_text_field(
                descriptor.name,
                stored=descriptor.stored,
                fast=descriptor.fast,
                tokenizer_name=cast("str", descriptor.tokenizer),
            )
        elif descriptor.kind == "json":
            sb.add_json_field(
                descriptor.name,
                stored=descriptor.stored,
                fast=descriptor.fast,
                tokenizer_name=cast("str", descriptor.tokenizer),
            )
        elif descriptor.kind == "u64":
            sb.add_unsigned_field(
                descriptor.name,
                stored=descriptor.stored,
                indexed=descriptor.indexed,
                fast=descriptor.fast,
            )
        elif descriptor.kind == "date":
            sb.add_date_field(
                descriptor.name,
                stored=descriptor.stored,
                indexed=descriptor.indexed,
                fast=descriptor.fast,
            )
        else:
            raise ValueError(f"Unknown schema field kind: {descriptor.kind}")

    return sb.build()


def needs_rebuild(index_dir: Path) -> bool:
    """
    Check if the search index needs rebuilding.

    Reads .index_settings.json to compare the stored schema version, search
    language and schema fingerprint against the current configuration. Returns
    True if the file is missing, unparsable, or any value mismatches.

    Args:
        index_dir: Path to the search index directory

    Returns:
        True if the index needs rebuilding, False if it's up to date
    """
    settings_file = index_dir / ".index_settings.json"
    if not settings_file.exists():
        return True
    try:
        data = json.loads(settings_file.read_text())
        if data.get("schema_version") != SCHEMA_VERSION:
            logger.info("Search index schema version mismatch - rebuilding.")
            return True
        if "language" not in data or data["language"] != settings.SEARCH_LANGUAGE:
            logger.info("Search index language changed - rebuilding.")
            return True
        if data.get("schema_fingerprint") != schema_fingerprint():
            logger.info("Search index schema fingerprint mismatch - rebuilding.")
            return True
    except ValueError:
        return True
    return False


def wipe_index(index_dir: Path) -> None:
    """
    Delete all contents of the index directory to prepare for rebuild.

    Recursively removes all files and subdirectories within the index
    directory while preserving the directory itself.

    Args:
        index_dir: Path to the search index directory to clear
    """
    for child in index_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _write_sentinels(index_dir: Path) -> None:
    """Write .index_settings.json so the next index open can skip rebuilding."""
    settings_file = index_dir / ".index_settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "language": settings.SEARCH_LANGUAGE,
                "schema_fingerprint": schema_fingerprint(),
            },
        ),
    )


def open_or_rebuild_index(index_dir: Path | None = None) -> tantivy.Index:
    """
    Open the Tantivy index, creating or rebuilding as needed.

    Checks if the index needs rebuilding due to schema version or language
    changes. If rebuilding is needed, wipes the directory and creates a fresh
    index with the current schema and configuration.

    Args:
        index_dir: Path to index directory (defaults to settings.INDEX_DIR)

    Returns:
        Opened Tantivy index (caller must register custom tokenizers)
    """
    if index_dir is None:
        index_dir = cast("Path", settings.INDEX_DIR)
    if not index_dir.exists():
        return tantivy.Index(build_schema())
    if needs_rebuild(index_dir):
        wipe_index(index_dir)
        idx = tantivy.Index(build_schema(), path=str(index_dir))
        _write_sentinels(index_dir)
        return idx
    return tantivy.Index.open(str(index_dir))
