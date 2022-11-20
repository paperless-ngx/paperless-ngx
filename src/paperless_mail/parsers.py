import os
import re
from html import escape
from io import BytesIO
from io import StringIO

import requests
from bleach import clean
from bleach import linkify
from django.conf import settings
from documents.parsers import DocumentParser
from documents.parsers import make_thumbnail_from_pdf
from documents.parsers import ParseError
from humanfriendly import format_size
from imap_tools import MailMessage
from tika import parser


class MailDocumentParser(DocumentParser):
    """
    This parser uses imap_tools to parse .eml files, generates pdf using
    gotenbergs and sends the html part to a local tika server for text extraction.
    """

    gotenberg_server = settings.TIKA_GOTENBERG_ENDPOINT
    tika_server = settings.TIKA_ENDPOINT

    logging_name = "paperless.parsing.mail"
    _parsed = None

    def get_parsed(self, document_path) -> MailMessage:
        if not self._parsed:
            try:
                with open(document_path, "rb") as eml:
                    self._parsed = MailMessage.from_bytes(eml.read())
            except Exception as err:
                raise ParseError(
                    f"Could not parse {document_path}: {err}",
                )
            if not self._parsed.from_values:
                self._parsed = None
                raise ParseError(
                    f"Could not parse {document_path}: Missing 'from'",
                )

        return self._parsed

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

        try:
            mail = self.get_parsed(document_path)
        except ParseError as e:
            self.log(
                "warning",
                f"Error while fetching document metadata for " f"{document_path}: {e}",
            )
            return result

        for key, value in mail.headers.items():
            value = ", ".join(i for i in value)

            result.append(
                {
                    "namespace": "",
                    "prefix": "header",
                    "key": key,
                    "value": value,
                },
            )

        result.append(
            {
                "namespace": "",
                "prefix": "",
                "key": "attachments",
                "value": ", ".join(
                    f"{attachment.filename}({(attachment.size / 1024):.2f} KiB)"
                    for attachment in mail.attachments
                ),
            },
        )

        result.append(
            {
                "namespace": "",
                "prefix": "",
                "key": "date",
                "value": mail.date.strftime("%Y-%m-%d %H:%M:%S %Z"),
            },
        )

        result.sort(key=lambda item: (item["prefix"], item["key"]))
        return result

    def parse(self, document_path, mime_type, file_name=None):
        def strip_text(text: str):
            text = re.sub("\t", " ", text)
            text = re.sub(" +", " ", text)
            text = re.sub("(\n *)+", "\n", text)
            return text.strip()

        mail = self.get_parsed(document_path)

        self.text = f"{strip_text(mail.text)}\n\n"
        self.text += f"Subject: {mail.subject}\n\n"
        self.text += f"From: {mail.from_values.full}\n\n"
        self.text += f"To: {', '.join(address.full for address in mail.to_values)}\n\n"
        if len(mail.cc_values) >= 1:
            self.text += (
                f"CC: {', '.join(address.full for address in mail.cc_values)}\n\n"
            )
        if len(mail.bcc_values) >= 1:
            self.text += (
                f"BCC: {', '.join(address.full for address in mail.bcc_values)}\n\n"
            )
        if len(mail.attachments) >= 1:
            att = []
            for a in mail.attachments:
                att.append(f"{a.filename} ({format_size(a.size, binary=True)})")

            self.text += f"Attachments: {', '.join(att)}\n\n"

        if mail.html != "":
            self.text += "HTML content: " + strip_text(self.tika_parse(mail.html))

        self.date = mail.date
        self.archive_path = self.generate_pdf(document_path)

    def tika_parse(self, html: str):
        self.log("info", "Sending content to Tika server")

        try:
            parsed = parser.from_buffer(html, self.tika_server)
        except Exception as err:
            raise ParseError(
                f"Could not parse content with tika server at "
                f"{self.tika_server}: {err}",
            )
        if parsed["content"]:
            return parsed["content"]
        else:
            return ""

    def generate_pdf(self, document_path):
        pdf_collection = []
        url_merge = self.gotenberg_server + "/forms/pdfengines/merge"
        pdf_path = os.path.join(self.tempdir, "merged.pdf")
        mail = self.get_parsed(document_path)

        pdf_collection.append(("1_mail.pdf", self.generate_pdf_from_mail(mail)))

        if mail.html != "":
            pdf_collection.append(
                (
                    "2_html.pdf",
                    self.generate_pdf_from_html(mail.html, mail.attachments),
                ),
            )

        if len(pdf_collection) == 1:
            with open(pdf_path, "wb") as file:
                file.write(pdf_collection[0][1])
                file.close()
            return pdf_path

        files = {}
        for name, content in pdf_collection:
            files[name] = (name, BytesIO(content))
        headers = {}
        try:
            response = requests.post(url_merge, files=files, headers=headers)
            response.raise_for_status()  # ensure we notice bad responses
        except Exception as err:
            raise ParseError(f"Error while converting document to PDF: {err}")

        with open(pdf_path, "wb") as file:
            file.write(response.content)
            file.close()

        return pdf_path

    @staticmethod
    def mail_to_html(mail: MailMessage) -> StringIO:
        data = {}

        def clean_html(text: str):
            if isinstance(text, list):
                text = "\n".join([str(e) for e in text])
            if type(text) != str:
                text = str(text)
            text = escape(text)
            text = clean(text)
            text = linkify(text, parse_email=True)
            text = text.replace("\n", "<br>")
            return text

        data["subject"] = clean_html(mail.subject)
        if data["subject"] != "":
            data["subject_label"] = "Subject"
        data["from"] = clean_html(mail.from_values.full)
        if data["from"] != "":
            data["from_label"] = "From"
        data["to"] = clean_html(", ".join(address.full for address in mail.to_values))
        if data["to"] != "":
            data["to_label"] = "To"
        data["cc"] = clean_html(", ".join(address.full for address in mail.cc_values))
        if data["cc"] != "":
            data["cc_label"] = "CC"
        data["bcc"] = clean_html(", ".join(address.full for address in mail.bcc_values))
        if data["bcc"] != "":
            data["bcc_label"] = "BCC"

        att = []
        for a in mail.attachments:
            att.append(f"{a.filename} ({format_size(a.size, binary=True)})")
        data["attachments"] = clean_html(", ".join(att))
        if data["attachments"] != "":
            data["attachments_label"] = "Attachments"

        data["date"] = clean_html(mail.date.astimezone().strftime("%Y-%m-%d %H:%M"))
        data["content"] = clean_html(mail.text.strip())

        html_file = os.path.join(os.path.dirname(__file__), "mail_template/index.html")
        placeholder_pattern = re.compile(r"{{(.+)}}")

        html = StringIO()

        with open(html_file) as html_template_handle:
            for line in html_template_handle.readlines():
                for placeholder in placeholder_pattern.findall(line):
                    line = re.sub(
                        "{{" + placeholder + "}}",
                        data.get(placeholder.strip(), ""),
                        line,
                    )
                html.write(line)
            html.seek(0)

        return html

    def generate_pdf_from_mail(self, mail):

        url = self.gotenberg_server + "/forms/chromium/convert/html"
        self.log("info", "Converting mail to PDF")

        css_file = os.path.join(os.path.dirname(__file__), "mail_template/output.css")

        with open(css_file, "rb") as css_handle:

            files = {
                "html": ("index.html", self.mail_to_html(mail)),
                "css": ("output.css", css_handle),
            }
            headers = {}
            data = {
                "marginTop": "0.1",
                "marginBottom": "0.1",
                "marginLeft": "0.1",
                "marginRight": "0.1",
                "paperWidth": "8.27",
                "paperHeight": "11.7",
                "scale": "1.0",
            }
            try:
                response = requests.post(
                    url,
                    files=files,
                    headers=headers,
                    data=data,
                )
                response.raise_for_status()  # ensure we notice bad responses
            except Exception as err:
                raise ParseError(f"Error while converting document to PDF: {err}")

        return response.content

    @staticmethod
    def transform_inline_html(html, attachments):
        def clean_html_script(text: str):
            compiled_open = re.compile(re.escape("<script"), re.IGNORECASE)
            text = compiled_open.sub("<div hidden ", text)

            compiled_close = re.compile(re.escape("</script"), re.IGNORECASE)
            text = compiled_close.sub("</div", text)
            return text

        html_clean = clean_html_script(html)
        files = []

        for a in attachments:
            name_cid = "cid:" + a.content_id
            name_clean = "".join(e for e in name_cid if e.isalnum())
            files.append((name_clean, BytesIO(a.payload)))
            html_clean = html_clean.replace(name_cid, name_clean)

        files.append(("index.html", StringIO(html_clean)))

        return files

    def generate_pdf_from_html(self, orig_html, attachments):
        url = self.gotenberg_server + "/forms/chromium/convert/html"
        self.log("info", "Converting html to PDF")

        files = {}
        for name, file in self.transform_inline_html(orig_html, attachments):
            files[name] = (name, file)

        headers = {}
        data = {
            "marginTop": "0.1",
            "marginBottom": "0.1",
            "marginLeft": "0.1",
            "marginRight": "0.1",
            "paperWidth": "8.27",
            "paperHeight": "11.7",
            "scale": "1.0",
        }
        try:
            response = requests.post(
                url,
                files=files,
                headers=headers,
                data=data,
            )
            response.raise_for_status()  # ensure we notice bad responses
        except Exception as err:
            raise ParseError(f"Error while converting document to PDF: {err}")

        return response.content
