import logging
from datetime import date
from datetime import datetime
from pathlib import Path

from django.utils.text import slugify as django_slugify
from jinja2 import StrictUndefined
from jinja2 import Template
from jinja2 import TemplateAssertionError
from jinja2 import TemplateSyntaxError
from jinja2 import UndefinedError
from jinja2 import make_logging_undefined
from jinja2.meta import find_undeclared_variables
from jinja2.sandbox import SecurityError

from documents.templating.environment import _template_environment
from documents.templating.filters import format_datetime
from documents.templating.filters import localize_date

logger = logging.getLogger("paperless.templating")

_LogStrictUndefined = make_logging_undefined(logger, StrictUndefined)


_template_environment.undefined = _LogStrictUndefined


# The `mail` namespace exposed to templates when a document was consumed via
# a mail rule. Non-mail triggers get this same shape with empty values so that
# `{{ mail.subject }}` renders as an empty string rather than blowing up under
# StrictUndefined.
_EMPTY_MAIL_CONTEXT: dict = {
    "subject": "",
    "sender": "",
    "recipients": [],
    "date": None,
}


def _resolve_mail_context(mail_context: dict | None) -> dict:
    """
    Return a fully-populated mail namespace dict, filling any missing keys
    from `_EMPTY_MAIL_CONTEXT` so template access never trips StrictUndefined.
    """
    if not mail_context:
        return dict(_EMPTY_MAIL_CONTEXT)
    resolved = dict(_EMPTY_MAIL_CONTEXT)
    resolved.update(mail_context)
    return resolved


_template_environment.filters["datetime"] = format_datetime

_template_environment.filters["slugify"] = django_slugify

_template_environment.filters["localize_date"] = localize_date


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
    "mail",
}


def render_workflow_custom_field_string(
    text: str,
    mail_context: dict | None = None,
) -> str:
    """
    Render a string custom-field value that may contain a Jinja template.

    Only the `mail` namespace is exposed for v1 (see WorkflowAction docstring).
    Raises the underlying jinja2 exception on syntax or security errors so the
    caller can decide how loudly to fail; unlike `parse_w_workflow_placeholders`
    this always returns a string on success (never None) so the caller can
    write the result directly to a value_text column.
    """
    formatting = {"mail": _resolve_mail_context(mail_context)}
    template = _template_environment.from_string(text, template_class=Template)
    return template.render(formatting)


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
    mail_context: dict | None = None,
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

    formatting["mail"] = _resolve_mail_context(mail_context)

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
