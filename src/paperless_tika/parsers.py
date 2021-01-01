import os
import requests
import dateutil.parser

from django.conf import settings

from documents.parsers import DocumentParser, ParseError, \
    make_thumbnail_from_pdf
from tika import parser


class TikaDocumentParser(DocumentParser):
    """
    This parser sends documents to a local tika server
    """

    def get_thumbnail(self, document_path, mime_type):
        if not self.archive_path:
            self.archive_path = self.convert_to_pdf(document_path)

        return make_thumbnail_from_pdf(
            self.archive_path, self.tempdir, self.logging_group)

    def parse(self, document_path, mime_type):
        self.log("info", f"[TIKA_PARSE] Sending {document_path} to Tika server")
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT

        try:
            parsed = parser.from_file(document_path, tika_server)
        except requests.exceptions.HTTPError as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at {tika_server}: {err}"
            )

        try:
            self.text = parsed["content"].strip()
        except:
            pass

        try:
            self.date = dateutil.parser.isoparse(parsed["metadata"]["Creation-Date"])
        except:
            pass

        self.archive_path = self.convert_to_pdf(document_path)

    def convert_to_pdf(self, document_path):
        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
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

        return pdf_path
