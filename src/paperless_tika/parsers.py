from pathlib import Path

import httpx
from django.conf import settings
from django.utils import timezone
from gotenberg_client import GotenbergClient
from gotenberg_client.options import PdfAFormat
from tika_client import TikaClient

from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless.config import OutputTypeConfig
from paperless.models import OutputTypeChoices


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
        try:
            with TikaClient(tika_url=settings.TIKA_ENDPOINT) as client:
                parsed = client.metadata.from_file(document_path, mime_type)
                return [
                    {
                        "namespace": "",
                        "prefix": "",
                        "key": key,
                        "value": parsed.data[key],
                    }
                    for key in parsed.data
                ]
        except Exception as e:
            self.log.warning(
                f"Error while fetching document metadata for {document_path}: {e}",
            )
            return []

    def parse(self, document_path: Path, mime_type: str, file_name=None):
        self.log.info(f"Sending {document_path} to Tika server")

        try:
            with TikaClient(tika_url=settings.TIKA_ENDPOINT) as client:
                try:
                    parsed = client.tika.as_text.from_file(document_path, mime_type)
                except httpx.HTTPStatusError as err:
                    # Workaround https://issues.apache.org/jira/browse/TIKA-4110
                    # Tika fails with some files as multi-part form data
                    if err.response.status_code == httpx.codes.INTERNAL_SERVER_ERROR:
                        parsed = client.tika.as_text.from_buffer(
                            document_path.read_bytes(),
                            mime_type,
                        )
                    else:  # pragma: no cover
                        raise
        except Exception as err:
            raise ParseError(
                f"Could not parse {document_path} with tika server at "
                f"{settings.TIKA_ENDPOINT}: {err}",
            ) from err

        self.text = parsed.content
        if self.text is not None:
            self.text = self.text.strip()

        self.date = parsed.created
        if self.date is not None and timezone.is_naive(self.date):
            self.date = timezone.make_aware(self.date)

        self.archive_path = self.convert_to_pdf(document_path, file_name)

    def convert_to_pdf(self, document_path: Path, file_name):
        pdf_path = Path(self.tempdir) / "convert.pdf"

        self.log.info(f"Converting {document_path} to PDF as {pdf_path}")

        with (
            GotenbergClient(
                host=settings.TIKA_GOTENBERG_ENDPOINT,
                timeout=settings.CELERY_TASK_TIME_LIMIT,
            ) as client,
            client.libre_office.to_pdf() as route,
        ):
            # Set the output format of the resulting PDF
            if settings.OCR_OUTPUT_TYPE in {
                OutputTypeChoices.PDF_A,
                OutputTypeChoices.PDF_A2,
            }:
                route.pdf_format(PdfAFormat.A2b)
            elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A1:
                self.log.warning(
                    "Gotenberg does not support PDF/A-1a, choosing PDF/A-2b instead",
                )
                route.pdf_format(PdfAFormat.A2b)
            elif settings.OCR_OUTPUT_TYPE == OutputTypeChoices.PDF_A3:
                route.pdf_format(PdfAFormat.A3b)

            route.convert(document_path)

            try:
                response = route.run()

                pdf_path.write_bytes(response.content)

                return pdf_path

            except Exception as err:
                raise ParseError(
                    f"Error while converting document to PDF: {err}",
                ) from err

    def get_settings(self) -> OutputTypeConfig:
        """
        This parser only uses the PDF output type configuration currently
        """
        return OutputTypeConfig()
