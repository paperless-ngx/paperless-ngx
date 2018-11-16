import os
import subprocess

from django.conf import settings

from documents.parsers import DocumentParser, ParseError


class TextDocumentParser(DocumentParser):
    """
    This parser directly parses a text document (.txt, .md, or .csv)
    """

    CONVERT = settings.CONVERT_BINARY
    THREADS = int(settings.OCR_THREADS) if settings.OCR_THREADS else None
    UNPAPER = settings.UNPAPER_BINARY
    DEFAULT_OCR_LANGUAGE = settings.OCR_LANGUAGE
    OCR_ALWAYS = settings.OCR_ALWAYS

    def __init__(self, path):
        super().__init__(path)
        self._text = None

    def get_thumbnail(self):
        """
        The thumbnail of a text file is just a 500px wide image of the text
        rendered onto a letter-sized page.
        """
        # The below is heavily cribbed from https://askubuntu.com/a/590951

        bg_color = "white"  # bg color
        text_color = "black"  # text color
        psize = [500, 647]  # icon size
        n_lines = 50  # number of lines to show
        out_path = os.path.join(self.tempdir, "convert.png")

        temp_bg = os.path.join(self.tempdir, "bg.png")
        temp_txlayer = os.path.join(self.tempdir, "tx.png")
        picsize = "x".join([str(n) for n in psize])
        txsize = "x".join([str(n - 8) for n in psize])

        def create_bg():
            work_size = ",".join([str(n - 1) for n in psize])
            r = str(round(psize[0] / 10))
            rounded = ",".join([r, r])
            run_command(
                self.CONVERT,
                "-size ", picsize,
                ' xc:none -draw ',
                '"fill ', bg_color, ' roundrectangle 0,0,', work_size, ",", rounded, '" ',  # NOQA: E501
                temp_bg
            )

        def read_text():
            with open(self.document_path, 'r') as src:
                lines = [l.strip() for l in src.readlines()]
                text = "\n".join([l for l in lines[:n_lines]])
                return text.replace('"', "'")

        def create_txlayer():
            run_command(
                self.CONVERT,
                "-background none",
                "-fill",
                text_color,
                "-pointsize", "12",
                "-border 4 -bordercolor none",
                "-size ", txsize,
                ' caption:"', read_text(), '" ',
                temp_txlayer
            )

        create_txlayer()
        create_bg()
        run_command(
            self.CONVERT,
            temp_bg,
            temp_txlayer,
            "-background None -layers merge ",
            out_path
        )

        return out_path

    def get_text(self):

        if self._text is not None:
            return self._text

        with open(self.document_path, 'r') as f:
            self._text = f.read()

        return self._text


def run_command(*args):
    environment = os.environ.copy()
    if settings.CONVERT_MEMORY_LIMIT:
        environment["MAGICK_MEMORY_LIMIT"] = settings.CONVERT_MEMORY_LIMIT
    if settings.CONVERT_TMPDIR:
        environment["MAGICK_TMPDIR"] = settings.CONVERT_TMPDIR

    if not subprocess.Popen(' '.join(args), env=environment,
                            shell=True).wait() == 0:
        raise ParseError("Convert failed at {}".format(args))
