import os
import re
import subprocess

import dateparser
from django.conf import settings

from documents.parsers import DocumentParser, ParseError


class TextDocumentParser(DocumentParser):
    """
    This parser directly parses a text document (.txt or .md)
    """


    CONVERT = settings.CONVERT_BINARY
    THREADS = int(settings.OCR_THREADS) if settings.OCR_THREADS else None
    UNPAPER = settings.UNPAPER_BINARY
    DATE_ORDER = settings.DATE_ORDER
    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE
    OCR_ALWAYS = settings.OCR_ALWAYS

    def __init__(self, path):
        super().__init__(path)
        self._text = None

    def get_thumbnail(self):
        """
        The thumbnail of a txt is just a 500px wide image of the text
        rendered onto a letter-sized page.
        """

        run_convert(
            self.CONVERT,
            "-size", "500x647",
            "xc:white",
            "-pointsize", "12",
            "-fill", "black",
            "-draw", "\"text 0,12 \'$(cat {})\'\"".format(self.document_path),
            os.path.join(self.tempdir, "convert-txt.png")
        )

        return os.path.join(self.tempdir, "convert-txt.png")

    def get_text(self):

        if self._text is not None:
            return self._text

        with open(self.document_path, 'r') as f:
            self._text = f.read()

        return self._text

    def get_date(self):
        date = None
        datestring = None

        try:
            text = self.get_text()
        except ParseError as e:
            return None

        # This regular expression will try to find dates in the document at
        # hand and will match the following formats:
        # - XX.YY.ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
        # - XX/YY/ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
        # - XX-YY-ZZZZ with XX + YY being 1 or 2 and ZZZZ being 2 or 4 digits
        # - XX. MONTH ZZZZ with XX being 1 or 2 and ZZZZ being 2 or 4 digits
        # - MONTH ZZZZ, with ZZZZ being 4 digits
        # - MONTH XX, ZZZZ with XX being 1 or 2 and ZZZZ being 4 digits
        pattern = re.compile(
            r'\b([0-9]{1,2})[\.\/-]([0-9]{1,2})[\.\/-]([0-9]{4}|[0-9]{2})\b|' +
            r'\b([0-9]{1,2}[\. ]+[^ ]{3,9} ([0-9]{4}|[0-9]{2}))\b|' +
            r'\b([^\W\d_]{3,9} [0-9]{1,2}, ([0-9]{4}))\b|' +
            r'\b([^\W\d_]{3,9} [0-9]{4})\b')

        # Iterate through all regex matches and try to parse the date
        for m in re.finditer(pattern, text):
            datestring = m.group(0)

            try:
                date = dateparser.parse(
                           datestring,
                           settings={'DATE_ORDER': self.DATE_ORDER,
                                     'PREFER_DAY_OF_MONTH': 'first',
                                     'RETURN_AS_TIMEZONE_AWARE': True})
            except TypeError:
                # Skip all matches that do not parse to a proper date
                continue

            if date is not None:
                break

        if date is not None:
            self.log("info", "Detected document date " + date.isoformat() +
                             " based on string " + datestring)
        else:
            self.log("info", "Unable to detect date for document")

        return date


def run_convert(*args):
    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    if not subprocess.Popen(args, env=environment).wait() == 0:
        raise ParseError("Convert failed at {}".format(args))