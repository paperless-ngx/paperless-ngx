import sys
import uuid
from pathlib import Path
from unittest import mock

import pytest
from django.test import TestCase
from django.test import override_settings

from documents.tests.utils import DirectoriesMixin
from documents.tests.utils import FileSystemAssertsMixin
from paperless_remote.parsers import RemoteDocumentParser


class TestParser(DirectoriesMixin, FileSystemAssertsMixin, TestCase):
    SAMPLE_FILES = Path(__file__).resolve().parent / "samples"

    def assertContainsStrings(self, content, strings):
        # Asserts that all strings appear in content, in the given order.
        indices = []
        for s in strings:
            if s in content:
                indices.append(content.index(s))
            else:
                self.fail(f"'{s}' is not in '{content}'")
        self.assertListEqual(indices, sorted(indices))

    @pytest.mark.skipif(
        sys.version_info > (3, 10),
        reason="Fails on 3.11 only on CI, for some reason",
    )  # TODO: investigate
    @mock.patch("azure.ai.formrecognizer.DocumentAnalysisClient")
    def test_get_text_with_azure(self, mock_azure_client):
        result = mock.Mock()
        result.content = "This is a test document."
        result.pages = [
            mock.Mock(
                width=100,
                height=100,
                words=[
                    mock.Mock(
                        content="This",
                        polygon=[
                            mock.Mock(x=0, y=0),
                        ],
                    ),
                    mock.Mock(
                        content="is",
                        polygon=[
                            mock.Mock(x=10, y=10),
                        ],
                    ),
                    mock.Mock(
                        content="a",
                        polygon=[
                            mock.Mock(x=20, y=20),
                        ],
                    ),
                    mock.Mock(
                        content="test",
                        polygon=[
                            mock.Mock(x=30, y=30),
                        ],
                    ),
                    mock.Mock(
                        content="document.",
                        polygon=[
                            mock.Mock(x=40, y=40),
                        ],
                    ),
                ],
            ),
        ]

        mock_azure_client.return_value.begin_analyze_document.return_value.result.return_value = result

        with override_settings(
            REMOTE_OCR_ENGINE="azureaivision",
            REMOTE_OCR_API_KEY="somekey",
            REMOTE_OCR_ENDPOINT="https://endpoint.cognitiveservices.azure.com/",
        ):
            parser = RemoteDocumentParser(uuid.uuid4())
            parser.parse(
                self.SAMPLE_FILES / "simple-digital.pdf",
                "application/pdf",
            )

            self.assertContainsStrings(
                parser.text.strip(),
                ["This is a test document."],
            )
