"""
Built-in mail document parser.

Handles message/rfc822 (EML) MIME type by:
- Parsing the email using imap_tools
- Generating a PDF via Gotenberg (for display and archive)
- Extracting text via Tika for HTML content
- Extracting metadata from email headers

The parser always produces a PDF because EML files cannot be rendered
natively in a browser (requires_pdf_rendition=True).
"""

from __future__ import annotations

import logging
import re
import shutil
import tempfile
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Self

from bleach import clean
from bleach import linkify
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import is_naive
from django.utils.timezone import make_aware
from gotenberg_client import GotenbergClient
from gotenberg_client.constants import A4
from gotenberg_client.options import Measurement
from gotenberg_client.options import MeasurementUnitType
from gotenberg_client.options import PageMarginsType
from gotenberg_client.options import PdfAFormat
from humanize import naturalsize
from imap_tools import MailAttachment
from imap_tools import MailMessage
from tika_client import TikaClient

from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless.models import OutputTypeChoices
from paperless.version import __full_version_str__
from paperless_mail.models import MailRule

if TYPE_CHECKING:
    import datetime
    from types import TracebackType

    from paperless.parsers import MetadataEntry
    from paperless.parsers import ParserContext

logger = logging.getLogger("paperless.parsing.mail")

_SUPPORTED_MIME_TYPES: dict[str, str] = {
    "message/rfc822": ".eml",
}


class MailDocumentParser:
    """Parse .eml email files for Paperless-ngx.

    Uses imap_tools to parse .eml files, generates a PDF using Gotenberg,
    and sends the HTML part to a Tika server for text extraction.  Because
    EML files cannot be rendered natively in a browser, the parser always
    produces a PDF rendition (requires_pdf_rendition=True).

    Pass a ``ParserContext`` to ``configure()`` before ``parse()`` to
    apply mail-rule-specific PDF layout options:

        parser.configure(ParserContext(mailrule_id=rule.pk))
        parser.parse(path, mime_type)

    Class attributes
    ----------------
    name : str
        Human-readable parser name.
    version : str
        Semantic version string, kept in sync with Paperless-ngx releases.
    author : str
        Maintainer name.
    url : str
        Issue tracker / source URL.
    """

    name: str = "Paperless-ngx Mail Parser"
    version: str = __full_version_str__
    author: str = "Paperless-ngx Contributors"
    url: str = "https://github.com/paperless-ngx/paperless-ngx"

    # ------------------------------------------------------------------
    # Class methods
    # ------------------------------------------------------------------

    @classmethod
    def supported_mime_types(cls) -> dict[str, str]:
        """Return the MIME types this parser handles.

        Returns
        -------
        dict[str, str]
            Mapping of MIME type to preferred file extension.
        """
        return _SUPPORTED_MIME_TYPES

    @classmethod
    def score(
        cls,
        mime_type: str,
        filename: str,
        path: Path | None = None,
    ) -> int | None:
        """Return the priority score for handling this file.

        Parameters
        ----------
        mime_type:
            Detected MIME type of the file.
        filename:
            Original filename including extension.
        path:
            Optional filesystem path. Not inspected by this parser.

        Returns
        -------
        int | None
            10 if the MIME type is supported, otherwise None.
        """
        if mime_type in _SUPPORTED_MIME_TYPES:
            return 10
        return None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def can_produce_archive(self) -> bool:
        """Whether this parser can produce a searchable PDF archive copy.

        Returns
        -------
        bool
            Always False — the mail parser produces a display PDF
            (requires_pdf_rendition=True), not an optional OCR archive.
        """
        return False

    @property
    def requires_pdf_rendition(self) -> bool:
        """Whether the parser must produce a PDF for the frontend to display.

        Returns
        -------
        bool
            Always True — EML files cannot be rendered natively in a browser,
            so a PDF conversion is always required for display.
        """
        return True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, logging_group: object = None) -> None:
        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
        self._tempdir = Path(
            tempfile.mkdtemp(prefix="paperless-", dir=settings.SCRATCH_DIR),
        )
        self._text: str | None = None
        self._date: datetime.datetime | None = None
        self._archive_path: Path | None = None
        self._mailrule_id: int | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        logger.debug("Cleaning up temporary directory %s", self._tempdir)
        shutil.rmtree(self._tempdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Core parsing interface
    # ------------------------------------------------------------------

    def configure(self, context: ParserContext) -> None:
        self._mailrule_id = context.mailrule_id

    def parse(
        self,
        document_path: Path,
        mime_type: str,
        *,
        produce_archive: bool = True,
    ) -> None:
        """Parse the given .eml into formatted text and a PDF archive.

        Call ``configure(ParserContext(mailrule_id=...))`` before this method
        to apply mail-rule-specific PDF layout options.  The ``produce_archive``
        flag is accepted for protocol compatibility but is always honoured —
        the mail parser always produces a PDF since EML files cannot be
        displayed natively.

        Parameters
        ----------
        document_path:
            Absolute path to the .eml file.
        mime_type:
            Detected MIME type of the document (should be "message/rfc822").
        produce_archive:
            Accepted for protocol compatibility. The PDF rendition is always
            produced since EML files cannot be displayed natively in a browser.

        Raises
        ------
        documents.parsers.ParseError
            If the file cannot be parsed or PDF generation fails.
        """

        def strip_text(text: str) -> str:
            """Reduces the spacing of the given text string."""
            text = re.sub(r"\s+", " ", text)
            text = re.sub(r"(\n *)+", "\n", text)
            return text.strip()

        def build_formatted_text(mail_message: MailMessage) -> str:
            """Constructs a formatted string based on the given email."""
            fmt_text = f"Subject: {mail_message.subject}\n\n"
            fmt_text += f"From: {mail_message.from_values.full if mail_message.from_values else ''}\n\n"
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

        logger.debug("Parsing file %s into an email", document_path.name)
        mail = self.parse_file_to_message(document_path)

        logger.debug("Building formatted text from email")
        self._text = build_formatted_text(mail)

        if is_naive(mail.date):
            self._date = make_aware(mail.date)
        else:
            self._date = mail.date

        logger.debug("Creating a PDF from the email")
        if self._mailrule_id:
            rule = MailRule.objects.get(pk=self._mailrule_id)
            self._archive_path = self.generate_pdf(
                mail,
                MailRule.PdfLayout(rule.pdf_layout),
            )
        else:
            self._archive_path = self.generate_pdf(mail)

    # ------------------------------------------------------------------
    # Result accessors
    # ------------------------------------------------------------------

    def get_text(self) -> str | None:
        """Return the plain-text content extracted during parse.

        Returns
        -------
        str | None
            Extracted text, or None if parse has not been called yet.
        """
        return self._text

    def get_date(self) -> datetime.datetime | None:
        """Return the document date detected during parse.

        Returns
        -------
        datetime.datetime | None
            Date from the email headers, or None if not detected.
        """
        return self._date

    def get_archive_path(self) -> Path | None:
        """Return the path to the generated archive PDF, or None.

        Returns
        -------
        Path | None
            Path to the PDF produced by Gotenberg, or None if parse has not
            been called yet.
        """
        return self._archive_path

    # ------------------------------------------------------------------
    # Thumbnail and metadata
    # ------------------------------------------------------------------

    def get_thumbnail(
        self,
        document_path: Path,
        mime_type: str,
        file_name: str | None = None,
    ) -> Path:
        """Generate a thumbnail from the PDF rendition of the email.

        Converts the document to PDF first if not already done.

        Parameters
        ----------
        document_path:
            Absolute path to the source document.
        mime_type:
            Detected MIME type of the document.
        file_name:
            Kept for backward compatibility; not used.

        Returns
        -------
        Path
            Path to the generated WebP thumbnail inside the temporary directory.
        """
        if not self._archive_path:
            self._archive_path = self.generate_pdf(
                self.parse_file_to_message(document_path),
            )

        return make_thumbnail_from_pdf(
            self._archive_path,
            self._tempdir,
        )

    def get_page_count(
        self,
        document_path: Path,
        mime_type: str,
    ) -> int | None:
        """Return the number of pages in the document.

        Counts pages in the archive PDF produced by a preceding parse()
        call.  Returns ``None`` if parse() has not been called yet or if
        no archive was produced.

        Returns
        -------
        int | None
            Page count of the archive PDF, or ``None``.
        """
        if self._archive_path is not None:
            from paperless.parsers.utils import get_page_count_for_pdf

            return get_page_count_for_pdf(self._archive_path, log=logger)
        return None

    def extract_metadata(
        self,
        document_path: Path,
        mime_type: str,
    ) -> list[MetadataEntry]:
        """Extract metadata from the email headers.

        Returns email headers as metadata entries with prefix "header",
        plus summary entries for attachments and date.

        Returns
        -------
        list[MetadataEntry]
            Sorted list of metadata entries, or ``[]`` on parse failure.
        """
        result: list[MetadataEntry] = []

        try:
            mail = self.parse_file_to_message(document_path)
        except ParseError as e:
            logger.warning(
                "Error while fetching document metadata for %s: %s",
                document_path,
                e,
            )
            return result

        for key, header_values in mail.headers.items():
            value = ", ".join(header_values)
            try:
                value.encode("utf-8")
            except UnicodeEncodeError as e:  # pragma: no cover
                logger.debug("Skipping header %s: %s", key, e)
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

    # ------------------------------------------------------------------
    # Email-specific methods
    # ------------------------------------------------------------------

    def _settings_to_gotenberg_pdfa(self) -> PdfAFormat | None:
        """Convert the OCR output type setting to a Gotenberg PdfAFormat."""
        if settings.OCR_OUTPUT_TYPE in {
            OutputTypeChoices.PDF_A,
            OutputTypeChoices.PDF_A2,
        }:
            return PdfAFormat.A2b
        elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A1:  # pragma: no cover
            logger.warning(
                "Gotenberg does not support PDF/A-1a, choosing PDF/A-2b instead",
            )
            return PdfAFormat.A2b
        elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A3:  # pragma: no cover
            return PdfAFormat.A3b
        return None

    @staticmethod
    def parse_file_to_message(filepath: Path) -> MailMessage:
        """Parse the given .eml file into a MailMessage object.

        Parameters
        ----------
        filepath:
            Path to the .eml file.

        Returns
        -------
        MailMessage
            Parsed mail message.

        Raises
        ------
        documents.parsers.ParseError
            If the file cannot be parsed or is missing required fields.
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

    def tika_parse(self, html: str) -> str:
        """Send HTML content to the Tika server for text extraction.

        Parameters
        ----------
        html:
            HTML string to parse.

        Returns
        -------
        str
            Extracted plain text.

        Raises
        ------
        documents.parsers.ParseError
            If the Tika server cannot be reached or returns an error.
        """
        logger.info("Sending content to Tika server")

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

    def generate_pdf(
        self,
        mail_message: MailMessage,
        pdf_layout: MailRule.PdfLayout | None = None,
    ) -> Path:
        """Generate a PDF from the email message.

        Creates separate PDFs for the email body and HTML content, then
        merges them according to the requested layout.

        Parameters
        ----------
        mail_message:
            Parsed email message.
        pdf_layout:
            Layout option for the PDF. Falls back to the
            EMAIL_PARSE_DEFAULT_LAYOUT setting if not provided.

        Returns
        -------
        Path
            Path to the generated PDF inside the temporary directory.
        """
        archive_path = Path(self._tempdir) / "merged.pdf"

        mail_pdf_file = self.generate_pdf_from_mail(mail_message)

        if pdf_layout is None:
            pdf_layout = MailRule.PdfLayout(settings.EMAIL_PARSE_DEFAULT_LAYOUT)

        # If no HTML content, create the PDF from the message.
        # Otherwise, create 2 PDFs and merge them with Gotenberg.
        if not mail_message.html:
            archive_path.write_bytes(mail_pdf_file.read_bytes())
        else:
            pdf_of_html_content = self.generate_pdf_from_html(
                mail_message.html,
                mail_message.attachments,
            )

            logger.debug("Merging email text and HTML content into single PDF")

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

                match pdf_layout:
                    case MailRule.PdfLayout.HTML_TEXT:
                        route.merge([pdf_of_html_content, mail_pdf_file])
                    case MailRule.PdfLayout.HTML_ONLY:
                        route.merge([pdf_of_html_content])
                    case MailRule.PdfLayout.TEXT_ONLY:
                        route.merge([mail_pdf_file])
                    case MailRule.PdfLayout.TEXT_HTML | _:
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
        """Convert the given email into an HTML file using a template.

        Parameters
        ----------
        mail:
            Parsed mail message.

        Returns
        -------
        Path
            Path to the rendered HTML file inside the temporary directory.
        """

        def clean_html(text: str) -> str:
            """Attempt to clean, escape, and linkify the given HTML string."""
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
        data["from"] = clean_html(mail.from_values.full if mail.from_values else "")
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

        data["date"] = clean_html(
            timezone.localtime(mail.date).strftime("%Y-%m-%d %H:%M"),
        )
        data["content"] = clean_html(mail.text.strip())

        from django.template.loader import render_to_string

        html_file = Path(self._tempdir) / "email_as_html.html"
        html_file.write_text(render_to_string("email_msg_template.html", context=data))

        return html_file

    def generate_pdf_from_mail(self, mail: MailMessage) -> Path:
        """Create a PDF from the email body using an HTML template and Gotenberg.

        Parameters
        ----------
        mail:
            Parsed mail message.

        Returns
        -------
        Path
            Path to the generated PDF inside the temporary directory.

        Raises
        ------
        documents.parsers.ParseError
            If Gotenberg returns an error.
        """
        logger.info("Converting mail to PDF")

        css_file = (
            Path(__file__).parent.parent.parent
            / "paperless_mail"
            / "templates"
            / "output.css"
        )
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
                            top=Measurement(0.1, MeasurementUnitType.Inches),
                            bottom=Measurement(0.1, MeasurementUnitType.Inches),
                            left=Measurement(0.1, MeasurementUnitType.Inches),
                            right=Measurement(0.1, MeasurementUnitType.Inches),
                        ),
                    )
                    .size(A4)
                    .scale(1.0)
                    .run()
                )
            except Exception as err:
                raise ParseError(
                    f"Error while converting email to PDF: {err}",
                ) from err

        email_as_pdf_file = Path(self._tempdir) / "email_as_pdf.pdf"
        email_as_pdf_file.write_bytes(response.content)

        return email_as_pdf_file

    def generate_pdf_from_html(
        self,
        orig_html: str,
        attachments: list[MailAttachment],
    ) -> Path:
        """Generate a PDF from the HTML content of the email.

        Parameters
        ----------
        orig_html:
            Raw HTML string from the email body.
        attachments:
            List of email attachments (used as inline resources).

        Returns
        -------
        Path
            Path to the generated PDF inside the temporary directory.

        Raises
        ------
        documents.parsers.ParseError
            If Gotenberg returns an error.
        """

        def clean_html_script(text: str) -> str:
            compiled_open = re.compile(re.escape("<script"), re.IGNORECASE)
            text = compiled_open.sub("<div hidden ", text)

            compiled_close = re.compile(re.escape("</script"), re.IGNORECASE)
            text = compiled_close.sub("</div", text)
            return text

        logger.info("Converting message html to PDF")

        tempdir = Path(self._tempdir)

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
                    top=Measurement(0.1, MeasurementUnitType.Inches),
                    bottom=Measurement(0.1, MeasurementUnitType.Inches),
                    left=Measurement(0.1, MeasurementUnitType.Inches),
                    right=Measurement(0.1, MeasurementUnitType.Inches),
                ),
            ).size(A4).scale(1.0)

            try:
                response = route.run()

            except Exception as err:
                raise ParseError(
                    f"Error while converting document to PDF: {err}",
                ) from err

        html_pdf = tempdir / "html.pdf"
        html_pdf.write_bytes(response.content)
        return html_pdf
