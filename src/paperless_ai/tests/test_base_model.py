import json

from paperless_ai.base_model import MAX_DATES
from paperless_ai.base_model import MAX_NEW_NAMES
from paperless_ai.base_model import MAX_SINGLE_VALUE_NAMES
from paperless_ai.base_model import MAX_TITLE_LENGTH
from paperless_ai.base_model import ClassificationSuggestions
from paperless_ai.base_model import DocumentClassifierSchema
from paperless_ai.base_model import TaxonomyChoiceDict
from paperless_ai.base_model import classification_suggestions_to_model
from paperless_ai.base_model import model_to_classification_suggestions


def test_document_classifier_schema_declared_defaults():
    """
    GIVEN:
        - A DocumentClassifierSchema constructed with only the required
          title field
    WHEN:
        - The schema is dumped to a dict via model_dump()
    THEN:
        - Every optional name field, and dates, dump as empty lists

    The model may omit optional fields, so the schema must provide the complete
    empty shape expected by the conversion and matching pipeline.
    """
    schema = DocumentClassifierSchema(title="Test Title")

    dumped = schema.model_dump()

    assert dumped == {
        "title": "Test Title",
        "tags": [],
        "matched_tags": [],
        "tag_ids": [],
        "correspondents": [],
        "matched_correspondents": [],
        "correspondent_ids": [],
        "document_types": [],
        "matched_document_types": [],
        "document_type_ids": [],
        "storage_paths": [],
        "matched_storage_paths": [],
        "storage_path_ids": [],
        "dates": [],
    }


def test_model_response_converts_names_to_internal_taxonomy_choices():
    """
    GIVEN:
        - A model response containing taxonomy names
    WHEN:
        - It is converted to Paperless' internal suggestion representation
    THEN:
        - Names enter the internal taxonomy representation as new names
        - Existing IDs remain empty for deterministic application-side matching
    """
    parsed = DocumentClassifierSchema(
        title="Electricity Bill",
        tags=["Utilities", "Electricity"],
        correspondents=["Power Company"],
        document_types=["Utility Bill"],
        storage_paths=["Finance/Utilities"],
    )
    suggestions = model_to_classification_suggestions(parsed)

    assert suggestions["tags"] == {
        "existing_ids": [],
        "new_names": ["Utilities", "Electricity"],
    }
    assert suggestions["correspondents"] == {
        "existing_ids": [],
        "new_names": ["Power Company"],
    }
    assert suggestions["document_types"] == {
        "existing_ids": [],
        "new_names": ["Utility Bill"],
    }
    assert suggestions["storage_paths"] == {
        "existing_ids": [],
        "new_names": ["Finance/Utilities"],
    }


def test_valid_candidate_mappings_replace_only_the_matched_names():
    parsed = DocumentClassifierSchema(
        title="Electricity Bill",
        tags=["Utilities", "Electricity"],
        matched_tags=["Utilities"],
        tag_ids=[12],
        correspondents=["Power Company"],
        matched_correspondents=["Power Company"],
        correspondent_ids=[23],
    )

    suggestions = model_to_classification_suggestions(
        parsed,
        {
            "tags": {12},
            "correspondents": {23},
        },
    )

    assert suggestions["tags"] == {
        "existing_ids": [12],
        "new_names": ["Electricity"],
    }
    assert suggestions["correspondents"] == {
        "existing_ids": [23],
        "new_names": [],
    }


def test_invalid_or_unpaired_candidate_mappings_do_not_remove_names():
    parsed = DocumentClassifierSchema(
        title="Electricity Bill",
        tags=["Utilities", "Electricity", "Energy"],
        matched_tags=["Invented", "Utilities", "Electricity"],
        tag_ids=[12, 999],
    )

    suggestions = model_to_classification_suggestions(
        parsed,
        {"tags": {12}},
    )

    assert suggestions["tags"] == {
        "existing_ids": [],
        "new_names": ["Utilities", "Electricity", "Energy"],
    }


def test_document_classifier_schema_json_schema_is_self_contained():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - Its JSON schema is generated via model_json_schema()
    THEN:
        - The schema contains no definitions, references, or nested objects
        - Every response field is a scalar or flat array

    This keeps the function declaration compatible with backends that reject
    JSON Schema references and with smaller models that struggle with nesting.
    """
    schema = DocumentClassifierSchema.model_json_schema()

    assert "$defs" not in schema
    assert "$ref" not in json.dumps(schema)
    assert all(
        field_schema.get("type") != "object"
        for field_schema in schema["properties"].values()
    )


def test_every_field_describes_itself_to_the_model():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - Its JSON schema is generated via model_json_schema()
    THEN:
        - Every property carries a non-empty description

    In tool-calling mode the schema is most of what tells the model how to
    fill these fields; on field names alone, small models can bin tags and
    correspondents into storage_paths.
    """
    schema = DocumentClassifierSchema.model_json_schema()

    undescribed = [
        name
        for name, prop in schema["properties"].items()
        if not prop.get("description")
    ]

    assert undescribed == []


def test_every_sequence_in_the_emitted_schema_is_bounded():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - Its JSON schema is generated via model_json_schema()
    THEN:
        - Every array property in the schema carries a maxItems
    """
    schema = DocumentClassifierSchema.model_json_schema()

    unbounded = [
        name
        for name, prop in schema["properties"].items()
        if prop.get("type") == "array" and "maxItems" not in prop
    ]

    assert unbounded == []


def test_single_valued_categories_are_capped_below_tags():
    r"""
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - The emitted maxItems for each category is inspected
    THEN:
        - Correspondents, document types and storage paths are capped at
          MAX_SINGLE_VALUE_NAMES, and their matched_*/\*_ids lists with them
        - Tags keep the larger MAX_NEW_NAMES bound

    A document has exactly one correspondent, document type and storage path.
    Offering eight slots for each is how 3.0.5 came to suggest four separate
    correspondents for a single document; tags are genuinely multi-valued and
    keep their headroom.
    """
    properties = DocumentClassifierSchema.model_json_schema()["properties"]

    for field in (
        "correspondents",
        "matched_correspondents",
        "correspondent_ids",
        "document_types",
        "matched_document_types",
        "document_type_ids",
        "storage_paths",
        "matched_storage_paths",
        "storage_path_ids",
    ):
        assert properties[field]["maxItems"] == MAX_SINGLE_VALUE_NAMES, field

    assert properties["tags"]["maxItems"] == MAX_NEW_NAMES
    assert MAX_SINGLE_VALUE_NAMES < MAX_NEW_NAMES


def test_over_long_single_valued_response_is_truncated():
    """
    GIVEN:
        - A response naming four correspondents for one document, as 3.0.5
          routinely produced
    WHEN:
        - The model is constructed and converted
    THEN:
        - Only the first MAX_SINGLE_VALUE_NAMES survive, with no error

    The cap is a ceiling, not a quality filter - it keeps whichever names the
    model emitted first, which is why the field description also asks for the
    best ones first. Derived from the constant rather than hardcoded: the
    exact bound is a tuning decision, the truncation is the contract.
    """
    names = [f"Correspondent {i}" for i in range(MAX_SINGLE_VALUE_NAMES + 2)]

    parsed = DocumentClassifierSchema(title="T", correspondents=names)

    assert parsed.correspondents == names[:MAX_SINGLE_VALUE_NAMES]


def test_dates_bound_matches_what_the_prompt_asks_for():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - The emitted maxItems for dates is inspected
    THEN:
        - It equals the 3 that build_prompt_without_rag asks the model for
    """
    dates_schema = DocumentClassifierSchema.model_json_schema()["properties"]["dates"]

    assert dates_schema["maxItems"] == MAX_DATES == 3


def test_over_long_response_is_truncated_rather_than_rejected():
    """
    GIVEN:
        - An LLM response overshooting every declared bound
    WHEN:
        - DocumentClassifierSchema is constructed from it
    THEN:
        - Each field is clipped to its maximum, with no ValidationError
    """
    parsed = DocumentClassifierSchema(
        title="T" * (MAX_TITLE_LENGTH + 50),
        tags=["n"] * (MAX_NEW_NAMES + 20),
        dates=[f"2016-{month:02d}-01" for month in range(1, 13)],
    )

    assert len(parsed.title) == MAX_TITLE_LENGTH
    assert len(parsed.dates) == MAX_DATES
    assert len(parsed.tags) == MAX_NEW_NAMES


def test_truncation_keeps_the_earliest_entries():
    """
    GIVEN:
        - An over-long dates list from an LLM response
    WHEN:
        - DocumentClassifierSchema is constructed from it
    THEN:
        - The kept entries are the first ones the model emitted
    """
    parsed = DocumentClassifierSchema(
        title="T",
        dates=["2016-10-01", "2016-09-01", "2016-08-01", "2016-07-01", "2016-06-01"],
    )

    assert parsed.dates == ["2016-10-01", "2016-09-01", "2016-08-01"]


def test_model_conversion_matches_internal_typed_dict_keys():
    """
    GIVEN:
        - A DocumentClassifierSchema instance
    WHEN:
        - It is converted to ClassificationSuggestions
    THEN:
        - The converted dict's keys exactly match ClassificationSuggestions'
          declared keys
        - The converted tags dict's keys exactly match TaxonomyChoiceDict's
          declared keys
    """
    schema = DocumentClassifierSchema(title="T", tags=["Tag"])
    suggestions = model_to_classification_suggestions(schema)

    assert set(suggestions.keys()) == set(
        ClassificationSuggestions.__annotations__.keys(),
    )
    assert set(suggestions["tags"].keys()) == set(
        TaxonomyChoiceDict.__annotations__.keys(),
    )


def test_internal_suggestions_convert_to_names_only_model():
    suggestions = ClassificationSuggestions(
        title="Electricity Bill",
        tags=TaxonomyChoiceDict(existing_ids=[1], new_names=["Utilities"]),
        correspondents=TaxonomyChoiceDict(
            existing_ids=[2],
            new_names=["Power Company"],
        ),
        document_types=TaxonomyChoiceDict(
            existing_ids=[3],
            new_names=["Utility Bill"],
        ),
        storage_paths=TaxonomyChoiceDict(
            existing_ids=[4],
            new_names=["Finance/Utilities"],
        ),
        dates=["2026-08-30"],
    )

    model = classification_suggestions_to_model(suggestions)

    converted = model_to_classification_suggestions(model)

    assert converted == ClassificationSuggestions(
        title="Electricity Bill",
        tags=TaxonomyChoiceDict(existing_ids=[], new_names=["Utilities"]),
        correspondents=TaxonomyChoiceDict(
            existing_ids=[],
            new_names=["Power Company"],
        ),
        document_types=TaxonomyChoiceDict(
            existing_ids=[],
            new_names=["Utility Bill"],
        ),
        storage_paths=TaxonomyChoiceDict(
            existing_ids=[],
            new_names=["Finance/Utilities"],
        ),
        dates=["2026-08-30"],
    )
