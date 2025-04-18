import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

from paperless_tesseract.parsers import RasterisedDocumentParser


class RemoteEngineConfig:
    def __init__(
        self,
        engine: str,
        api_key: str | None = None,
        endpoint: str | None = None,
    ):
        self.engine = engine
        self.api_key = api_key
        self.endpoint = endpoint

    def engine_is_valid(self):
        valid = self.engine in ["azureai"] and self.api_key is not None
        if self.engine == "azureai":
            valid = valid and self.endpoint is not None
        return valid


class RemoteDocumentParser(RasterisedDocumentParser):
    """
    This parser uses a remote ocr engine to parse documents
    """

    logging_name = "paperless.parsing.remote"

    def get_settings(self) -> RemoteEngineConfig:
        """
        This parser uses the OCR configuration settings to parse documents
        """
        return RemoteEngineConfig(
            engine=settings.REMOTE_OCR_ENGINE,
            api_key=settings.REMOTE_OCR_API_KEY,
            endpoint=settings.REMOTE_OCR_ENDPOINT,
        )

    def supported_mime_types(self):
        if self.settings.engine_is_valid():
            return [
                "application/pdf",
                "image/png",
                "image/jpeg",
                "image/tiff",
                "image/bmp",
                "image/gif",
                "image/webp",
            ]
        else:
            return []

    def azure_ai_vision_parse(
        self,
        file: Path,
    ) -> str | None:
        """
        This method uses the Azure AI Vision API to parse documents
        """
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(
            endpoint=self.settings.endpoint,
            credential=AzureKeyCredential(self.settings.api_key),
        )

        with file.open("rb") as f:
            poller = client.begin_analyze_document(
                model_id="prebuilt-read",
                analyze_request=f,
                content_type="application/octet-stream",
                output_format="pdf",
            )

        result = poller.result()

        # Download the PDF with embedded text
        pdf_bytes = client.get_analyze_result_pdf(result.result_id)
        self.archive_path = Path(self.tempdir) / "archive.pdf"
        self.archive_path.write_bytes(pdf_bytes)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            subprocess.run(
                [
                    "pdftotext",
                    "-q",
                    "-layout",
                    str(self.archive_path),
                    tmp.name,
                ],
            )
            with Path.open(tmp.name, encoding="utf-8") as t:
                return t.read()

    def parse(self, document_path: Path, mime_type, file_name=None):
        if not self.settings.engine_is_valid():
            self.log.warning(
                "No valid remote parser engine is configured, content will be empty.",
            )
            self.text = ""
            return
        elif self.settings.engine == "azureai":
            self.text = self.azure_ai_vision_parse(document_path)
