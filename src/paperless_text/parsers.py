import os
import re
import subprocess

import dateparser
from django.conf import settings

from documents.parsers import DocumentParser, ParseError, pattern


class TextDocumentParser(DocumentParser):
    """
    This parser directly parses a text document (.txt, .md, or .csv)
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
        # The below is heavily cribbed from https://askubuntu.com/a/590951

        bg_color = "white"  # bg color
        text_color = "black"  # text color
        psize = [500, 647]  # icon size
        n_lines = 50  # number of lines to show
        output_file = os.path.join(self.tempdir, "convert-txt.png")

        temp_bg = os.path.join(self.tempdir, "bg.png")
        temp_txlayer = os.path.join(self.tempdir, "tx.png")
        picsize = "x".join([str(n) for n in psize])
        txsize = "x".join([str(n - 8) for n in psize])

        def create_bg():
            work_size = ",".join([str(n - 1) for n in psize])
            r = str(round(psize[0] / 10));
            rounded = ",".join([r, r])
            run_command(self.CONVERT, "-size ", picsize, ' xc:none -draw ',
                        '"fill ', bg_color, ' roundrectangle 0,0,',
                        work_size, ",", rounded, '" ', temp_bg)

        def read_text():
            with open(self.document_path, 'r') as src:
                lines = [l.strip() for l in src.readlines()]
                text = "\n".join([l for l in lines[:n_lines]])
                return text.replace('"', "'")

        def create_txlayer():
            run_command(self.CONVERT,
                        "-background none",
                        "-fill",
                        text_color,
                        "-pointsize", "12",
                        "-border 4 -bordercolor none",
                        "-size ", txsize,
                        ' caption:"', read_text(), '" ',
                        temp_txlayer)

        create_txlayer()
        create_bg()
        run_command(self.CONVERT, temp_bg, temp_txlayer,
                    "-background None -layers merge ", output_file)

        return output_file

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


def run_command(*args):
    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    if not subprocess.Popen(' '.join(args), env=environment,
                            shell=True).wait() == 0:
        raise ParseError("Convert failed at {}".format(args))