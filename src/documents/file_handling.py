import os
from pathlib import Path

from django.conf import settings

from documents.models import Document
from documents.templating.filepath import validate_filepath_template_and_render
from documents.templating.utils import convert_format_str_to_template_format


def create_source_path_directory(source_path: Path) -> None:
    source_path.parent.mkdir(parents=True, exist_ok=True)


def delete_empty_directories(directory: Path, root: Path) -> None:
    if not directory.is_dir():
        return

    if not directory.is_relative_to(root):
        # don't do anything outside our originals folder.

        # append os.path.set so that we avoid these cases:
        #   directory = /home/originals2/test
        #   root = /home/originals ("/" gets appended and startswith fails)
        return

    # Go up in the directory hierarchy and try to delete all directories
    while directory != root:
        if not list(directory.iterdir()):
            # it's empty
            try:
                directory.rmdir()
            except OSError:
                # whatever. empty directories aren't that bad anyway.
                return
        else:
            # it's not empty.
            return

        # go one level up
        directory = directory.parent


def generate_unique_filename(doc, *, archive_filename=False) -> Path:
    """
    Generates a unique filename for doc in settings.ORIGINALS_DIR.

    The returned filename is guaranteed to be either the current filename
    of the document if unchanged, or a new filename that does not correspondent
    to any existing files. The function will append _01, _02, etc to the
    filename before the extension to avoid conflicts.

    If archive_filename is True, return a unique archive filename instead.

    """
    if archive_filename:
        old_filename: Path | None = (
            Path(doc.archive_filename) if doc.archive_filename else None
        )
        root = settings.ARCHIVE_DIR
    else:
        old_filename = Path(doc.filename) if doc.filename else None
        root = settings.ORIGINALS_DIR

    # If generating archive filenames, try to make a name that is similar to
    # the original filename first.

    if archive_filename and doc.filename:
        # Generate the full path using the same logic as generate_filename
        base_generated = generate_filename(doc, archive_filename=archive_filename)

        # Try to create a simple PDF version based on the original filename
        # but preserve any directory structure from the template
        if str(base_generated.parent) != ".":
            # Has directory structure, preserve it
            simple_pdf_name = base_generated.parent / (Path(doc.filename).stem + ".pdf")
        else:
            # No directory structure
            simple_pdf_name = Path(Path(doc.filename).stem + ".pdf")

        if simple_pdf_name == old_filename or not (root / simple_pdf_name).exists():
            return simple_pdf_name

    counter = 0

    while True:
        new_filename = generate_filename(
            doc,
            counter=counter,
            archive_filename=archive_filename,
        )
        if new_filename == old_filename:
            # still the same as before.
            return new_filename

        if (root / new_filename).exists():
            counter += 1
        else:
            return new_filename


def format_filename(document: Document, template_str: str) -> str | None:
    rendered_filename = validate_filepath_template_and_render(
        template_str,
        document,
    )
    if rendered_filename is None:
        return None

    # Apply this setting.  It could become a filter in the future (or users could use |default)
    if settings.FILENAME_FORMAT_REMOVE_NONE:
        rendered_filename = rendered_filename.replace("/-none-/", "/")
        rendered_filename = rendered_filename.replace(" -none-", "")
        rendered_filename = rendered_filename.replace("-none-", "")
        rendered_filename = rendered_filename.strip(os.sep)

    rendered_filename = rendered_filename.replace(
        "-none-",
        "none",
    )  # backward compatibility

    return rendered_filename


def generate_filename(
    doc: Document,
    *,
    counter=0,
    archive_filename=False,
) -> Path:
    base_path: Path | None = None

    # Determine the source of the format string
    if doc.storage_path is not None:
        filename_format = doc.storage_path.path
    elif settings.FILENAME_FORMAT is not None:
        # Maybe convert old to new style
        filename_format = convert_format_str_to_template_format(
            settings.FILENAME_FORMAT,
        )
    else:
        filename_format = None

    # If we have one, render it
    if filename_format is not None:
        rendered_path: str | None = format_filename(doc, filename_format)
        if rendered_path:
            base_path = Path(rendered_path)

    counter_str = f"_{counter:02}" if counter else ""
    filetype_str = ".pdf" if archive_filename else doc.file_type

    if base_path:
        # Split the path into directory and filename parts
        directory = base_path.parent
        # Use the full name (not just stem) as the base filename
        base_filename = base_path.name

        # Build the final filename with counter and filetype
        final_filename = f"{base_filename}{counter_str}{filetype_str}"

        # If we have a directory component, include it
        if str(directory) != ".":
            full_path = directory / final_filename
        else:
            full_path = Path(final_filename)
    else:
        # No template, use document ID
        final_filename = f"{doc.pk:07}{counter_str}{filetype_str}"
        full_path = Path(final_filename)

    return full_path
