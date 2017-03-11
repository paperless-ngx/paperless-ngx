import logging
import shutil
import tempfile

from django.conf import settings


class ParseError(Exception):
    pass


class DocumentParser(object):
    """
    Subclass this to make your own parser.  Have a look at
    `paperless_tesseract.parsers` for inspiration.
    """

    SCRATCH = settings.SCRATCH_DIR

    def __init__(self, path):
        self.document_path = path
        self.tempdir = tempfile.mkdtemp(prefix="paperless", dir=self.SCRATCH)
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

    def log(self, level, message):
        getattr(self.logger, level)(message, extra={
            "group": self.logging_group
        })

    def cleanup(self):
        self.log("debug", "Deleting directory {}".format(self.tempdir))
        shutil.rmtree(self.tempdir)
