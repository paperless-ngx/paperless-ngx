import logging
from datetime import datetime
from decimal import Decimal
from decimal import InvalidOperation
from typing import Any
from typing import Final
from typing import TypedDict
from urllib.parse import urlparse

from documents.models import CustomField

logger = logging.getLogger("paperless_ai.custom_fields")

# Document link fields are intentionally not suggested: picking *which*
# document a field should point at is too error-prone for free-text
# extraction, and the LLM has no way to resolve it to a document ID.
EXCLUDED_DATA_TYPES: Final = (CustomField.FieldDataType.DOCUMENTLINK,)

TRUE_LITERALS: Final[frozenset[str]] = frozenset(
    {"true", "yes", "1", "ja", "oui", "sí", "si", "wahr", "sì"},
)
FALSE_LITERALS: Final[frozenset[str]] = frozenset(
    {"false", "no", "0", "nein", "non", "falsch", "false"},
)


class CustomFieldPromptData(TypedDict):
    """One custom field as handed to the LLM prompt."""

    id: int
    name: str
    data_type: str
    description: str
    select_options: list[str]


def get_ai_suggestable_custom_fields() -> list[CustomField]:
    """All custom fields the AI may suggest values for, in stable order."""
    return list(
        CustomField.objects.exclude(
            data_type__in=list(EXCLUDED_DATA_TYPES),
        ).order_by("id"),
    )


def get_custom_field_prompt_data() -> list[CustomFieldPromptData]:
    """Serialize the suggestable custom fields for the prompt.

    The user-provided description is the basis for the suggestion; the field
    name is the fallback when there is no description. Select options are
    included so the model can pick from them instead of inventing values.
    """
    return [
        CustomFieldPromptData(
            id=field.pk,
            name=field.name,
            data_type=field.data_type,
            description=(field.description or field.name).strip(),
            select_options=(
                [
                    option["label"]
                    for option in (
                        (field.extra_data or {}).get("select_options", []) or []
                    )
                ]
                if field.data_type == CustomField.FieldDataType.SELECT
                else []
            ),
        )
        for field in get_ai_suggestable_custom_fields()
    ]


def format_custom_fields_for_prompt(fields: list[CustomFieldPromptData]) -> str:
    """Render the custom-field instructions block. Returns "" when there are
    no fields, so callers can treat it like an empty taxonomy block.
    """
    if not fields:
        return ""

    lines = [
        (
            "Additionally, suggest values for these custom fields of this "
            "installation. Only return a value when the document clearly "
            "contains it; leave the value empty when you are not confident. "
            'Use the key "cf_<id>" (e.g. "cf_7") for each field and give '
            "the value as a single string:"
        ),
    ]
    for field in fields:
        line = (
            f"- cf_{field['id']} ({field['name']}, "
            f"{field['data_type']}): {field['description']}"
        )
        if field["select_options"]:
            options = ", ".join(field["select_options"])
            line += f" - one of: {options}"
        elif field["data_type"] == CustomField.FieldDataType.DATE:
            line += " - format YYYY-MM-DD"
        lines.append(line)
    return "\n".join(lines)


def _coerce(
    field: CustomField,
    raw: Any,
) -> Any | None:
    """Convert one raw LLM value into the storage type of ``field``, or None
    when it cannot be represented. Never raises.
    """
    if raw is None:
        return None
    value = str(raw).strip()
    if not value:
        return None

    data_type = field.data_type
    if data_type == CustomField.FieldDataType.BOOL:
        lowered = value.lower()
        if lowered in TRUE_LITERALS:
            return True
        if lowered in FALSE_LITERALS:
            return False
        return None

    if data_type == CustomField.FieldDataType.DATE:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None

    if data_type == CustomField.FieldDataType.INT:
        try:
            amount = Decimal(value)
        except InvalidOperation:
            return None
        if amount != amount.to_integral_value():
            return None
        return int(amount)

    if data_type == CustomField.FieldDataType.FLOAT:
        try:
            return float(Decimal(value))
        except (InvalidOperation, ValueError):
            return None

    if data_type == CustomField.FieldDataType.MONETARY:
        # value_monetary is a free string ("12,34 EUR"); accept it as-is,
        # but only when it contains at least one digit.
        if not any(char.isdigit() for char in value):
            return None
        return value

    if data_type == CustomField.FieldDataType.URL:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        return value

    if data_type == CustomField.FieldDataType.SELECT:
        options = (field.extra_data or {}).get("select_options", []) or []
        labels = [(option.get("label") or "").strip() for option in options]
        if value in labels:
            return value
        # Tolerate case/whitespace differences against the allowed options.
        for option in options:
            label = (option.get("label") or "").strip()
            if label and label.lower() == value.lower():
                return label
        return None

    # STRING and LONG_TEXT: accept as-is.
    return value


def coerce_custom_field_suggestions(
    raw_suggestions: dict[str, Any],
    fields: list[CustomField],
) -> dict[int, Any]:
    """Validate the model's ``cf_<id>`` values against the live field
    definitions and return {field_id: converted value}, dropping anything
    unknown, invalid, or of a type the LLM is not asked to fill.
    """
    fields_by_id = {field.pk: field for field in fields}
    result: dict[int, Any] = {}
    for key, raw in (raw_suggestions or {}).items():
        if not isinstance(key, str) or not key.startswith("cf_"):
            continue
        try:
            field_id = int(key[3:])
        except ValueError:
            continue
        field = fields_by_id.get(field_id)
        if field is None:
            logger.debug(
                "Ignoring AI suggestion for unknown custom field %s",
                key,
            )
            continue
        value = _coerce(field, raw)
        if value is None:
            if raw is not None and str(raw).strip():
                logger.debug(
                    "Dropping invalid AI suggestion %r for custom field %s (%s)",
                    raw,
                    field.name,
                    field.data_type,
                )
            continue
        result[field_id] = value
    return result
