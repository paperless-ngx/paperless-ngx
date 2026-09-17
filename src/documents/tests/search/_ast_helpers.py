"""Field references and leaf constructors shared by the unit-level tests.

These are pure whoosh-compat AST values with no state and no database
behind them, so they stay plain module-level functions rather than
fixtures. ``NOTES`` is the reason this module exists at all: notes is a
JSON field, so addressing its text means naming a subpath, and spelling
``wc.FieldRef("notes", "note")`` out once per test file invites two of
them to disagree.
"""

from __future__ import annotations

import whoosh_compat as wc
import whoosh_compat.ast as wc_ast

CONTENT = wc.FieldRef("content")
TITLE = wc.FieldRef("title")
NOTES = wc.FieldRef("notes", "note")
BIGRAM_CONTENT = wc.FieldRef("bigram_content")
BIGRAM_TITLE = wc.FieldRef("bigram_title")


def content(text: str) -> wc_ast.Term:
    """A Term on the content field, the default leaf these tests widen."""
    return wc_ast.Term(field=CONTENT, text=text)


def bigram(text: str) -> wc_ast.Term:
    """A Term on the bigram side of content."""
    return wc_ast.Term(field=BIGRAM_CONTENT, text=text)
