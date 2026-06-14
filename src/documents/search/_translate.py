from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import regex

# TODO: this module translates date queries into Tantivy *string* syntax, which
# forces two workarounds for things Tantivy's string parser cannot express on
# date fields: open-ended ranges use far-past/far-future string sentinels
# (OPEN_LO/OPEN_HI), and unparseable dates use a degenerate no-match range
# (NO_MATCH). Both can be replaced with real tantivy.Query objects
# (Query.range_query(..., None) for open bounds, Query.empty_query() for
# no-match) once tantivy-py accepts Python datetimes in range_query/term_query on
# Date fields. That support exists on tantivy-py master (PRs #655 + #666) but
# postdates the pinned 0.26.0 wheel, so it is blocked only on a published release
# > 0.26.0 and a dependency bump.

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


# Produced by the comma-resolution pass (not by scan()).
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


# Produced by the comma-resolution pass (not by scan()).
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
    as verbatim ``Passthrough`` runs. Non-recursive: finds the first matching
    close bracket/quote. Nested brackets are not valid Tantivy range syntax and
    pass through verbatim on mismatch.
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
        if (
            m
            and m.group("field") in KNOWN_FIELDS
            and (i == 0 or not (query[i - 1].isalnum() or query[i - 1] == "_"))
        ):
            field = m.group("field")
            j = m.end()
            if j < n and query[j] in "[{":
                rng = _consume_range(query, j, field)
                if rng is not None:
                    token, i = rng
                    flush()
                    tokens.append(token)
                    i = _maybe_comma(query, i, tokens)
                    continue
            else:
                val = _consume_value(query, j)
                if val is not None:
                    value, k = val
                    # Handle trailing comma semantics.
                    while k < n and query[k] == ",":
                        nxt = k + 1
                        if _looks_like_known_field(query, nxt):
                            # Clause separator: emit Comma() after this token.
                            break
                        # Not a clause separator: consume more.
                        if field in MULTI_VALUE_FIELDS and (
                            nxt >= n or query[nxt] not in "[{ \t),"
                        ):
                            # Multi-value field: accumulate as comma-joined value
                            # (resolve_commas will split into FieldValueList).
                            more = _consume_value(query, nxt)
                            if more is None:
                                break
                            value = f"{value},{more[0]}"
                            k = more[1]
                        else:
                            # Non-multi-value field: comma is literal, keep consuming.
                            more = _consume_value(query, nxt)
                            if more is None:
                                break
                            value = f"{value},{more[0]}"
                            k = more[1]
                    flush()
                    tokens.append(FieldValue(field, value))
                    i = k
                    i = _maybe_comma(query, i, tokens)
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
    """Consume a bare or quoted field value from ``start``, stopping at comma."""
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
    while j < n and query[j] not in " \t),":
        j += 1
    return query[start:j], j


def _looks_like_known_field(query: str, pos: int) -> bool:
    """True if a known ``field:`` token starts at ``pos``."""
    m = _FIELD_RE.match(query, pos)
    return bool(m and m.group("field") in KNOWN_FIELDS)


def _maybe_comma(query: str, i: int, tokens: list) -> int:
    """If a clause-separator comma follows at ``i``, emit ``Comma()`` and advance."""
    if i < len(query) and query[i] == "," and _looks_like_known_field(query, i + 1):
        tokens.append(Comma())
        return i + 1
    return i


def resolve_commas(tokens: list) -> list:
    """
    Collapse value-list commas into ``FieldValueList`` and keep clause-separator
    commas as ``Comma``. (Clause-sep commas are already emitted by ``scan`` via
    the value-stop logic; this pass folds value-lists.)
    """
    out: list = []
    for tok in tokens:
        if (
            isinstance(tok, FieldValue)
            and tok.field in MULTI_VALUE_FIELDS
            and "," in tok.value
        ):
            values = tuple(v for v in tok.value.split(",") if v)
            out.append(FieldValueList(tok.field, values))
        else:
            out.append(tok)
    return out
