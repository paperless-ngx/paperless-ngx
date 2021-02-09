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

    logging_name = "paperless.parsing.tika"

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        if not self.archive_path:
            self.archive_path = self.convert_to_pdf(document_path, file_name)

        return make_thumbnail_from_pdf(
            self.archive_path, self.tempdir, self.logging_group)

    def extract_metadata(self, document_path, mime_type):
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT
        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as e:
            self.log("warning", f"Error while fetching document metadata for "
                                f"{document_path}: {e}")
            return []

        return [
            {
                "namespace": "",
                "prefix": "",
                "key": key,
                "value": parsed['metadata'][key]
            } for key in parsed['metadata']
        ]

    def parse(self, document_path, mime_type, file_name=None):
        self.log("info", f"Sending {document_path} to Tika server")
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT

        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at "
                f"{tika_server}: {err}"
            )

        self.text = parsed["content"].strip()

        try:
            self.date = dateutil.parser.isoparse(
                parsed["metadata"]["Creation-Date"])
        except Exception as e:
            self.log("warning", f"Unable to extract date for document "
                                f"{document_path}: {e}")

        self.archive_path = self.convert_to_pdf(document_path, file_name)

    def convert_to_pdf(self, document_path, file_name):
        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
        url = gotenberg_server + "/convert/office"

        self.log("info", f"Converting {document_path} to PDF as {pdf_path}")
        files = {"files": (file_name or os.path.basename(document_path),
                           open(document_path, "rb"))}
        headers = {}

        try:
            response = requests.post(url, files=files, headers=headers)
            response.raise_for_status()  # ensure we notice bad responses
        except Exception as err:
            raise ParseError(
                f"Error while converting document to PDF: {err}"
            )

        file = open(pdf_path, "wb")
        file.write(response.content)
        file.close()

        return pdf_path
