import re
from html import escape
from pathlib import Path

from bleach import clean
from bleach import linkify
from django.conf import settings
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware
from gotenberg_client import GotenbergClient
from gotenberg_client.options import MarginType
from gotenberg_client.options import MarginUnitType
from gotenberg_client.options import PageMarginsType
from gotenberg_client.options import PageSize
from gotenberg_client.options import PdfAFormat
from humanize import naturalsize
from imap_tools import MailAttachment
from imap_tools import MailMessage
from tika_client import TikaClient

from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless.models import OutputTypeChoices


class MailDocumentParser(DocumentParser):
    """
    This parser uses imap_tools to parse .eml files, generates pdf using
    Gotenberg and sends the html part to a Tika server for text extraction.
    """

    logging_name = "paperless.parsing.mail"

    def _settings_to_gotenberg_pdfa(self) -> PdfAFormat | None:
        """
        Converts our requested PDF/A output into the Gotenberg API
        format
        """
        if settings.OCR_OUTPUT_TYPE in {
            OutputTypeChoices.PDF_A,
            OutputTypeChoices.PDF_A2,
        }:
            return PdfAFormat.A2b
        elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A1:  # pragma: no cover
            self.log.warning(
                "Gotenberg does not support PDF/A-1a, choosing PDF/A-2b instead",
            )
            return PdfAFormat.A2b
        elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A3:  # pragma: no cover
            return PdfAFormat.A3b
        return None

    def get_thumbnail(
        self,
        document_path: Path,
        mime_type: str,
        file_name=None,
    ) -> Path:
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
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as e:  # pragma: no cover
                self.log.debug(f"Skipping header {key}: {e}")
                continue

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
            with TikaClient(tika_url=settings.TIKA_ENDPOINT) as client:
                parsed = client.tika.as_text.from_buffer(html, "text/html")

                if parsed.content is not None:
                    return parsed.content.strip()
                return ""
        except Exception as err:
            raise ParseError(
                f"Could not parse content with tika server at "
                f"{settings.TIKA_ENDPOINT}: {err}",
            ) from err

    def generate_pdf(self, mail_message: MailMessage) -> Path:
        archive_path = Path(self.tempdir) / "merged.pdf"

        mail_pdf_file = self.generate_pdf_from_mail(mail_message)

        # If no HTML content, create the PDF from the message
        # Otherwise, create 2 PDFs and merge them with Gotenberg
        if not mail_message.html:
            archive_path.write_bytes(mail_pdf_file.read_bytes())
        else:
            pdf_of_html_content = self.generate_pdf_from_html(
                mail_message.html,
                mail_message.attachments,
            )

            self.log.debug("Merging email text and HTML content into single PDF")

            with (
                GotenbergClient(
                    host=settings.TIKA_GOTENBERG_ENDPOINT,
                    timeout=settings.CELERY_TASK_TIME_LIMIT,
                ) as client,
                client.merge.merge() as route,
            ):
                # Configure requested PDF/A formatting, if any
                pdf_a_format = self._settings_to_gotenberg_pdfa()
                if pdf_a_format is not None:
                    route.pdf_format(pdf_a_format)

                route.merge([mail_pdf_file, pdf_of_html_content])

                try:
                    response = route.run()
                    archive_path.write_bytes(response.content)
                except Exception as err:
                    raise ParseError(
                        f"Error while merging email HTML into PDF: {err}",
                    ) from err

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
        self.log.info("Converting mail to PDF")

        css_file = Path(__file__).parent / "templates" / "output.css"
        email_html_file = self.mail_to_html(mail)

        with (
            GotenbergClient(
                host=settings.TIKA_GOTENBERG_ENDPOINT,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            ) as client,
            client.chromium.html_to_pdf() as route,
        ):
            # Configure requested PDF/A formatting, if any
            pdf_a_format = self._settings_to_gotenberg_pdfa()
            if pdf_a_format is not None:
                route.pdf_format(pdf_a_format)

            try:
                response = (
                    route.index(email_html_file)
                    .resource(css_file)
                    .margins(
                        PageMarginsType(
                            top=MarginType(0.1, MarginUnitType.Inches),
                            bottom=MarginType(0.1, MarginUnitType.Inches),
                            left=MarginType(0.1, MarginUnitType.Inches),
                            right=MarginType(0.1, MarginUnitType.Inches),
                        ),
                    )
                    .size(PageSize(height=11.7, width=8.27))
                    .scale(1.0)
                    .run()
                )
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

        self.log.info("Converting message html to PDF")

        tempdir = Path(self.tempdir)

        html_clean = clean_html_script(orig_html)
        html_clean_file = tempdir / "index.html"
        html_clean_file.write_text(html_clean)

        with (
            GotenbergClient(
                host=settings.TIKA_GOTENBERG_ENDPOINT,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            ) as client,
            client.chromium.html_to_pdf() as route,
        ):
            # Configure requested PDF/A formatting, if any
            pdf_a_format = self._settings_to_gotenberg_pdfa()
            if pdf_a_format is not None:
                route.pdf_format(pdf_a_format)

            # Add attachments as resources, cleaning the filename and replacing
            # it in the index file for inclusion
            for attachment in attachments:
                # Clean the attachment name to be valid
                name_cid = f"cid:{attachment.content_id}"
                name_clean = "".join(e for e in name_cid if e.isalnum())

                # Write attachment payload to a temp file
                temp_file = tempdir / name_clean
                temp_file.write_bytes(attachment.payload)

                route.resource(temp_file)

                # Replace as needed the name with the clean name
                html_clean = html_clean.replace(name_cid, name_clean)

            # Now store the cleaned up HTML version
            html_clean_file = tempdir / "index.html"
            html_clean_file.write_text(html_clean)
            # This is our index file, the main page basically
            route.index(html_clean_file)

            # Set page size, margins
            route.margins(
                PageMarginsType(
                    top=MarginType(0.1, MarginUnitType.Inches),
                    bottom=MarginType(0.1, MarginUnitType.Inches),
                    left=MarginType(0.1, MarginUnitType.Inches),
                    right=MarginType(0.1, MarginUnitType.Inches),
                ),
            ).size(
                PageSize(height=11.7, width=8.27),
            ).scale(1.0)

            try:
                response = route.run()

            except Exception as err:
                raise ParseError(
                    f"Error while converting document to PDF: {err}",
                ) from err

        html_pdf = tempdir / "html.pdf"
        html_pdf.write_bytes(response.content)
        return html_pdf

    def get_settings(self):
        """
        This parser does not implement additional settings yet
        """
        return None
