import logging
import os
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import PurePath

import pathvalidate
from django.utils import timezone
from django.utils.dateparse import parse_date
from jinja2 import StrictUndefined
from jinja2 import Template
from jinja2 import TemplateSyntaxError
from jinja2 import UndefinedError
from jinja2 import make_logging_undefined
from jinja2.sandbox import SandboxedEnvironment
from jinja2.sandbox import SecurityError

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag

logger = logging.getLogger("paperless.templating")

_LogStrictUndefined = make_logging_undefined(logger, StrictUndefined)


class FilePathEnvironment(SandboxedEnvironment):
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


_template_environment = FilePathEnvironment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=False,
    autoescape=False,
    extensions=["jinja2.ext.loopcontrols"],
    undefined=_LogStrictUndefined,
)


class FilePathTemplate(Template):
    def render(self, *args, **kwargs) -> str:
        def clean_filepath(value: str) -> str:
            """
            Clean up a filepath by:
            1. Removing newlines and carriage returns
            2. Removing extra spaces before and after forward slashes
            3. Preserving spaces in other parts of the path
            """
            value = value.replace("\n", "").replace("\r", "")
            value = re.sub(r"\s*/\s*", "/", value)

            # We remove trailing and leading separators, as these are always relative paths, not absolute, even if the user
            # tries
            return value.strip().strip(os.sep)

        original_render = super().render(*args, **kwargs)

        return clean_filepath(original_render)


def get_cf_value(
    custom_field_data: dict[str, dict[str, str]],
    name: str,
    default: str | None = None,
) -> str | None:
    if name in custom_field_data and custom_field_data[name]["value"] is not None:
        return custom_field_data[name]["value"]
    elif default is not None:
        return default
    return None


_template_environment.filters["get_cf_value"] = get_cf_value


def format_datetime(value: str | datetime, format: str) -> str:
    if isinstance(value, str):
        value = parse_date(value)
    return value.strftime(format=format)


_template_environment.filters["datetime"] = format_datetime


def create_dummy_document():
    """
    Create a dummy Document instance with all possible fields filled
    """
    # Populate the document with representative values for every field
    dummy_doc = Document(
        pk=1,
        title="Sample Title",
        correspondent=Correspondent(name="Sample Correspondent"),
        storage_path=StoragePath(path="/dummy/path"),
        document_type=DocumentType(name="Sample Type"),
        content="This is some sample document content.",
        mime_type="application/pdf",
        checksum="dummychecksum12345678901234567890123456789012",
        archive_checksum="dummyarchivechecksum123456789012345678901234",
        page_count=5,
        created=timezone.now(),
        modified=timezone.now(),
        storage_type=Document.STORAGE_TYPE_UNENCRYPTED,
        added=timezone.now(),
        filename="/dummy/filename.pdf",
        archive_filename="/dummy/archive_filename.pdf",
        original_filename="original_file.pdf",
        archive_serial_number=12345,
    )
    return dummy_doc


def get_creation_date_context(document: Document) -> dict[str, str]:
    """
    Given a Document, localizes the creation date and builds a context dictionary with some common, shorthand
    formatted values from it
    """
    local_created = timezone.localdate(document.created)

    return {
        "created": local_created.isoformat(),
        "created_year": local_created.strftime("%Y"),
        "created_year_short": local_created.strftime("%y"),
        "created_month": local_created.strftime("%m"),
        "created_month_name": local_created.strftime("%B"),
        "created_month_name_short": local_created.strftime("%b"),
        "created_day": local_created.strftime("%d"),
    }


def get_added_date_context(document: Document) -> dict[str, str]:
    """
    Given a Document, localizes the added date and builds a context dictionary with some common, shorthand
    formatted values from it
    """
    local_added = timezone.localdate(document.added)

    return {
        "added": local_added.isoformat(),
        "added_year": local_added.strftime("%Y"),
        "added_year_short": local_added.strftime("%y"),
        "added_month": local_added.strftime("%m"),
        "added_month_name": local_added.strftime("%B"),
        "added_month_name_short": local_added.strftime("%b"),
        "added_day": local_added.strftime("%d"),
    }


def get_basic_metadata_context(
    document: Document,
    *,
    no_value_default: str,
) -> dict[str, str]:
    """
    Given a Document, constructs some basic information about it.  If certain values are not set,
    they will be replaced with the no_value_default.

    Regardless of set or not, the values will be sanitized
    """
    return {
        "title": pathvalidate.sanitize_filename(
            document.title,
            replacement_text="-",
        ),
        "correspondent": pathvalidate.sanitize_filename(
            document.correspondent.name,
            replacement_text="-",
        )
        if document.correspondent
        else no_value_default,
        "document_type": pathvalidate.sanitize_filename(
            document.document_type.name,
            replacement_text="-",
        )
        if document.document_type
        else no_value_default,
        "asn": str(document.archive_serial_number)
        if document.archive_serial_number
        else no_value_default,
        "owner_username": document.owner.username
        if document.owner
        else no_value_default,
        "original_name": PurePath(document.original_filename).with_suffix("").name
        if document.original_filename
        else no_value_default,
        "doc_pk": f"{document.pk:07}",
    }


def get_tags_context(tags: Iterable[Tag]) -> dict[str, str | list[str]]:
    """
    Given an Iterable of tags, constructs some context from them for usage
    """
    return {
        "tag_list": pathvalidate.sanitize_filename(
            ",".join(
                sorted(tag.name for tag in tags),
            ),
            replacement_text="-",
        ),
        # Assumed to be ordered, but a template could loop through to find what they want
        "tag_name_list": [x.name for x in tags],
    }


def get_custom_fields_context(
    custom_fields: Iterable[CustomFieldInstance],
) -> dict[str, dict[str, dict[str, str]]]:
    """
    Given an Iterable of CustomFieldInstance, builds a dictionary mapping the field name
    to its type and value
    """
    field_data = {"custom_fields": {}}
    for field_instance in custom_fields:
        type_ = pathvalidate.sanitize_filename(
            field_instance.field.data_type,
            replacement_text="-",
        )
        if field_instance.value is None:
            value = None
        # String types need to be sanitized
        elif field_instance.field.data_type in {
            CustomField.FieldDataType.MONETARY,
            CustomField.FieldDataType.STRING,
            CustomField.FieldDataType.URL,
        }:
            value = pathvalidate.sanitize_filename(
                field_instance.value,
                replacement_text="-",
            )
        elif (
            field_instance.field.data_type == CustomField.FieldDataType.SELECT
            and field_instance.field.extra_data["select_options"] is not None
        ):
            options = field_instance.field.extra_data["select_options"]
            value = pathvalidate.sanitize_filename(
                options[int(field_instance.value)],
                replacement_text="-",
            )
        else:
            value = field_instance.value
        field_data["custom_fields"][
            pathvalidate.sanitize_filename(
                field_instance.field.name,
                replacement_text="-",
            )
        ] = {
            "type": type_,
            "value": value,
        }
    return field_data


def validate_filepath_template_and_render(
    template_string: str,
    document: Document | None = None,
) -> str | None:
    """
    Renders the given template string using either the given Document or using a dummy Document and data

    Returns None if the string is not valid or an error occurred, otherwise
    """

    # Create the dummy document object with all fields filled in for validation purposes
    if document is None:
        document = create_dummy_document()
        tags_list = [Tag(name="Test Tag 1"), Tag(name="Another Test Tag")]
        custom_fields = [
            CustomFieldInstance(
                field=CustomField(
                    name="Text Custom Field",
                    data_type=CustomField.FieldDataType.STRING,
                ),
                value_text="Some String Text",
            ),
        ]
    else:
        # or use the real document information
        tags_list = document.tags.order_by("name").all()
        custom_fields = CustomFieldInstance.global_objects.filter(document=document)

    # Build the context dictionary
    context = (
        {"document": document}
        | get_basic_metadata_context(document, no_value_default="-none-")
        | get_creation_date_context(document)
        | get_added_date_context(document)
        | get_tags_context(tags_list)
        | get_custom_fields_context(custom_fields)
    )

    # Try rendering the template
    try:
        # We load the custom tag used to remove spaces and newlines from the final string around the user string
        template = _template_environment.from_string(
            template_string,
            template_class=FilePathTemplate,
        )
        rendered_template = template.render(context)

        # We're good!
        return rendered_template
    except UndefinedError:
        # The undefined class logs this already for us
        pass
    except TemplateSyntaxError as e:
        logger.warning(f"Template syntax error in filename generation: {e}")
    except SecurityError as e:
        logger.warning(f"Template attempted restricted operation: {e}")
    except Exception as e:
        logger.warning(f"Unknown error in filename generation: {e}")
        logger.warning(
            f"Invalid filename_format '{template_string}', falling back to default",
        )
    return None
