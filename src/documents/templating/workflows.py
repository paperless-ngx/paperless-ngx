import logging
import re

# from babel.dates import format_date, format_time, format_datetime
from datetime import date
from datetime import datetime
from pathlib import Path

from django.utils.text import slugify as django_slugify
from jinja2 import StrictUndefined
from jinja2 import Template
from jinja2 import TemplateSyntaxError
from jinja2 import UndefinedError
from jinja2 import make_logging_undefined
from jinja2.sandbox import SandboxedEnvironment
from jinja2.sandbox import SecurityError

from documents.templating.utils import format_datetime
from documents.templating.utils import get_cf_value
from documents.templating.utils import localize_date

logger = logging.getLogger("paperless.templating")

_LogStrictUndefined = make_logging_undefined(logger, StrictUndefined)


class TitleEnvironment(SandboxedEnvironment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.undefined_tracker = None


def is_safe_callable(self, obj):
    # Block access to .save() and .delete() methods
    if callable(obj) and getattr(obj, "__name__", None) in (
        "save",
        "delete",
        "update",
    ):
        return False
    # Call the parent method for other cases
    return super().is_safe_callable(obj)


class TileTemplate(Template):
    def render(self, *args, **kwargs) -> str:
        return super().render(*args, **kwargs)


_template_environment = TitleEnvironment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
    extensions=["jinja2.ext.loopcontrols"],
    undefined=_LogStrictUndefined,
)

_template_environment.filters["get_cf_value"] = get_cf_value

_template_environment.filters["datetime"] = format_datetime

_template_environment.filters["slugify"] = django_slugify

_template_environment.filters["localize_date"] = localize_date


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

    if re.search(r"\{\{.*\}\}", text) or re.search(r"{\%.*\%\}", text):
        # Try rendering the template
        logger.info(f"Jinja Template is : {text}")
        try:
            template = _template_environment.from_string(
                text,
                template_class=TileTemplate,
            )

            rendered_template = template.render(formatting)

            # We're good!
            return rendered_template
        except UndefinedError:
            # The undefined class logs this already for us
            pass
        except TemplateSyntaxError as e:
            logger.warning(f"Template syntax error in title generation: {e}")
        except SecurityError as e:
            logger.warning(f"Template attempted restricted operation: {e}")
        except Exception as e:
            logger.warning(f"Unknown error in ftitle  generation: {e}")
            logger.warning(
                f"Invalid title format '{text}', workflow not applied: {e}",
            )
        return None
        # django_engine = engines["jinja2"]
        # template = django_engine.from_string(text)

    return text.format(**formatting).strip()
