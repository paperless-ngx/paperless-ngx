import datetime

import pytest
from django.test import override_settings

from documents.models import CustomField
from paperless.config import AIConfig
from paperless_ai.ai_classifier import build_prompt_without_rag
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.base_model import DocumentClassifierSchema
from paperless_ai.custom_fields import coerce_custom_field_suggestions
from paperless_ai.custom_fields import format_custom_fields_for_prompt
from paperless_ai.custom_fields import get_ai_suggestable_custom_fields
from paperless_ai.custom_fields import get_custom_field_prompt_data
from paperless_ai.taxonomy import empty_taxonomy_candidates

_counter = 0


def _make_field(name, data_type, description=None, extra_data=None):
    """Create a custom field with a unique name; the name suffix identifies
    the field within a test, independent of test execution order."""
    global _counter
    _counter += 1
    return CustomField.objects.create(
        name=f"{name}-{_counter}",
        data_type=data_type,
        description=description,
        extra_data=extra_data,
    )


def _prompt_data_for(name_prefix):
    """The prompt data entries for fields created with the given name prefix."""
    return [
        entry
        for entry in get_custom_field_prompt_data()
        if entry["name"].startswith(name_prefix)
    ]


def _coerce_one(field, raw) -> dict[int, object]:
    return coerce_custom_field_suggestions({"cf_1": raw}, [field])


def test_suggestable_excludes_document_links(db):
    """Document link fields are never suggested by the AI."""
    _make_field("Normal", "string")
    _make_field("Link", CustomField.FieldDataType.DOCUMENTLINK)

    fields = get_ai_suggestable_custom_fields()

    assert [field.name for field in fields] == [
        field.name for field in fields if "Link" not in field.name
    ]
    assert all("Link" not in field.name for field in fields)


def test_prompt_data_falls_back_to_name_without_description(db):
    """Without a description, the field name is the suggestion basis."""
    field = _make_field("Invoice Number", "string")

    data = _prompt_data_for("Invoice Number")

    assert len(data) == 1
    assert data[0]["id"] == field.pk
    assert data[0]["description"] == field.name
    assert data[0]["select_options"] == []


def test_prompt_data_prefers_description_over_name(db):
    """The user description wins over the field name when present."""
    _make_field(
        "x",
        "string",
        description="The unique reference code printed on the document",
    )

    data = _prompt_data_for("x")

    assert data[0]["description"] == "The unique reference code printed on the document"


def test_prompt_data_includes_select_options(db):
    """Select fields list their allowed options in the prompt data."""
    _make_field(
        "Priority",
        "select",
        extra_data={"select_options": [{"label": "Low"}, {"label": "High"}]},
    )

    data = _prompt_data_for("Priority")

    assert data[0]["select_options"] == ["Low", "High"]


def test_format_prompt_empty_when_no_fields():
    """No fields means no block, like the empty taxonomy block."""
    assert format_custom_fields_for_prompt([]) == ""


def test_format_prompt_renders_fields_and_formats(db):
    """The block names each field by cf_<id>, its type and description."""
    date_field = _make_field("Payment Date", "date")

    block = format_custom_fields_for_prompt(get_custom_field_prompt_data())

    assert f"cf_{date_field.pk}" in block
    assert "Payment Date" in block
    assert "YYYY-MM-DD" in block
    assert "leave the value empty when you are not confident" in block


def test_format_prompt_renders_select_options(db):
    """Select fields render their allowed options inline."""
    _make_field(
        "Status",
        "select",
        extra_data={"select_options": [{"label": "Open"}, {"label": "Closed"}]},
    )

    block = format_custom_fields_for_prompt(get_custom_field_prompt_data())

    assert "one of: Open, Closed" in block


def test_prompt_without_rag_includes_custom_fields_block(db):
    """The custom fields block reaches the rendered classification prompt."""
    from unittest.mock import MagicMock

    doc = MagicMock()
    doc.filename = "f.pdf"
    doc.content = "some content"

    _make_field("Project", "string")
    config = AIConfig()

    prompt = build_prompt_without_rag(
        doc,
        config,
        custom_fields_block=format_custom_fields_for_prompt(
            get_custom_field_prompt_data(),
        ),
    )

    assert "suggest values for these custom fields" in prompt
    assert "cf_" in prompt


def test_prompt_without_rag_omits_block_when_no_fields(db):
    """With no custom fields, the prompt carries no custom-field section."""
    from unittest.mock import MagicMock

    doc = MagicMock()
    doc.filename = "f.pdf"
    doc.content = "some content"

    config = AIConfig()
    prompt = build_prompt_without_rag(doc, config)

    assert "custom fields" not in prompt


@pytest.mark.django_db
class TestCoerce:
    def test_string(self, db):
        field = _make_field("s", "string")
        assert _coerce_one(field, "hello") == {1: "hello"}

    def test_string_empty_is_dropped(self, db):
        field = _make_field("s", "string")
        assert _coerce_one(field, "   ") == {}

    def test_long_text(self, db):
        field = _make_field("lt", "longtext")
        assert _coerce_one(field, "a\nb") == {1: "a\nb"}

    @pytest.mark.parametrize(
        "raw,expected",
        [("true", True), ("YES", True), ("0", False), ("nein", False)],
    )
    def test_bool(self, db, raw, expected):
        field = _make_field("b", "boolean")
        assert _coerce_one(field, raw) == {1: expected}

    def test_bool_unknown_is_dropped(self, db):
        field = _make_field("b", "boolean")
        assert _coerce_one(field, "maybe") == {}

    def test_date(self, db):
        field = _make_field("d", "date")
        assert _coerce_one(field, "2026-09-30") == {1: datetime.date(2026, 9, 30)}

    def test_date_invalid_is_dropped(self, db):
        field = _make_field("d", "date")
        assert _coerce_one(field, "30.09.2026") == {}

    @pytest.mark.parametrize(
        "raw,expected",
        [("42", 42), ("1e2", 100), ("abc", None), ("1.5", None)],
    )
    def test_int(self, db, raw, expected):
        field = _make_field("i", "integer")
        result = _coerce_one(field, raw)
        if expected is None:
            assert result == {}
        else:
            assert result == {1: expected}

    @pytest.mark.parametrize(
        "raw,expected",
        [("3.7", 3.7), ("4", 4.0), ("abc", None)],
    )
    def test_float(self, db, raw, expected):
        field = _make_field("f", "float")
        result = _coerce_one(field, raw)
        if expected is None:
            assert result == {}
        else:
            assert result == {1: expected}

    @pytest.mark.parametrize(
        "raw,expected",
        [("12,34 EUR", "12,34 EUR"), ("EUR", None)],
    )
    def test_monetary(self, db, raw, expected):
        field = _make_field("m", "monetary")
        result = _coerce_one(field, raw)
        if expected is None:
            assert result == {}
        else:
            assert result == {1: expected}

    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("https://example.com/doc", "https://example.com/doc"),
            ("not a url", None),
            ("ftp://example.com", None),
        ],
    )
    def test_url(self, db, raw, expected):
        field = _make_field("u", "url")
        result = _coerce_one(field, raw)
        if expected is None:
            assert result == {}
        else:
            assert result == {1: expected}

    def test_select_exact_option(self, db):
        field = _make_field(
            "sel",
            "select",
            extra_data={"select_options": [{"label": "High"}, {"label": "Low"}]},
        )
        assert _coerce_one(field, "High") == {1: "High"}

    def test_select_case_insensitive_maps_to_canonical_label(self, db):
        field = _make_field(
            "sel",
            "select",
            extra_data={"select_options": [{"label": "High"}]},
        )
        assert _coerce_one(field, "high") == {1: "High"}

    def test_select_unknown_option_is_dropped(self, db):
        field = _make_field(
            "sel",
            "select",
            extra_data={"select_options": [{"label": "High"}]},
        )
        assert _coerce_one(field, "Urgent") == {}


def test_coerce_ignores_unknown_keys(db):
    """Keys for fields that do not exist are dropped, not raised."""
    field = _make_field("s", "string")

    result = coerce_custom_field_suggestions(
        {"cf_1": "ok", "cf_999": "nope", "tags": "junk", "cf_x": "junk"},
        [field],
    )

    assert result == {1: "ok"}


@pytest.mark.django_db
@override_settings(LLM_BACKEND="ollama", LLM_MODEL="some_model")
def test_get_ai_document_classification_returns_coerced_custom_fields(db):
    """
    GIVEN:
        - String, date and select custom fields
        - An LLM response with valid, invalid and unknown cf_<id> values
    WHEN:
        - get_ai_document_classification() is called
    THEN:
        - Valid values are coerced per type into suggestions["custom_fields"]
        - Invalid and unknown values are dropped
        - The classification prompt contains the custom fields block
    """
    from unittest.mock import MagicMock
    from unittest.mock import patch

    string_field = _make_field("Project", "string")
    date_field = _make_field("Due", "date")
    select_field = _make_field(
        "Priority",
        "select",
        extra_data={"select_options": [{"label": "High"}]},
    )

    mock_document = MagicMock()
    mock_document.filename = "invoice.pdf"
    mock_document.content = "content"

    flat_response = DocumentClassifierSchema(
        title="Invoice",
        custom_fields={
            f"cf_{string_field.pk}": "Website",
            f"cf_{date_field.pk}": "2026-12-01",
            f"cf_{select_field.pk}": "High",
            "cf_9999": "ghost",
        },
    )

    with (
        patch(
            "paperless_ai.ai_classifier.get_taxonomy_context",
            return_value=(empty_taxonomy_candidates(), ""),
        ),
        patch(
            "paperless_ai.client.AIClient.run_llm_query",
            return_value=flat_response,
        ) as mock_llm,
    ):
        result = get_ai_document_classification(mock_document)

    prompt = mock_llm.call_args.args[0]
    assert f"cf_{string_field.pk}" in prompt
    assert f"cf_{date_field.pk}" in prompt

    custom = result["custom_fields"]
    assert custom[string_field.pk] == "Website"
    assert custom[date_field.pk] == datetime.date(2026, 12, 1)
    assert custom[select_field.pk] == "High"
    assert 9999 not in custom
