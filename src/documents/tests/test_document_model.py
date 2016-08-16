from unittest import mock

from django.test import TestCase

from ..models import Document, Correspondent


class TestDocument(TestCase):

    def test_file_deletion(self):
        document = Document.objects.create(
            correspondent=Correspondent.objects.create(name="Test0"),
            title="Title",
            content="content",
            checksum="checksum",
        )
        file_path = document.source_path
        with mock.patch("documents.signals.handlers.os.unlink") as mock_unlink:
            document.delete()
            mock_unlink.assert_called_with(file_path)
