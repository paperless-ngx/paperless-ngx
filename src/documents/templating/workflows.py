import logging
from collections.abc import Mapping
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import Any

from django.utils.text import slugify as django_slugify
from jinja2 import StrictUndefined
from jinja2 import Template
from jinja2 import TemplateAssertionError
from jinja2 import TemplateSyntaxError
from jinja2 import UndefinedError
from jinja2 import make_logging_undefined
from jinja2.meta import find_undeclared_variables
from jinja2.sandbox import SecurityError

from documents.models import CustomField
from documents.models import Document
from documents.templating.environment import _template_environment
from documents.templating.filters import format_datetime
from documents.templating.filters import get_cf_value
from documents.templating.filters import localize_date

logger = logging.getLogger("paperless.templating")

_LogStrictUndefined = make_logging_undefined(logger, StrictUndefined)


_template_environment.undefined = _LogStrictUndefined

_template_environment.filters["datetime"] = format_datetime

_template_environment.filters["slugify"] = django_slugify

_template_environment.filters["localize_date"] = localize_date

_template_environment.filters["get_cf_value"] = get_cf_value


_known_placeholder_names = {
    "correspondent",
    "document_type",
    "added",
    "added_year",
    "added_year_short",
    "added_month",
    "added_month_name",
    "added_month_name_short",
    "added_day",
    "added_time",
    "owner_username",
    "original_filename",
    "filename",
    "created",
    "created_year",
    "created_year_short",
    "created_month",
    "created_month_name",
    "created_month_name_short",
    "created_day",
    "created_time",
    "doc_title",
    "doc_url",
    "doc_id",
    "custom_fields",
}


def _custom_field_context_value(field: CustomField, value: Any) -> Any:
    if field.data_type == CustomField.FieldDataType.SELECT and value is not None:
        options = (field.extra_data or {}).get("select_options", [])
        for option in options:
            if option["id"] == value:
                return option["label"]
        return None
    return value


def get_custom_field_context_entry(field: CustomField, value: Any) -> dict[str, Any]:
    return {
        "type": field.data_type,
        "value": _custom_field_context_value(field, value),
    }


def get_document_custom_fields_context(document: Document) -> dict[str, dict[str, Any]]:
    """Expose document custom fields without passing model instances to Jinja."""
    return {
        instance.field.name: get_custom_field_context_entry(
            instance.field,
            instance.value,
        )
        for instance in document.custom_fields.select_related("field")
    }


def get_override_custom_fields_context(
    values: Mapping[int, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Expose custom fields assigned before a document has been consumed."""
    if not values:
        return {}
    return {
        field.name: get_custom_field_context_entry(field, values[field.pk])
        for field in CustomField.objects.filter(pk__in=values)
    }


def validate_workflow_template(text: str) -> None:
    try:
        ast = _template_environment.parse(text)
        undeclared_vars = find_undeclared_variables(ast)
    except TemplateAssertionError as e:
        raise ValueError(f"Template assertion error: {e}")
    except TemplateSyntaxError as e:
        raise ValueError(f"Template syntax error: {e}")
    unknown_vars = undeclared_vars - _known_placeholder_names
    if unknown_vars:
        raise KeyError(
            f"Template references unknown placeholders: {', '.join(unknown_vars)}",
        )


def parse_w_workflow_placeholders(
    text: str,
    correspondent_name: str,
    doc_type_name: str,
    owner_username: str,
    local_added: datetime,
    original_filename: str,
    filename: str,
    created: date | None = None,
    doc_title: str | None = None,
    doc_url: str | None = None,
    doc_id: int | None = None,
    custom_fields: Mapping[str, dict[str, Any]] | None = None,
) -> str:
    """
    Available title placeholders for Workflows depend on what has already been assigned,
    e.g. for pre-consumption triggers created will not have been parsed yet, but it will
    for added / updated triggers
    """

    formatting = {
        "correspondent": correspondent_name,
        "document_type": doc_type_name,
        "added": local_added.isoformat(),
        "added_year": local_added.strftime("%Y"),
        "added_year_short": local_added.strftime("%y"),
        "added_month": local_added.strftime("%m"),
        "added_month_name": local_added.strftime("%B"),
        "added_month_name_short": local_added.strftime("%b"),
        "added_day": local_added.strftime("%d"),
        "added_time": local_added.strftime("%H:%M"),
        "owner_username": owner_username,
        "original_filename": Path(original_filename).stem,
        "filename": Path(filename).stem,
        "custom_fields": custom_fields or {},
    }
    if created is not None:
        formatting.update(
            {
                "created": created.isoformat(),
                "created_year": created.strftime("%Y"),
                "created_year_short": created.strftime("%y"),
                "created_month": created.strftime("%m"),
                "created_month_name": created.strftime("%B"),
                "created_month_name_short": created.strftime("%b"),
                "created_day": created.strftime("%d"),
                "created_time": created.strftime("%H:%M"),
            },
        )
    if doc_title is not None:
        formatting.update({"doc_title": doc_title})
    if doc_url is not None:
        formatting.update({"doc_url": doc_url})
    if doc_id is not None:
        formatting.update({"doc_id": str(doc_id)})

    logger.debug(f"Parsing Workflow Jinja template: {text}")
    try:
        template = _template_environment.from_string(
            text,
            template_class=Template,
        )
        rendered_template = template.render(formatting)

        # We're good!
        return rendered_template
    except UndefinedError as e:
        # The undefined class logs this already for us
        raise e
    except TemplateSyntaxError as e:
        logger.warning(f"Template syntax error in title generation: {e}")
    except SecurityError as e:
        logger.warning(f"Template attempted restricted operation: {e}")
    except Exception as e:
        logger.warning(f"Unknown error in title generation: {e}")
        logger.warning(
            f"Invalid title format '{text}', workflow not applied: {e}",
        )
        raise e
    return None
