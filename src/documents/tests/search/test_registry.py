from collections.abc import Sequence

import pytest
from whoosh_compat import FieldKind
from whoosh_compat import FieldRegistry
from whoosh_compat.fields import ResolvedField

from documents.search._fields import PUBLIC_FIELDS
from documents.search._registry import get_field_registry


@pytest.fixture
def registry() -> FieldRegistry:
    return get_field_registry(None)


def _resolve(registry: FieldRegistry, name: str) -> ResolvedField:
    ref = registry.make_ref(name)
    assert ref is not None, f"{name} is not a valid field ref"
    resolved = registry.resolve(ref)
    assert resolved is not None, f"{name} did not resolve"
    return resolved


def _distinct_forms(result: str | Sequence[str]) -> tuple[str, ...]:
    """The forms a term may match, in order, the way whoosh-compat's emitter
    reads a pattern_normalizer's answer: a bare str is one form, a sequence is
    several, deduplicated."""
    if isinstance(result, str):
        return (result,)
    return tuple(dict.fromkeys(result))


class TestFieldRegistry:
    def test_internal_id_fields_are_not_registered(
        self,
        registry: FieldRegistry,
    ) -> None:
        """
        GIVEN:
            - The field registry built from PUBLIC_FIELDS
        WHEN:
            - An internal *_id column name (e.g. "tag_id") is looked up
        THEN:
            - The registry does not recognize it as a queryable field
        """
        for name in (
            "tag_id",
            "owner_id",
            "viewer_id",
            "correspondent_id",
            "document_type_id",
            "storage_path_id",
            "viewer_group_id",
        ):
            assert name not in registry

    def test_no_queryable_field_name_ends_in_id(self) -> None:
        """
        GIVEN:
            - PUBLIC_FIELDS, the canonical query-syntax field table
        WHEN:
            - Every declared field name is inspected
        THEN:
            - None of them end in "_id" (internal id columns, written for
              permission filtering and joins, must never reach the query
              surface; checked against PUBLIC_FIELDS rather than the
              registry so a leak is caught where it is declared)
        """
        leaked = [f.name for f in PUBLIC_FIELDS if f.name.endswith("_id")]
        assert not leaked, f"internal id fields reached the query surface: {leaked}"

    def test_type_alias_resolves_to_document_type(
        self,
        registry: FieldRegistry,
    ) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The alias "type" is resolved
        THEN:
            - It resolves to the canonical "document_type" field
        """
        assert _resolve(registry, "type").spec.name == "document_type"

    def test_path_alias_resolves_to_storage_path(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The alias "path" is resolved
        THEN:
            - It resolves to the canonical "storage_path" field
        """
        assert _resolve(registry, "path").spec.name == "storage_path"

    def test_notes_json_subpaths_resolve(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - "notes.user" is resolved
        THEN:
            - It resolves to the "notes" field with json_path "user"
        """
        resolved = _resolve(registry, "notes.user")
        assert resolved.spec.name == "notes"
        assert resolved.json_path == "user"
        assert resolved.is_subpath is True

    def test_custom_fields_json_subpaths_resolve(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - "custom_fields.name" and "custom_fields.value" are resolved
        THEN:
            - Both resolve without error
        """
        for raw in ("custom_fields.name", "custom_fields.value"):
            _resolve(registry, raw)

    def test_unregistered_json_subpath_does_not_resolve(
        self,
        registry: FieldRegistry,
    ) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - A dotted name naming an unregistered subpath ("notes.bogus")
              is turned into a FieldRef
        THEN:
            - make_ref returns None (it is not even a valid ref for
              resolve() to then reject)
        """
        assert registry.make_ref("notes.bogus") is None

    def test_tag_is_comma_values(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The "tag" field is resolved
        THEN:
            - It is marked comma_values=True
        """
        assert _resolve(registry, "tag").spec.comma_values is True

    def test_correspondent_is_not_comma_values(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The "correspondent" field is resolved
        THEN:
            - It is not marked comma_values ("tag" is the only field that
              opts in; end to end the two readings of
              "correspondent:foo,bar" agree anyway, since the analyzer
              splits the literal value on the comma regardless, so this is
              only observable at the registry level)
        """
        assert _resolve(registry, "correspondent").spec.comma_values is False

    def test_created_is_date_kind(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The "created" field is resolved
        THEN:
            - Its kind is DATE and date_only is True
        """
        resolved = _resolve(registry, "created")
        assert resolved.spec.kind is FieldKind.DATE
        assert resolved.spec.date_only is True

    def test_analyzer_lowercases_and_ascii_folds(self, registry: FieldRegistry) -> None:
        """
        GIVEN:
            - The field registry with no language configured (no stemmer
              in the analyzer chain)
        WHEN:
            - The "title" field's analyzer processes "Café"
        THEN:
            - It is lowercased and ASCII-folded to the single token "cafe"
        """
        resolved = _resolve(registry, "title")
        assert resolved.spec.analyzer is not None
        assert resolved.spec.analyzer("Café") == ["cafe"]

    def test_checksum_analyzer_is_identity_single_token(
        self,
        registry: FieldRegistry,
    ) -> None:
        """
        GIVEN:
            - The field registry
        WHEN:
            - The "checksum" field's analyzer (raw tokenizer, no
              splitting) processes "ABC-123"
        THEN:
            - It is returned unchanged as a single token
        """
        resolved = _resolve(registry, "checksum")
        assert resolved.spec.analyzer is not None
        assert resolved.spec.analyzer("ABC-123") == ["ABC-123"]

    def test_pattern_normalizer_follows_the_registry_language(
        self,
        registry: FieldRegistry,
    ) -> None:
        """
        GIVEN:
            - A registry with no language, and a registry built for "en"
        WHEN:
            - The "title" field's pattern normalizer processes "Running"
        THEN:
            - With no language, only the folded run is offered
              ("running"), since the index holds surface forms
            - With "en", the stem is offered too ("run"), since indexed
              terms are stemmed and the pattern has to reach them
        """
        resolved = _resolve(registry, "title")
        assert resolved.spec.pattern_normalizer is not None
        assert _distinct_forms(resolved.spec.pattern_normalizer("Running")) == (
            "running",
        )

        resolved_en = _resolve(get_field_registry("en"), "title")
        assert resolved_en.spec.pattern_normalizer is not None
        assert _distinct_forms(resolved_en.spec.pattern_normalizer("Running")) == (
            "running",
            "run",
        )

    def test_registry_is_cached_per_language(self) -> None:
        """
        GIVEN:
            - Two calls to get_field_registry("en")
        WHEN:
            - Both calls are made
        THEN:
            - They return the same registry instance
        """
        a = get_field_registry("en")
        b = get_field_registry("en")
        assert a is b

    def test_registry_rebuilds_on_language_change(self) -> None:
        """
        GIVEN:
            - A call to get_field_registry("en") and a call to
              get_field_registry("de")
        WHEN:
            - Both calls are made
        THEN:
            - They return different registry instances
        """
        a = get_field_registry("en")
        b = get_field_registry("de")
        assert a is not b
