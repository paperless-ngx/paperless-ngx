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
    This parser uses a remote OCR engine to parse documents. Currently, it supports Azure AI Vision
    as this is the only service that provides a remote OCR API with text-embedded PDF output.
    """

    logging_name = "paperless.parsing.remote"

    def get_settings(self) -> RemoteEngineConfig:
        """
        Returns the configuration for the remote OCR engine, loaded from Django settings.
        """
        return RemoteEngineConfig(
            engine=settings.REMOTE_OCR_ENGINE,
            api_key=settings.REMOTE_OCR_API_KEY,
            endpoint=settings.REMOTE_OCR_ENDPOINT,
        )

    def supported_mime_types(self):
        if self.settings.engine_is_valid():
            return {
                "application/pdf": ".pdf",
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/tiff": ".tiff",
                "image/bmp": ".bmp",
                "image/gif": ".gif",
                "image/webp": ".webp",
            }
        else:
            return {}

    def azure_ai_vision_parse(
        self,
        file: Path,
    ) -> str | None:
        """
        Uses Azure AI Vision to parse the document and return the text content.
        It requests a searchable PDF output with embedded text.
        The PDF is saved to the archive_path attribute.
        Returns the text content extracted from the document.
        If the parsing fails, it returns None.
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

        try:
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
            self.archive_path = self.tempdir / "archive.pdf"
            with self.archive_path.open("wb") as f:
                for chunk in client.get_analyze_result_pdf(
                    model_id="prebuilt-read",
                    result_id=result_id,
                ):
                    f.write(chunk)
            return result.content
        except Exception as e:
            self.log.error(f"Azure AI Vision parsing failed: {e}")
        finally:
            client.close()

        return None

    def parse(self, document_path: Path, mime_type, file_name=None):
        if not self.settings.engine_is_valid():
            self.log.warning(
                "No valid remote parser engine is configured, content will be empty.",
            )
            self.text = ""
        elif self.settings.engine == "azureai":
            self.text = self.azure_ai_vision_parse(document_path)
