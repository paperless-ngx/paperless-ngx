from __future__ import annotations

from whoosh_compat import FieldKind
from whoosh_compat import FieldSpec
from whoosh_compat import SubpathSpec

# Internal-only schema fields with no query-syntax meaning of their own
# (sort shadow fields, bigram CJK fields, simple_title/simple_content,
# autocomplete_word, notes_text) are NOT represented here — they are
# declared in _schema.py's field_descriptors().
#
# analyzer/pattern_normalizer are deliberately left at FieldSpec's default
# (None): they're language-specific and only meaningful to whoosh-compat's
# parser, so _registry.py attaches them per-language via dataclasses.replace()
# rather than PUBLIC_FIELDS declaring them itself. _schema.py only reads
# name/kind/fast and never sees the analyzer at all.
PUBLIC_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("title", FieldKind.TEXT),
    FieldSpec("content", FieldKind.TEXT),
    FieldSpec("correspondent", FieldKind.TEXT),
    FieldSpec("document_type", FieldKind.TEXT, aliases=("type",)),
    FieldSpec("storage_path", FieldKind.TEXT, aliases=("path",)),
    FieldSpec("original_filename", FieldKind.TEXT),
    FieldSpec("tag", FieldKind.TEXT, comma_values=True),
    FieldSpec("checksum", FieldKind.KEYWORD),
    FieldSpec("asn", FieldKind.U64, fast=True),
    FieldSpec("page_count", FieldKind.U64, fast=True),
    FieldSpec("num_notes", FieldKind.U64, fast=True),
    FieldSpec("created", FieldKind.DATE, date_only=True, fast=True),
    FieldSpec("modified", FieldKind.DATETIME, fast=True),
    FieldSpec("added", FieldKind.DATETIME, fast=True),
    FieldSpec(
        "notes",
        FieldKind.JSON,
        subpaths={"user": SubpathSpec(), "note": SubpathSpec(default=True)},
    ),
    FieldSpec(
        "custom_fields",
        FieldKind.JSON,
        subpaths={"name": SubpathSpec(), "value": SubpathSpec(default=True)},
    ),
)
