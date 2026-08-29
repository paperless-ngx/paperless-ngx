from paperless_ai.base_model import MAX_DATES
from paperless_ai.base_model import MAX_EXISTING_IDS
from paperless_ai.base_model import MAX_NEW_NAMES
from paperless_ai.base_model import MAX_TITLE_LENGTH
from paperless_ai.base_model import ClassificationSuggestions
from paperless_ai.base_model import DocumentClassifierSchema
from paperless_ai.base_model import TaxonomyChoice
from paperless_ai.base_model import TaxonomyChoiceDict


def test_document_classifier_schema_declared_defaults():
    """
    GIVEN:
        - A DocumentClassifierSchema constructed with only the required
          title field
    WHEN:
        - The schema is dumped to a dict via model_dump()
    THEN:
        - Every taxonomy field dumps as an empty existing_ids/new_names
          dict, and dates dumps as an empty list

    This is the one project-owned fact worth pinning down here: which
    defaults this schema declares for a partial LLM response (see
    client.py's DocumentClassifierSchema(**json.loads(...)) call sites,
    which construct from whatever subset of fields the backend actually
    returned). It deliberately hardcodes the expected literal rather than
    re-deriving it from TaxonomyChoice()/[] - pydantic's own
    default_factory machinery is not this project's to re-test, and a
    test that recomputes the expected value from the model under test
    can't ever catch a wrong default.
    """
    schema = DocumentClassifierSchema(title="Test Title")

    dumped = schema.model_dump()

    empty_choice = {"existing_ids": [], "new_names": []}
    assert dumped["tags"] == empty_choice
    assert dumped["correspondents"] == empty_choice
    assert dumped["document_types"] == empty_choice
    assert dumped["storage_paths"] == empty_choice
    assert dumped["dates"] == []


def test_document_classifier_schema_json_schema_is_self_contained():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - Its JSON schema is generated via model_json_schema()
    THEN:
        - No $defs section or taxonomy $ref survives in the schema
        - Each taxonomy property carries existing_ids/new_names inline

    Regression guard for #13831: Google's function-declaration schema rejects
    the $ref Pydantic normally emits for the nested TaxonomyChoice model.
    """
    schema = DocumentClassifierSchema.model_json_schema()

    assert "$defs" not in schema
    for field in ("tags", "correspondents", "document_types", "storage_paths"):
        field_schema = schema["properties"][field]
        assert "$ref" not in field_schema
        assert set(field_schema["properties"].keys()) == {
            "existing_ids",
            "new_names",
        }


def test_every_sequence_in_the_emitted_schema_is_bounded():
    """
    GIVEN:
        - The DocumentClassifierSchema pydantic model
    WHEN:
        - Its JSON schema is generated via model_json_schema()
    THEN:
        - Every array property in the schema, including those on each
          inlined TaxonomyChoice, carries a maxItems
    """
    schema = DocumentClassifierSchema.model_json_schema()

    unbounded = [
        f"{owner}.{name}"
        for owner, definition in [
            ("DocumentClassifierSchema", schema),
            *(
                (name, prop)
                for name, prop in schema["properties"].items()
                if prop.get("type") == "object"
            ),
        ]
        for name, prop in definition.get("properties", {}).items()
        if prop.get("type") == "array" and "maxItems" not in prop
    ]

    assert unbounded == []


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
        tags=TaxonomyChoice(
            existing_ids=list(range(MAX_EXISTING_IDS + 20)),
            new_names=["n"] * (MAX_NEW_NAMES + 20),
        ),
        dates=[f"2016-{month:02d}-01" for month in range(1, 13)],
    )

    assert len(parsed.title) == MAX_TITLE_LENGTH
    assert len(parsed.dates) == MAX_DATES
    assert len(parsed.tags.existing_ids) == MAX_EXISTING_IDS
    assert len(parsed.tags.new_names) == MAX_NEW_NAMES


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


def test_model_dump_matches_typed_dict_keys():
    """
    GIVEN:
        - A DocumentClassifierSchema instance
    WHEN:
        - It is dumped to a dict via model_dump()
    THEN:
        - The dumped dict's keys exactly match ClassificationSuggestions'
          declared keys
        - The dumped tags dict's keys exactly match TaxonomyChoiceDict's
          declared keys
    """
    # TaxonomyChoiceDict/ClassificationSuggestions are the static-typing
    # counterparts of TaxonomyChoice/DocumentClassifierSchema - this pins
    # down that .model_dump()'s actual runtime keys are exactly what the
    # TypedDicts declare, so the two don't silently drift apart.
    schema = DocumentClassifierSchema(title="T", tags=TaxonomyChoice(existing_ids=[1]))
    dumped = schema.model_dump()

    assert set(dumped.keys()) == set(ClassificationSuggestions.__annotations__.keys())
    assert set(dumped["tags"].keys()) == set(TaxonomyChoiceDict.__annotations__.keys())
