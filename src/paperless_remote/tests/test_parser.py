import uuid
from pathlib import Path
from unittest import mock

from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_remote.parsers import RemoteDocumentParser
from paperless_remote.signals import get_parser


class TestParser(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_FILES = Path(__file__).resolve().parent / "samples"

    def assertContainsStrings(self, content: str, strings: list[str]):
        # Asserts that all strings appear in content, in the given order.
        indices = []
        for s in strings:
            if s in content:
                indices.append(content.index(s))
            else:
                self.fail(f"'{s}' is not in '{content}'")
        self.assertListEqual(indices, sorted(indices))

    @mock.patch("paperless_tesseract.parsers.run_subprocess")
    @mock.patch("azure.ai.documentintelligence.DocumentIntelligenceClient")
    def test_get_text_with_azure(self, mock_client_cls, mock_subprocess):
        # Arrange mock Azure client
        mock_client = mock.Mock()
        mock_client_cls.return_value = mock_client

        # Simulate poller result and its `.details`
        mock_poller = mock.Mock()
        mock_poller.wait.return_value = None
        mock_poller.details = {"operation_id": "fake-op-id"}
        mock_client.begin_analyze_document.return_value = mock_poller
        mock_poller.result.return_value.content = "This is a test document."

        # Return dummy PDF bytes
        mock_client.get_analyze_result_pdf.return_value = [
            b"%PDF-",
            b"1.7 ",
            b"FAKEPDF",
        ]

        # Simulate pdftotext by writing dummy text to sidecar file
        def fake_run(cmd, *args, **kwargs):
            with Path(cmd[-1]).open("w", encoding="utf-8") as f:
                f.write("This is a test document.")

        mock_subprocess.side_effect = fake_run

        with override_settings(
            REMOTE_OCR_ENGINE="azureai",
            REMOTE_OCR_API_KEY="somekey",
            REMOTE_OCR_ENDPOINT="https://endpoint.cognitiveservices.azure.com",
        ):
            parser = get_parser(uuid.uuid4())
            parser.parse(
                self.SAMPLE_FILES / "simple-digital.pdf",
                "application/pdf",
            )

            self.assertContainsStrings(
                parser.text.strip(),
                ["This is a test document."],
            )

    @override_settings(
        REMOTE_OCR_ENGINE="azureai",
        REMOTE_OCR_API_KEY="key",
        REMOTE_OCR_ENDPOINT="https://endpoint.cognitiveservices.azure.com",
    )
    def test_supported_mime_types_valid_config(self):
        parser = RemoteDocumentParser(uuid.uuid4())
        expected_types = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/tiff": ".tiff",
            "image/bmp": ".bmp",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        self.assertEqual(parser.supported_mime_types(), expected_types)

    def test_supported_mime_types_invalid_config(self):
        parser = get_parser(uuid.uuid4())
        self.assertEqual(parser.supported_mime_types(), {})

    @override_settings(
        REMOTE_OCR_ENGINE=None,
        REMOTE_OCR_API_KEY=None,
        REMOTE_OCR_ENDPOINT=None,
    )
    def test_parse_with_invalid_config(self):
        parser = get_parser(uuid.uuid4())
        parser.parse(self.SAMPLE_FILES / "simple-digital.pdf", "application/pdf")
        self.assertEqual(parser.text, "")
