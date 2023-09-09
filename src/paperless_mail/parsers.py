import re
from html import escape
from pathlib import Path

import httpx
from bleach import clean
from bleach import linkify
from django.conf import settings
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware
from humanize import naturalsize
from imap_tools import MailAttachment
from imap_tools import MailMessage
from tika_client import TikaClient

from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf


class MailDocumentParser(DocumentParser):
    """
    This parser uses imap_tools to parse .eml files, generates pdf using
    Gotenberg and sends the html part to a Tika server for text extraction.
    """

    gotenberg_server = settings.TIKA_GOTENBERG_ENDPOINT
    tika_server = settings.TIKA_ENDPOINT

    logging_name = "paperless.parsing.mail"

    def get_thumbnail(self, document_path: Path, mime_type: str, file_name=None):
        if not self.archive_path:
            self.archive_path = self.generate_pdf(
                self.parse_file_to_message(document_path),
            )

        return make_thumbnail_from_pdf(
            self.archive_path,
            self.tempdir,
            self.logging_group,
        )

    def extract_metadata(self, document_path: Path, mime_type: str):
        result = []

        try:
            mail = self.parse_file_to_message(document_path)
        except ParseError as e:
            self.log.warning(
                f"Error while fetching document metadata for {document_path}: {e}",
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
                    f"{attachment.filename}"
                    f"({naturalsize(attachment.size, binary=True, format='%.2f')})"
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

    def parse(self, document_path: Path, mime_type: str, file_name=None):
        """
        Parses the given .eml into formatted text, based on the decoded email.

        """

        def strip_text(text: str):
            """
            Reduces the spacing of the given text string
            """
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"(\n *)+", "\n", text)
            return text.strip()

        def build_formatted_text(mail_message: MailMessage) -> str:
            """
            Constructs a formatted string, based on the given email.  Basically tries
            to get most of the email content, included front matter, into a nice string
            """
            fmt_text = f"Subject: {mail_message.subject}\n\n"
            fmt_text += f"From: {mail_message.from_values.full}\n\n"
            to_list = [address.full for address in mail_message.to_values]
            fmt_text += f"To: {', '.join(to_list)}\n\n"
            if mail_message.cc_values:
                fmt_text += (
                    f"CC: {', '.join(address.full for address in mail.cc_values)}\n\n"
                )
            if mail_message.bcc_values:
                fmt_text += (
                    f"BCC: {', '.join(address.full for address in mail.bcc_values)}\n\n"
                )
            if mail_message.attachments:
                att = []
                for a in mail.attachments:
                    attachment_size = naturalsize(a.size, binary=True, format="%.2f")
                    att.append(
                        f"{a.filename} ({attachment_size})",
                    )
                fmt_text += f"Attachments: {', '.join(att)}\n\n"

            if mail.html:
                fmt_text += "HTML content: " + strip_text(self.tika_parse(mail.html))

            fmt_text += f"\n\n{strip_text(mail.text)}"

            return fmt_text

        self.log.debug(f"Parsing file {document_path.name} into an email")
        mail = self.parse_file_to_message(document_path)

        self.log.debug("Building formatted text from email")
        self.text = build_formatted_text(mail)

        if is_naive(mail.date):
            self.date = make_aware(mail.date)
        else:
            self.date = mail.date

        self.log.debug("Creating a PDF from the email")
        self.archive_path = self.generate_pdf(mail)

    @staticmethod
    def parse_file_to_message(filepath: Path) -> MailMessage:
        """
        Parses the given .eml file into a MailMessage object
        """
        try:
            with filepath.open("rb") as eml:
                parsed = MailMessage.from_bytes(eml.read())
                if parsed.from_values is None:
                    raise ParseError(
                        f"Could not parse {filepath}: Missing 'from'",
                    )
        except Exception as err:
            raise ParseError(
                f"Could not parse {filepath}: {err}",
            ) from err

        return parsed

    def tika_parse(self, html: str):
        self.log.info("Sending content to Tika server")

        try:
            with TikaClient(tika_url=self.tika_server) as client:
                parsed = client.tika.as_text.from_buffer(html, "text/html")

                if parsed.content is not None:
                    return parsed.content.strip()
                return ""
        except Exception as err:
            raise ParseError(
                f"Could not parse content with tika server at "
                f"{self.tika_server}: {err}",
            ) from err

    def generate_pdf(self, mail_message: MailMessage) -> Path:
        archive_path = Path(self.tempdir) / "merged.pdf"

        mail_pdf_file = self.generate_pdf_from_mail(mail_message)

        # If no HTML content, create the PDF from the message
        # Otherwise, create 2 PDFs and merge them with Gotenberg
        if not mail_message.html:
            archive_path.write_bytes(mail_pdf_file.read_bytes())
        else:
            url_merge = self.gotenberg_server + "/forms/pdfengines/merge"

            pdf_of_html_content = self.generate_pdf_from_html(
                mail_message.html,
                mail_message.attachments,
            )

            pdf_collection = {
                "1_mail.pdf": ("1_mail.pdf", mail_pdf_file, "application/pdf"),
                "2_html.pdf": ("2_html.pdf", pdf_of_html_content, "application/pdf"),
            }

            try:
                # Open a handle to each file, replacing the tuple
                for filename in pdf_collection:
                    file_multi_part = pdf_collection[filename]
                    pdf_collection[filename] = (
                        file_multi_part[0],
                        file_multi_part[1].open("rb"),
                        file_multi_part[2],
                    )

                response = httpx.post(
                    url_merge,
                    files=pdf_collection,
                    timeout=settings.CELERY_TASK_TIME_LIMIT,
                )
                response.raise_for_status()  # ensure we notice bad responses

                archive_path.write_bytes(response.content)

            except Exception as err:
                raise ParseError(
                    f"Error while merging email HTML into PDF: {err}",
                ) from err
            finally:
                for filename in pdf_collection:
                    file_multi_part_handle = pdf_collection[filename][1]
                    file_multi_part_handle.close()

        return archive_path

    def mail_to_html(self, mail: MailMessage) -> Path:
        """
        Converts the given email into an HTML file, formatted
        based on the given template
        """

        def clean_html(text: str) -> str:
            """
            Attempts to clean, escape and linkify the given HTML string
            """
            if isinstance(text, list):
                text = "\n".join([str(e) for e in text])
            if not isinstance(text, str):
                text = str(text)
            text = escape(text)
            text = clean(text)
            text = linkify(text, parse_email=True)
            text = text.replace("\n", "<br>")
            return text

        data = {}

        data["subject"] = clean_html(mail.subject)
        if data["subject"]:
            data["subject_label"] = "Subject"
        data["from"] = clean_html(mail.from_values.full)
        if data["from"]:
            data["from_label"] = "From"
        data["to"] = clean_html(", ".join(address.full for address in mail.to_values))
        if data["to"]:
            data["to_label"] = "To"
        data["cc"] = clean_html(", ".join(address.full for address in mail.cc_values))
        if data["cc"]:
            data["cc_label"] = "CC"
        data["bcc"] = clean_html(", ".join(address.full for address in mail.bcc_values))
        if data["bcc"]:
            data["bcc_label"] = "BCC"

        att = []
        for a in mail.attachments:
            att.append(
                f"{a.filename} ({naturalsize(a.size, binary=True, format='%.2f')})",
            )
        data["attachments"] = clean_html(", ".join(att))
        if data["attachments"]:
            data["attachments_label"] = "Attachments"

        data["date"] = clean_html(mail.date.astimezone().strftime("%Y-%m-%d %H:%M"))
        data["content"] = clean_html(mail.text.strip())

        from django.template.loader import render_to_string

        html_file = Path(self.tempdir) / "email_as_html.html"
        html_file.write_text(render_to_string("email_msg_template.html", context=data))

        return html_file

    def generate_pdf_from_mail(self, mail: MailMessage) -> Path:
        """
        Creates a PDF based on the given email, using the email's values in a
        an HTML template
        """
        url = self.gotenberg_server + "/forms/chromium/convert/html"
        self.log.info("Converting mail to PDF")

        css_file = Path(__file__).parent / "templates" / "output.css"
        email_html_file = self.mail_to_html(mail)

        with css_file.open("rb") as css_handle, email_html_file.open(
            "rb",
        ) as email_html_handle:
            files = {
                "html": ("index.html", email_html_handle, "text/html"),
                "css": ("output.css", css_handle, "text/css"),
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

            # Set the output format of the resulting PDF
            # Valid inputs: https://gotenberg.dev/docs/modules/pdf-engines#uno
            if settings.OCR_OUTPUT_TYPE in {"pdfa", "pdfa-2"}:
                data["pdfFormat"] = "PDF/A-2b"
            elif settings.OCR_OUTPUT_TYPE == "pdfa-1":
                data["pdfFormat"] = "PDF/A-1a"
            elif settings.OCR_OUTPUT_TYPE == "pdfa-3":
                data["pdfFormat"] = "PDF/A-3b"

            try:
                response = httpx.post(
                    url,
                    files=files,
                    headers=headers,
                    data=data,
                    timeout=settings.CELERY_TASK_TIME_LIMIT,
                )
                response.raise_for_status()  # ensure we notice bad responses
            except Exception as err:
                raise ParseError(
                    f"Error while converting email to PDF: {err}",
                ) from err

        email_as_pdf_file = Path(self.tempdir) / "email_as_pdf.pdf"
        email_as_pdf_file.write_bytes(response.content)

        return email_as_pdf_file

    def generate_pdf_from_html(
        self,
        orig_html: str,
        attachments: list[MailAttachment],
    ) -> Path:
        """
        Generates a PDF file based on the HTML and attachments of the email
        """

        def clean_html_script(text: str):
            compiled_open = re.compile(re.escape("<script"), re.IGNORECASE)
            text = compiled_open.sub("<div hidden ", text)

            compiled_close = re.compile(re.escape("</script"), re.IGNORECASE)
            text = compiled_close.sub("</div", text)
            return text

        url = self.gotenberg_server + "/forms/chromium/convert/html"
        self.log.info("Converting html to PDF")

        tempdir = Path(self.tempdir)

        html_clean = clean_html_script(orig_html)

        files = {}

        for attachment in attachments:
            # Clean the attachment name to be valid
            name_cid = f"cid:{attachment.content_id}"
            name_clean = "".join(e for e in name_cid if e.isalnum())

            # Write attachment payload to a temp file
            temp_file = tempdir / name_clean
            temp_file.write_bytes(attachment.payload)

            # Store the attachment for upload
            files[name_clean] = (name_clean, temp_file, attachment.content_type)

            # Replace as needed the name with the clean name
            html_clean = html_clean.replace(name_cid, name_clean)

        # Now store the cleaned up HTML version
        html_clean_file = tempdir / "index.html"
        html_clean_file.write_text(html_clean)

        files["index.html"] = ("index.html", html_clean_file, "text/html")

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
            # Open a handle to each file, replacing the tuple
            for filename in files:
                file_multi_part = files[filename]
                files[filename] = (
                    file_multi_part[0],
                    file_multi_part[1].open("rb"),
                    file_multi_part[2],
                )

            response = httpx.post(
                url,
                files=files,
                data=data,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            )
            response.raise_for_status()  # ensure we notice bad responses
        except Exception as err:
            raise ParseError(f"Error while converting document to PDF: {err}") from err
        finally:
            # Ensure all file handles as closed
            for filename in files:
                file_multi_part_handle = files[filename][1]
                file_multi_part_handle.close()

        html_pdf = tempdir / "html.pdf"
        html_pdf.write_bytes(response.content)
        return html_pdf
