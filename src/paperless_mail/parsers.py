import os
import re
from io import StringIO

import requests
from bleach import clean
from bleach import linkify
from django.conf import settings
from documents.parsers import DocumentParser
from documents.parsers import make_thumbnail_from_pdf
from documents.parsers import ParseError
from imap_tools import MailMessage


class MailDocumentParser(DocumentParser):
    """
    This parser sends documents to a local tika server
    """

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
        mail = self.get_parsed(document_path)

        content = mail.text.strip()

        content = re.sub(" +", " ", content)
        content = re.sub("\n+", "\n", content)

        self.text = f"{content}\n\n"
        self.text += f"Subject: {mail.subject}\n"
        self.text += f"From: {mail.from_values.full}\n"
        self.text += f"To: {', '.join(address.full for address in mail.to_values)}\n"
        if len(mail.cc_values) >= 1:
            self.text += (
                f"CC: {', '.join(address.full for address in mail.cc_values)}\n"
            )
        if len(mail.bcc_values) >= 1:
            self.text += (
                f"BCC: {', '.join(address.full for address in mail.bcc_values)}\n"
            )
        if len(mail.attachments) >= 1:
            att = ", ".join(f"{a.filename} ({a.size})" for a in mail.attachments)
            self.text += f"Attachments: {att}"

        self.date = mail.date
        self.archive_path = self.generate_pdf(document_path)

    def generate_pdf(self, document_path):
        def clean_html(text: str):
            if isinstance(text, list):
                text = "\n".join([str(e) for e in text])
            if type(text) != str:
                text = str(text)
            text = text.replace("&", "&amp;")
            text = text.replace("<", "&lt;")
            text = text.replace(">", "&gt;")
            text = text.replace("  ", " &nbsp;")
            text = text.replace("'", "&apos;")
            text = text.replace('"', "&quot;")
            text = clean(text)
            text = linkify(text, parse_email=True)
            text = text.replace("\n", "<br>")
            return text

        def clean_html_script(text: str):
            text = text.replace("<script", "<div hidden ")
            text = text.replace("</script", "</div")
            return text

        mail = self.get_parsed(document_path)

        pdf_path = os.path.join(self.tempdir, "convert.pdf")
        gotenberg_server = settings.PAPERLESS_TIKA_GOTENBERG_ENDPOINT
        url = gotenberg_server + "/forms/chromium/convert/html"

        self.log("info", f"Converting {document_path} to PDF as {pdf_path}")

        data = {}
        data["subject"] = clean_html(mail.subject)
        if data["subject"] != "":
            data["subject_label"] = "Subject"
        data["from"] = clean_html(mail.from_values.full)
        if data["from"] != "":
            data["from_label"] = "From"
        data["to"] = clean_html("\n".join(address.full for address in mail.to_values))
        if data["to"] != "":
            data["to_label"] = "To"
        data["cc"] = clean_html("\n".join(address.full for address in mail.cc_values))
        if data["cc"] != "":
            data["cc_label"] = "CC"
        data["bcc"] = clean_html("\n".join(address.full for address in mail.bcc_values))
        if data["bcc"] != "":
            data["bcc_label"] = "BCC"
        data["date"] = clean_html(mail.date.astimezone().strftime("%Y-%m-%d %H:%M"))
        data["content"] = clean_html(mail.text.strip())

        html_file = os.path.join(os.path.dirname(__file__), "mail_template/index.html")
        css_file = os.path.join(os.path.dirname(__file__), "mail_template/output.css")
        placeholder_pattern = re.compile(r"{{(.+)}}")
        html = StringIO()
        orig_html = StringIO(clean_html_script(mail.html))

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
                    "mail_html": (
                        "mail_html.html",
                        orig_html,
                    ),
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

        with open(pdf_path, "wb") as file:
            file.write(response.content)
            file.close()

        return pdf_path
