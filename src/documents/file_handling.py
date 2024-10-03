import logging
import os
import re
from collections.abc import Iterable
from pathlib import PurePath

import pathvalidate
from django.conf import settings
from django.template import Context
from django.template import Engine
from django.utils import timezone

from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.templatetags.filepath import convert_to_django_template_format

logger = logging.getLogger("paperless.filehandling")

INVALID_VARIABLE_STR = "InvalidVarError"

filepath_engine = Engine(
    autoescape=False,
    string_if_invalid=f"{INVALID_VARIABLE_STR}: %s",
    libraries={
        "filepath": "documents.templatetags.filepath",
        "get_cf_value": "documents.templatetags.get_cf_value",
    },
)


def create_source_path_directory(source_path):
    os.makedirs(os.path.dirname(source_path), exist_ok=True)


def delete_empty_directories(directory, root):
    if not os.path.isdir(directory):
        return

    # Go up in the directory hierarchy and try to delete all directories
    directory = os.path.normpath(directory)
    root = os.path.normpath(root)

    if not directory.startswith(root + os.path.sep):
        # don't do anything outside our originals folder.

        # append os.path.set so that we avoid these cases:
        #   directory = /home/originals2/test
        #   root = /home/originals ("/" gets appended and startswith fails)
        return

    while directory != root:
        if not os.listdir(directory):
            # it's empty
            try:
                os.rmdir(directory)
            except OSError:
                # whatever. empty directories aren't that bad anyway.
                return
        else:
            # it's not empty.
            return

        # go one level up
        directory = os.path.normpath(os.path.dirname(directory))


def generate_unique_filename(doc, archive_filename=False):
    """
    Generates a unique filename for doc in settings.ORIGINALS_DIR.

    The returned filename is guaranteed to be either the current filename
    of the document if unchanged, or a new filename that does not correspondent
    to any existing files. The function will append _01, _02, etc to the
    filename before the extension to avoid conflicts.

    If archive_filename is True, return a unique archive filename instead.

    """
    if archive_filename:
        old_filename = doc.archive_filename
        root = settings.ARCHIVE_DIR
    else:
        old_filename = doc.filename
        root = settings.ORIGINALS_DIR

    # If generating archive filenames, try to make a name that is similar to
    # the original filename first.

    if archive_filename and doc.filename:
        new_filename = os.path.splitext(doc.filename)[0] + ".pdf"
        if new_filename == old_filename or not os.path.exists(
            os.path.join(root, new_filename),
        ):
            return new_filename

    counter = 0

    while True:
        new_filename = generate_filename(
            doc,
            counter,
            archive_filename=archive_filename,
        )
        if new_filename == old_filename:
            # still the same as before.
            return new_filename

        if os.path.exists(os.path.join(root, new_filename)):
            counter += 1
        else:
            return new_filename


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
        # String types need to be sanitized
        if field_instance.field.data_type in {
            CustomField.FieldDataType.DOCUMENTLINK,
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


def validate_template_and_render(
    template_string: str,
    document: Document | None = None,
) -> str | None:
    """
    Renders the given template string using either the given Document or using a dummy Document and data

    Returns None if the string is not valid or an error occurred, otherwise
    """

    def detect_undefined_variables(rendered_string: str) -> list[str] | None:
        """
        Checks the rendered template for variables which were not defined/invalid and returns a
        listing of them or None if none were found.

        Used to provide context to the user, rather than mostly failing silently

        """
        pattern = rf"{INVALID_VARIABLE_STR}: ([\w]+(?:[.\s]+[\w]+)*)"
        matches = re.findall(pattern, rendered_string)

        if matches:
            return list(set(matches))
        else:
            return None

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
        custom_fields = document.custom_fields.all()

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
        template = filepath_engine.from_string(
            "{% load filepath %}{% load get_cf_value %}{% filepath %}"
            + template_string
            + "{% endfilepath %}",
        )
        rendered_template = template.render(Context(context))

        # Check for errors
        undefined_vars = detect_undefined_variables(rendered_template)
        if undefined_vars:
            logger.error(f"Template contained {len(undefined_vars)} undefined values:")
            for x in undefined_vars:
                logger.error(f"  Variable '{x}' was undefined")
            return None

        # We're good!
        return rendered_template
    except Exception as e:
        logger.warning(f"Error in filename generation: {e}")
        logger.warning(
            f"Invalid filename_format '{template_string}', falling back to default",
        )
    return None


def generate_filename(
    doc: Document,
    counter=0,
    append_gpg=True,
    archive_filename=False,
):
    path = ""

    def format_filename(document: Document, template_str: str) -> str | None:
        rendered_filename = validate_template_and_render(template_str, document)
        if rendered_filename is None:
            return None

        # Apply this setting.  It could become a filter in the future (or users could use |default)
        if settings.FILENAME_FORMAT_REMOVE_NONE:
            rendered_filename = rendered_filename.replace("/-none-/", "/")
            rendered_filename = rendered_filename.replace(" -none-", "")
            rendered_filename = rendered_filename.replace("-none-", "")

        rendered_filename = rendered_filename.replace(
            "-none-",
            "none",
        )  # backward compatibility

        return rendered_filename

    # Determine the source of the format string
    if doc.storage_path is not None:
        logger.debug(
            f"Document has storage_path {doc.storage_path.pk} "
            f"({doc.storage_path.path}) set",
        )
        filename_format = doc.storage_path.path
    elif settings.FILENAME_FORMAT is not None:
        # Maybe convert old to new style
        filename_format = convert_to_django_template_format(
            settings.FILENAME_FORMAT,
        )
    else:
        filename_format = None

    # If we have one, render it
    if filename_format is not None:
        path = format_filename(doc, filename_format)

    counter_str = f"_{counter:02}" if counter else ""
    filetype_str = ".pdf" if archive_filename else doc.file_type

    if path:
        filename = f"{path}{counter_str}{filetype_str}"
    else:
        filename = f"{doc.pk:07}{counter_str}{filetype_str}"

    if append_gpg and doc.storage_type == doc.STORAGE_TYPE_GPG:
        filename += ".gpg"

    return filename
