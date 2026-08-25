"""``_DEFAULT_SEARCH_FIELDS`` must stay a subset of the registered public
field names.

Nothing enforced this before: a rename in PUBLIC_FIELDS not mirrored in
``_DEFAULT_SEARCH_FIELDS`` (documents/search/_query.py) would 400 every
unfielded search at request time, since ``index.parse_query`` and the
fuzzy/CJK clause builders are handed a field name the schema no longer
has.
"""

from __future__ import annotations

from documents.search._fields import PUBLIC_FIELDS
from documents.search._query import _DEFAULT_SEARCH_FIELDS


class TestDefaultSearchFieldsAreRegistered:
    def test_every_default_search_field_is_a_public_field(self) -> None:
        public_field_names = {f.name for f in PUBLIC_FIELDS}
        assert set(_DEFAULT_SEARCH_FIELDS) <= public_field_names
