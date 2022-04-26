import os
import re
from io import StringIO

import dateutil.parser
import requests
from django.conf import settings
from documents.parsers import DocumentParser
from documents.parsers import make_thumbnail_from_pdf
from documents.parsers import ParseError
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
    _tika_parsed = None

    def get_tika_result(self, document_path):
        if not self._tika_parsed:
            self.log("info", f"Sending {document_path} to Tika server")
            tika_server = settings.PAPERLESS_TIKA_ENDPOINT

            try:
                self._tika_parsed = parser.from_file(
                    document_path,
                    tika_server,
                )
            except Exception as err:
                raise ParseError(
                    f"Could not parse {document_path} with tika server at "
                    f"{tika_server}: {err}",
                )

        return self._tika_parsed

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        if not self.archive_path:
            self.archive_path = self.generate_pdf(document_path)

        return make_thumbnail_from_pdf(
            self.archive_path,
            self.tempdir,
            self.logging_group,
        )

    def extract_metadata(self, document_path, mime_type):
        result = []
        prefix_pattern = re.compile(r"(.*):(.*)")

        try:
            parsed = self.get_tika_result(document_path)
        except ParseError as e:
            self.log(
                "warning",
                f"Error while fetching document metadata for " f"{document_path}: {e}",
            )
            return result

        for key, value in parsed["metadata"].items():
            if isinstance(value, list):
                value = ", ".join([str(e) for e in value])
            value = str(value)
            try:
                m = prefix_pattern.match(key)
                result.append(
                    {
                        "namespace": "",
                        "prefix": m.group(1),
                        "key": m.group(2),
                        "value": value,
                    },
                )
            except AttributeError:
                result.append(
                    {
                        "namespace": "",
                        "prefix": "",
                        "key": key,
                        "value": value,
                    },
                )
            except Exception as e:
                self.log(
                    "warning",
                    f"Error while reading metadata {key}: {value}. Error: " f"{e}",
                )
            result.sort(key=lambda item: (item["prefix"], item["key"]))
        return result

    def parse(self, document_path, mime_type, file_name=None):
        parsed = self.get_tika_result(document_path)

        subject = parsed["metadata"].get("dc:subject", "<no subject>")
        content = parsed["content"].strip()

        if content.startswith(subject):
            content = content[len(subject) :].strip()

        content = re.sub(" +", " ", content)
        content = re.sub("\n+", "\n", content)

        self.text = (
            f"{content}\n\n"
            f"From: {parsed['metadata'].get('Message-From', '')}\n"
            f"To: {parsed['metadata'].get('Message-To', '')}\n"
            f"CC: {parsed['metadata'].get('Message-CC', '')}"
        )

        try:
            self.date = dateutil.parser.isoparse(
                parsed["metadata"]["dcterms:created"],
            )
        except Exception as e:
            self.log(
                "warning",
                f"Unable to extract date for document " f"{document_path}: {e}",
            )

        self.archive_path = self.generate_pdf(document_path)

    def generate_pdf(self, document_path):
        def clean_html(text: str):
            if isinstance(text, list):
                text = ", ".join([str(e) for e in text])
            if type(text) != str:
                text = str(text)
            text = text.replace("&", "&amp;")
            text = text.replace("<", "&lt;")
            text = text.replace(">", "&gt;")
            text = text.replace(" ", "&nbsp;")
            text = text.replace("'", "&apos;")
            text = text.replace('"', "&quot;")
            return text

        parsed = self.get_tika_result(document_path)

        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
        url = gotenberg_server + "/forms/chromium/convert/html"

        self.log("info", f"Converting {document_path} to PDF as {pdf_path}")

        data = {}
        data["subject"] = clean_html(parsed["metadata"].get("dc:subject", ""))
        data["from"] = clean_html(parsed["metadata"].get("Message-From", ""))
        data["to"] = clean_html(parsed["metadata"].get("Message-To", ""))
        data["cc"] = clean_html(parsed["metadata"].get("Message-CC", ""))
        data["date"] = clean_html(parsed["metadata"].get("dcterms:created", ""))

        content = parsed.get("content", "").strip()
        if content.startswith(data["subject"]):
            content = content[len(data["subject"]) :].strip()
        data["content"] = clean_html(content)

        html_file = os.path.join(os.path.dirname(__file__), "mail_template/index.html")
        css_file = os.path.join(os.path.dirname(__file__), "mail_template/output.css")
        placeholder_pattern = re.compile(r"{{(.+)}}")
        html = StringIO()

        with open(html_file, "r") as html_template_handle:
            with open(css_file, "rb") as css_handle:
                for line in html_template_handle.readlines():
                    for placeholder in placeholder_pattern.findall(line):
                        line = re.sub(
                            "{{" + placeholder + "}}",
                            data.get(placeholder.strip(), ""),
                            line,
                        )
                    html.write(line)
                html.seek(0)
                files = {
                    "html": (
                        "index.html",
                        html,
                    ),
                    "css": (
                        "output.css",
                        css_handle,
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
