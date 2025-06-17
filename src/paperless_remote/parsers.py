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
        from azure.ai.documentintelligence.models import AnalyzeDocumentRequest
        from azure.ai.documentintelligence.models import AnalyzeOutputOption
        from azure.ai.documentintelligence.models import DocumentContentFormat
        from azure.core.credentials import AzureKeyCredential

        client = DocumentIntelligenceClient(
            endpoint=self.settings.endpoint,
            credential=AzureKeyCredential(self.settings.api_key),
        )

        with file.open("rb") as f:
            analyze_request = AnalyzeDocumentRequest(bytes_source=f.read())
            poller = client.begin_analyze_document(
                model_id="prebuilt-read",
                body=analyze_request,
                output_content_format=DocumentContentFormat.TEXT,
                output=[AnalyzeOutputOption.PDF],  # request searchable PDF output
                content_type="application/json",
            )

        poller.wait()
        result_id = poller.details["operation_id"]
        result = poller.result()

        # Download the PDF with embedded text
        self.archive_path = Path(self.tempdir) / "archive.pdf"
        with self.archive_path.open("wb") as f:
            for chunk in client.get_analyze_result_pdf(
                model_id="prebuilt-read",
                result_id=result_id,
            ):
                f.write(chunk)

        return result.content

    def parse(self, document_path: Path, mime_type, file_name=None):
        if not self.settings.engine_is_valid():
            self.log.warning(
                "No valid remote parser engine is configured, content will be empty.",
            )
            self.text = ""
            return
        elif self.settings.engine == "azureai":
            self.text = self.azure_ai_vision_parse(document_path)
