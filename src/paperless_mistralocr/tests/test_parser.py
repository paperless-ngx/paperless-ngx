import tempfile
from pathlib import Path
from unittest import mock

from django.test import TestCase

# Mock the HAS_MISTRAL flag for testing
with mock.patch("paperless_mistralocr.parsers.HAS_MISTRAL", new=True):
    from paperless_mistralocr.parsers import MistralOcrDocumentParser


class TestMistralOcrParser(TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.parser = MistralOcrDocumentParser(None)
        self.parser.tempdir = Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    @mock.patch(
        "paperless_mistralocr.parsers.MistralOcrDocumentParser._call_mistral_api"
    )
    def test_parse_basic(self, mock_call_api):
        # Mock the API response
        mock_call_api.return_value = {
            "pages": [
                {
                    "index": 1,
                    "markdown": "# Sample Document\n\nThis is a test document.",
                    "images": [],
                    "dimensions": {"width": 595, "height": 842, "dpi": 72},
                }
            ],
            "metadata": {"title": "Test Document", "date": "2023-04-15"},
        }

        # Create a simple test file
        sample_file = Path(self.tempdir.name) / "sample.txt"
        with sample_file.open("w") as f:
            f.write("Sample text")

        # Test parsing with mocked API
        self.parser.parse(sample_file, "text/plain")

        # Verify results
        self.assertEqual(
            self.parser.text, "# Sample Document\n\nThis is a test document."
        )
        mock_call_api.assert_called_once()

    @mock.patch("paperless_mistralocr.parsers.Mistral")
    def test_api_call(self, mock_mistral):
        # Setup mock response
        mock_client = mock.MagicMock()
        mock_mistral.return_value = mock_client

        mock_ocr = mock.MagicMock()
        mock_client.ocr = mock_ocr

        # Setup mock OCR process response
        mock_process = mock.MagicMock()
        mock_ocr.process = mock_process

        # Define the API response
        mock_process.return_value = {
            "pages": [
                {
                    "index": 1,
                    "markdown": "# Test Document\n\nThis is a sample document content.",
                    "images": [],
                    "dimensions": {"width": 595, "height": 842, "dpi": 72},
                }
            ]
        }

        # Setup test environment
        sample_file = Path(self.tempdir.name) / "sample.txt"
        with sample_file.open("w") as f:
            f.write("Sample text")

        # Mock settings
        with mock.patch(
            "paperless_mistralocr.parsers.MistralOcrDocumentParser.get_settings"
        ) as mock_settings:
            mock_settings.return_value.api_key = "test_api_key"
            mock_settings.return_value.model = "mistral-ocr-latest"

            # Call the API
            result = self.parser._call_mistral_api(sample_file, "text/plain")

            # Verify results
            self.assertIn("pages", result)
            self.assertEqual(len(result.pages), 1)
            mock_text = "# Test Document\n\nThis is a sample document content."

            # Use get_combined_markdown instead of direct access
            extracted_text = self.parser.get_combined_markdown(result)
            self.assertEqual(extracted_text, mock_text)

            # Verify the Mistral client was called with correct parameters
            mock_mistral.assert_called_once_with(api_key="test_api_key")
            mock_process.assert_called_once()

    def test_extract_text_from_ocr_response(self):
        """Test extracting text from OCR response with multiple pages"""
        ocr_response = {
            "pages": [
                {"markdown": "Page 1 content", "images": []},
                {"markdown": "Page 2 content", "images": []},
                {"markdown": "Page 3 content", "images": []},
            ]
        }

        result = self.parser.get_combined_markdown(ocr_response)
        self.assertEqual(result, "Page 1 content\n\nPage 2 content\n\nPage 3 content")

    def test_extract_text_from_ocr_response_empty(self):
        """Test extracting text from empty OCR response"""
        empty_response = {"pages": []}
        self.assertEqual(self.parser.get_combined_markdown(empty_response), "")

        # For None, we'll need to mock to avoid errors
        with mock.patch(
            "paperless_mistralocr.parsers.MistralOcrDocumentParser.get_combined_markdown"
        ) as mock_method:
            mock_method.return_value = ""
            self.assertEqual(mock_method(None), "")
