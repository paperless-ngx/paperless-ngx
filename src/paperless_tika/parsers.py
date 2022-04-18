import os
import re
from io import StringIO

import dateutil.parser
import requests
from django.conf import settings
from documents.parsers import DocumentParser
from documents.parsers import make_thumbnail_from_pdf
from documents.parsers import ParseError
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
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
            self.archive_path,
            self.tempdir,
            self.logging_group,
        )

    def extract_metadata(self, document_path, mime_type):
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT
        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as e:
            self.log(
                "warning",
                f"Error while fetching document metadata for " f"{document_path}: {e}",
            )
            return []

        return [
            {
                "namespace": "",
                "prefix": "",
                "key": key,
                "value": parsed["metadata"][key],
            }
            for key in parsed["metadata"]
        ]

    def parse(self, document_path, mime_type, file_name=None):
        self.log("info", f"Sending {document_path} to Tika server")
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT

        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at "
                f"{tika_server}: {err}",
            )

        self.text = parsed["content"].strip()

        try:
            self.date = dateutil.parser.isoparse(parsed["metadata"]["Creation-Date"])
        except Exception as e:
            self.log(
                "warning",
                f"Unable to extract date for document " f"{document_path}: {e}",
            )

        self.archive_path = self.convert_to_pdf(document_path, file_name)

    def convert_to_pdf(self, document_path, file_name):
        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
        url = gotenberg_server + "/forms/libreoffice/convert"

        self.log("info", f"Converting {document_path} to PDF as {pdf_path}")
        with open(document_path, "rb") as document_handle:
            files = {
                "files": (
                    file_name or os.path.basename(document_path),
                    document_handle,
                ),
            }
            headers = {}

            try:
                response = requests.post(url, files=files, headers=headers)
                response.raise_for_status()  # ensure we notice bad responses
            except Exception as err:
                raise ParseError(f"Error while converting document to PDF: {err}")

        with open(pdf_path, "wb") as file:
            file.write(response.content)
            file.close()

        return pdf_path


class TikaDocumentParserEml(DocumentParser):
    """
    This parser sends documents to a local tika server
    """

    logging_name = "paperless.parsing.tikaeml"

    def get_thumbnail(self, document_path, mime_type, file_name=None):

        img = Image.new("RGB", (500, 700), color="white")
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype(
            font=settings.THUMBNAIL_FONT_NAME,
            size=20,
            layout_engine=ImageFont.LAYOUT_BASIC,
        )
        draw.text((5, 5), self.text, font=font, fill="black")

        out_path = os.path.join(self.tempdir, "thumb.png")
        img.save(out_path)

        return out_path

    def extract_metadata(self, document_path, mime_type):
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT
        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as e:
            self.log(
                "warning",
                f"Error while fetching document metadata for " f"{document_path}: {e}",
            )
            return []

        return [
            {
                "namespace": "",
                "prefix": "",
                "key": key,
                "value": parsed["metadata"][key],
            }
            for key in parsed["metadata"]
        ]

    def parse(self, document_path, mime_type, file_name=None):
        self.log("info", f"Sending {document_path} to Tika server")
        tika_server = settings.PAPERLESS_TIKA_ENDPOINT

        try:
            parsed = parser.from_file(document_path, tika_server)
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at "
                f"{tika_server}: {err}",
            )

        text = re.sub(" +", " ", str(parsed))
        text = re.sub("\n+", "\n", text)
        self.text = text

        print(text)

        try:
            self.date = dateutil.parser.isoparse(parsed["metadata"]["Creation-Date"])
        except Exception as e:
            self.log(
                "warning",
                f"Unable to extract date for document " f"{document_path}: {e}",
            )

        md_path = self.convert_to_md(document_path, file_name)
        self.archive_path = self.convert_md_to_pdf(md_path)

    def convert_md_to_pdf(self, md_path):
        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
        url = gotenberg_server + "/forms/chromium/convert/markdown"

        self.log("info", f"Converting {md_path} to PDF as {pdf_path}")
        html = StringIO(
            """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>My PDF</title>
  </head>
  <body>
    {{ toHTML "convert.md" }}
  </body>
</html>
        """,
        )
        md = StringIO(
            """
# Subject

blub  \nblah
blib
        """,
        )

        files = {
            "md": (
                os.path.basename(md_path),
                md,
            ),
            "html": (
                "index.html",
                html,
            ),
        }
        headers = {}

        try:
            response = requests.post(url, files=files, headers=headers)
            response.raise_for_status()  # ensure we notice bad responses
        except Exception as err:
            raise ParseError(f"Error while converting document to PDF: {err}")

        with open(pdf_path, "wb") as file:
            file.write(response.content)
            file.close()

        return pdf_path

    def convert_to_md(self, document_path, file_name):
        md_path = os.path.join(self.tempdir, "convert.md")

        self.log("info", f"Converting {document_path} to markdown as {md_path}")

        with open(md_path, "w") as file:
            md = [
                "# Subject",
                "\n\n",
                "blah",
            ]
            file.writelines(md)
            file.close()

        return md_path
