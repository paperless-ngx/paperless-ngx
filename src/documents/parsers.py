import logging
import shutil
import tempfile
import re

from django.conf import settings

# This regular expression will try to find dates in the document at
# hand and will match the following formats:
# - XX.YY.ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX/YY/ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX-YY-ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
# - XX. MONTH ZZZZ with XX being 1 or 2 and ZZZZ being 2 or 4 digits
# - MONTH ZZZZ, with ZZZZ being 4 digits
# - MONTH XX, ZZZZ with XX being 1 or 2 and ZZZZ being 4 digits
DATE_REGEX = re.compile(
    r'\b([0-9]{1,2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{4}|[0-9]{2})\b|' +
    r'\b([0-9]{1,2}[\. ]+[^ ]{3,9} ([0-9]{4}|[0-9]{2}))\b|' +
    r'\b([^\W\d_]{3,9} [0-9]{1,2}, ([0-9]{4}))\b|' +
    r'\b([^\W\d_]{3,9} [0-9]{4})\b'
)


class ParseError(Exception):
    pass


class DocumentParser:
    """
    Subclass this to make your own parser.  Have a look at
    `paperless_tesseract.parsers` for inspiration.
    """

    SCRATCH = settings.SCRATCH_DIR

    def __init__(self, path):
        self.document_path = path
        self.tempdir = tempfile.mkdtemp(prefix="paperless-", dir=self.SCRATCH)
        self.logger = logging.getLogger(__name__)
        self.logging_group = None

    def get_thumbnail(self):
        """
        Returns the path to a file we can use as a thumbnail for this document.
        """
        raise NotImplementedError()

    def get_text(self):
        """
        Returns the text from the document and only the text.
        """
        raise NotImplementedError()

    def get_date(self):
        """
        Returns the date of the document.
        """
        raise NotImplementedError()

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    def cleanup(self):
        self.log("debug", "Deleting directory {}".format(self.tempdir))
        shutil.rmtree(self.tempdir)
