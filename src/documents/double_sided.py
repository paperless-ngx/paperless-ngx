import datetime as dt
import logging
import os
import shutil
from pathlib import Path

from django.conf import settings
from pikepdf import Pdf

from documents.consumer import ConsumerError
from documents.converters import convert_from_tiff_to_pdf
from documents.data_models import ConsumableDocument

logger = logging.getLogger("paperless.double_sided")

# Hardcoded for now, could be made a configurable setting if needed
TIMEOUT_MINUTES = 30

# Used by test cases
STAGING_FILE_NAME = "double-sided-staging.pdf"


def collate(input_doc: ConsumableDocument) -> str:
    """
    Tries to collate pages from 2 single sided scans of a double sided
    document.

    When called with a file, it checks whether or not a staging file
    exists, if not, the current file is turned into that staging file
    containing the odd numbered pages.

    If a staging file exists, and it is not too old, the current file is
    considered to be the second part (the even numbered pages) and it will
    collate the pages of both, the pages of the second file will be added
    in reverse order, since the ADF will have scanned the pages from bottom
    to top.

    Returns a status message on success, or raises a ConsumerError
    in case of failure.
    """

    # Make sure scratch dir exists, Consumer might not have run yet
    settings.SCRATCH_DIR.mkdir(exist_ok=True)

    if input_doc.mime_type == "application/pdf":
        pdf_file = input_doc.original_file
    elif (
        input_doc.mime_type == "image/tiff"
        and settings.CONSUMER_COLLATE_DOUBLE_SIDED_TIFF_SUPPORT
    ):
        pdf_file = convert_from_tiff_to_pdf(
            input_doc.original_file,
            settings.SCRATCH_DIR,
        )
        input_doc.original_file.unlink()
    else:
        raise ConsumerError("Unsupported file type for collation of double-sided scans")

    staging = settings.SCRATCH_DIR / STAGING_FILE_NAME

    valid_staging_exists = False
    if staging.exists():
        stats = os.stat(str(staging))
        # if the file is older than the timeout, we don't consider
        # it valid
        if dt.datetime.now().timestamp() - stats.st_mtime > TIMEOUT_MINUTES * 60:
            logger.warning("Outdated double sided staging file exists, deleting it")
            os.unlink(str(staging))
        else:
            valid_staging_exists = True

    if valid_staging_exists:
        try:
            # Collate pages from second PDF in reverse order
            with Pdf.open(staging) as pdf1, Pdf.open(pdf_file) as pdf2:
                pdf2.pages.reverse()
                try:
                    for i, page in enumerate(pdf2.pages):
                        pdf1.pages.insert(2 * i + 1, page)
                except IndexError:
                    raise ConsumerError(
                        "This second file (even numbered pages) contains more "
                        "pages than the first/odd numbered one. This means the "
                        "two uploaded files don't belong to the same double-"
                        "sided scan. Please retry, starting with the odd "
                        "numbered pages again.",
                    )
                # Merged file has the same path, but without the
                # double-sided subdir. Therefore, it is also in the
                # consumption dir and will be picked up for processing
                old_file = input_doc.original_file
                new_file = Path(
                    *(
                        part
                        for part in old_file.with_name(
                            f"{old_file.stem}-collated.pdf",
                        ).parts
                        if part != settings.CONSUMER_COLLATE_DOUBLE_SIDED_SUBDIR_NAME
                    ),
                )
                # If the user didn't create the subdirs yet, do it for them
                new_file.parent.mkdir(parents=True, exist_ok=True)
                pdf1.save(new_file)
            logger.info("Collated documents into new file %s", new_file)
            return (
                "Success. Even numbered pages of double sided scan collated "
                "with odd pages"
            )
        finally:
            # Delete staging and recently uploaded file no matter what.
            # If any error occurs, the user needs to be able to restart
            # the process from scratch; after all, the staging file
            # with the odd numbered pages might be the culprit
            pdf_file.unlink()
            staging.unlink()

    else:
        shutil.move(pdf_file, staging)
        # update access to modification time so we know if the file
        # is outdated when another file gets uploaded
        os.utime(staging, (dt.datetime.now().timestamp(),) * 2)
        logger.info(
            "Got scan with odd numbered pages of double-sided scan, moved it to %s",
            staging,
        )
        return (
            "Received odd numbered pages of double sided scan, waiting up to "
            f"{TIMEOUT_MINUTES} minutes for even numbered pages"
        )
