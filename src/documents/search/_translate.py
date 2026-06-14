from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import regex

# Fields that store exact, non-analyzed comma-joined tokens in the index and so
# need explicit comma->AND expansion (Whoosh KEYWORD(commas=True) set).
MULTI_VALUE_FIELDS = frozenset({"tag", "tag_id", "viewer_id"})

# Date fields whose values/ranges get rewritten to RFC3339 Tantivy ranges.
DATE_FIELDS = frozenset({"created", "modified", "added"})

# Known schema fields: a comma immediately followed by ``<known>:`` is a clause
# separator. Restricting to known fields prevents URL-like ``http:`` misfires.
KNOWN_FIELDS = frozenset(
    {
        "title",
        "content",
        "correspondent",
        "document_type",
        "type",
        "storage_path",
        "tag",
        "tag_id",
        "correspondent_id",
        "document_type_id",
        "storage_path_id",
        "owner_id",
        "viewer_id",
        "asn",
        "page_count",
        "num_notes",
        "created",
        "modified",
        "added",
        "original_filename",
        "checksum",
        "notes",
        "custom_fields",
    },
)

_FIELD_RE = regex.compile(r"(?P<field>\w+):")

# Matches the TO separator inside a range bracket. Handles three forms:
#   middle:   "lo TO hi"   (either lo or hi may be empty)
#   trailing: "lo TO"      (open upper bound)
#   leading:  "TO hi"      (open lower bound)
_RANGE_RE = regex.compile(
    r"^\s*(?P<lo>[^\s]*?)\s+[Tt][Oo]\s+(?P<hi>[^\s]*?)\s*$"
    r"|"
    r"^\s*(?P<lo2>[^\s]+)\s+[Tt][Oo]\s*$"
    r"|"
    r"^\s*[Tt][Oo]\s+(?P<hi2>[^\s]+)\s*$",
)


@dataclass(frozen=True, slots=True)
class FieldValue:
    field: str
    value: str


@dataclass(frozen=True, slots=True)
class FieldValueList:
    field: str
    values: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FieldRange:
    field: str
    open: str
    lo: str
    hi: str
    close: str


@dataclass(frozen=True, slots=True)
class Comma:
    pass


@dataclass(frozen=True, slots=True)
class Passthrough:
    raw: str


Token: TypeAlias = FieldValue | FieldValueList | FieldRange | Comma | Passthrough

_CLOSE: dict[str, str] = {"[": "]", "{": "}"}


def scan(query: str) -> list[Token]:
    """
    Tokenize a raw query into date/comma-aware tokens, leaving everything else
    as verbatim ``Passthrough`` runs. Depth-aware over ``[]``/``{}`` and quotes.
    """
    tokens: list[Token] = []
    buf: list[str] = []  # accumulates passthrough chars
    i, n = 0, len(query)

    def flush() -> None:
        if buf:
            tokens.append(Passthrough("".join(buf)))
            buf.clear()

    while i < n:
        ch = query[i]
        # A field token can begin only at a word boundary outside any value.
        m = _FIELD_RE.match(query, i)
        if m and (i == 0 or (not query[i - 1].isalnum() and query[i - 1] != "_")):
            field = m.group("field")
            j = m.end()
            if j < n and query[j] in "[{":
                rng = _consume_range(query, j, field)
                if rng is not None:
                    token, i = rng
                    flush()
                    tokens.append(token)
                    continue
            else:
                val = _consume_value(query, j)
                if val is not None:
                    value, i = val
                    flush()
                    tokens.append(FieldValue(field, value))
                    continue
        buf.append(ch)
        i += 1

    flush()
    return tokens


def _consume_range(
    query: str,
    start: int,
    field: str,
) -> tuple[FieldRange, int] | None:
    """Consume ``[lo TO hi]`` / ``{lo TO hi}`` from ``start`` (the bracket)."""
    open_br = query[start]
    close_br = _CLOSE[open_br]
    end = query.find(close_br, start + 1)
    if end == -1:
        return None
    inner = query[start + 1 : end]
    m = _RANGE_RE.match(inner)
    if m is not None:
        if m.group("lo") is not None or m.group("hi") is not None:
            # Middle form: "lo TO hi" (either may be empty string)
            lo = (m.group("lo") or "").strip()
            hi = (m.group("hi") or "").strip()
        elif m.group("lo2") is not None:
            # Trailing form: "lo TO"
            lo = m.group("lo2").strip()
            hi = ""
        else:
            # Leading form: "TO hi"
            lo = ""
            hi = (m.group("hi2") or "").strip()
    else:
        lo, hi = inner.strip(), ""
    return FieldRange(field, open_br, lo, hi, close_br), end + 1


def _consume_value(query: str, start: int) -> tuple[str, int] | None:
    """Consume a bare or quoted field value from ``start``."""
    n = len(query)
    if start >= n or query[start] in " \t":
        return None
    if query[start] in "\"'":
        quote = query[start]
        end = query.find(quote, start + 1)
        if end == -1:
            return None
        return query[start : end + 1], end + 1
    j = start
    while j < n and query[j] not in " \t)":
        j += 1
    return query[start:j], j
