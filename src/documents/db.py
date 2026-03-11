"""Cross-database accent folding support for Django ORM queries."""

from __future__ import annotations

import unicodedata

from django.db.models import CharField
from django.db.models import TextField
from django.db.models import Transform

# Pre-built translation table for fast accent stripping via str.translate().
# Covers Latin-1 Supplement, Latin Extended-A/B, and Latin Extended Additional.
_ACCENT_TABLE: dict[int, str] = {}
for _i in list(range(0x00C0, 0x024F + 1)) + list(range(0x1E00, 0x1EFF + 1)):
    _c = chr(_i)
    _nfkd = unicodedata.normalize("NFKD", _c)
    _stripped = "".join(_ch for _ch in _nfkd if unicodedata.category(_ch) != "Mn")
    if _stripped != _c:
        _ACCENT_TABLE[_i] = _stripped
_TRANSLATE_TABLE = str.maketrans(_ACCENT_TABLE)


def strip_accents(value: str | None) -> str:
    """Remove diacritical marks from a string.

    Uses a pre-built translation table for performance (important when
    called as a SQLite user-defined function on every row).

    E.g. "étudiant" -> "etudiant", "café" -> "cafe"
    """
    if value is None:
        return ""
    return value.translate(_TRANSLATE_TABLE)


class Unaccent(Transform):
    """A cross-database Transform that strips accents/diacritics.

    - PostgreSQL: uses the native ``unaccent()`` function (requires the
      ``unaccent`` extension).
    - SQLite: uses a fast Python function registered at connection time.
    - MariaDB/MySQL: accent folding is already handled by the
      ``utf8mb4_unicode_ci`` collation, so this is a no-op passthrough.

    ``bilateral = True`` ensures both the column value and the query
    parameter are transformed.
    """

    lookup_name = "unaccent"
    bilateral = True

    def as_postgresql(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return f"unaccent({lhs})", params

    def as_sqlite(self, compiler, connection):
        lhs, params = compiler.compile(self.lhs)
        return f"paperless_unaccent({lhs})", params

    def as_sql(self, compiler, connection):
        # MariaDB / fallback: passthrough (no transformation)
        lhs, params = compiler.compile(self.lhs)
        return lhs, params


CharField.register_lookup(Unaccent)
TextField.register_lookup(Unaccent)


def setup_sqlite_unaccent(sender, connection, **kwargs):
    """Register the ``paperless_unaccent`` function for SQLite connections."""
    if connection.vendor == "sqlite":
        connection.connection.create_function("paperless_unaccent", 1, strip_accents)
