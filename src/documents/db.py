"""Cross-database accent folding support for Django ORM queries."""

from __future__ import annotations

import unicodedata

from django.db.models import CharField
from django.db.models import TextField
from django.db.models import Transform


def strip_accents(value: str | None) -> str:
    """Remove diacritical marks from a string.

    E.g. "étudiant" -> "etudiant", "café" -> "cafe"
    """
    if value is None:
        return ""
    nfkd = unicodedata.normalize("NFKD", value)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


class Unaccent(Transform):
    """A cross-database Transform that strips accents/diacritics.

    - PostgreSQL: uses the native ``unaccent()`` function (requires the
      ``unaccent`` extension).
    - SQLite: uses a Python function registered at connection time.
    - MariaDB/MySQL: accent folding is already handled by the
      ``utf8mb4_unicode_ci`` collation, so this is a no-op passthrough.
    """

    lookup_name = "unaccent"
    bilateral = True  # apply to both sides of the comparison

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
