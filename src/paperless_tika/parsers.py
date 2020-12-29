import os
import subprocess
import tika
import requests
import dateutil.parser

from PIL import ImageDraw, ImageFont, Image
from django.conf import settings

from documents.parsers import DocumentParser, ParseError, run_convert
from paperless_tesseract.parsers import RasterisedDocumentParser
from tika import parser


class TikaDocumentParser(DocumentParser):
    """
    This parser sends documents to a local tika server
    """

    def get_thumbnail(self, document_path, mime_type):
        self.log("info", f"[TIKA_THUMB] Generating thumbnail for{document_path}")
        archive_path = self.archive_path

        out_path = os.path.join(self.tempdir, "convert.png")

        # Run convert to get a decent thumbnail
        try:
            run_convert(
                density=300,
                scale="500x5000>",
                alpha="remove",
                strip=True,
                trim=False,
                input_file="{}[0]".format(archive_path),
                output_file=out_path,
                logging_group=self.logging_group,
            )
        except ParseError:
            # if convert fails, fall back to extracting
            # the first PDF page as a PNG using Ghostscript
            self.log(
                "warning",
                "Thumbnail generation with ImageMagick failed, falling back "
                "to ghostscript. Check your /etc/ImageMagick-x/policy.xml!",
            )
            gs_out_path = os.path.join(self.tempdir, "gs_out.png")
            cmd = [
                settings.GS_BINARY,
                "-q",
                "-sDEVICE=pngalpha",
                "-o",
                gs_out_path,
                archive_path,
            ]
            if not subprocess.Popen(cmd).wait() == 0:
                raise ParseError("Thumbnail (gs) failed at {}".format(cmd))
            # then run convert on the output from gs
            run_convert(
                density=300,
                scale="500x5000>",
                alpha="remove",
                strip=True,
                trim=False,
                input_file=gs_out_path,
                output_file=out_path,
                logging_group=self.logging_group,
            )

        return out_path

    def parse(self, document_path, mime_type):
        self.log("info", f"[TIKA_PARSE] Sending {document_path} to Tika server")

        try:
            parsed = parser.from_file(document_path)
        except requests.exceptions.HTTPError as err:
            raise ParseError(f"Could not parse {document_path} with tika server: {err}")

        try:
            content = parsed["content"].strip()
        except:
            content = ""

        try:
            creation_date = dateutil.parser.isoparse(
                parsed["metadata"]["Creation-Date"]
            )
        except:
            creation_date = None

        archive_path = os.path.join(self.tempdir, "convert.pdf")
        convert_to_pdf(self, document_path, archive_path)

        self.archive_path = archive_path
        self.date = creation_date
        self.text = content


def convert_to_pdf(self, document_path, pdf_path):
    pdf_path = os.path.join(self.tempdir, "convert.pdf")
    gotenberg_server = settings.GOTENBERG_SERVER_ENDPOINT
    url = gotenberg_server + "/convert/office"

    self.log("info", f"[TIKA] Converting {document_path} to PDF as {pdf_path}")
    files = {"files": open(document_path, "rb")}
    headers = {}

    try:
        response = requests.post(url, files=files, headers=headers)
        response.raise_for_status()  # ensure we notice bad responses
    except requests.exceptions.HTTPError as err:
        raise ParseError(
            f"Could not contact gotenberg server at {gotenberg_server}: {err}"
        )

    file = open(pdf_path, "wb")
    file.write(response.content)
    file.close()
