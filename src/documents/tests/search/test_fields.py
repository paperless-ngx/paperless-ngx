from whoosh_compat import FieldKind

from documents.search._fields import PUBLIC_FIELDS


class TestPublicFields:
    def test_json_fields_have_subpaths(self) -> None:
        """
        GIVEN:
            - PUBLIC_FIELDS, the canonical query-syntax field table
        WHEN:
            - A field declares FieldKind.JSON
        THEN:
            - That field also declares at least one subpath
        """
        for field in PUBLIC_FIELDS:
            if field.kind is FieldKind.JSON:
                assert field.subpaths, f"{field.name} is JSON but has no subpaths"
