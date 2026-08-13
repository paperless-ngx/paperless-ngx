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
        - $defs includes a fully-resolvable TaxonomyChoice definition with
          existing_ids/new_names properties

    client.py hands this generated schema straight to the LLM backend as
    the response-format constraint (Ollama's format=json_schema, and the
    OpenAI-like tool-calling path). What that backend actually needs is a
    self-contained schema it can resolve without a document loader --
    unlike a bare "$ref present" check, this asserts the referenced
    definition genuinely carries the two fields the rest of the pipeline
    (parse_ai_response, matching.py's resolve_*_ids) relies on.
    """
    schema = DocumentClassifierSchema.model_json_schema()

    defs = schema.get("$defs", {})
    assert "TaxonomyChoice" in defs
    taxonomy_choice_properties = defs["TaxonomyChoice"]["properties"]
    assert set(taxonomy_choice_properties.keys()) == {"existing_ids", "new_names"}


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
