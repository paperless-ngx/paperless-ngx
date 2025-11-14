"""
Tests for the scan_documents_ai management command.
"""

from io import StringIO
from unittest import mock

from django.core.management import CommandError
from django.core.management import call_command
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone

from documents.ai_scanner import AIScanResult
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


class TestScanDocumentsAICommand(DirectoriesMixin, TestCase):
    """Test cases for the scan_documents_ai management command."""

    def setUp(self):
        """Set up test data."""
        super().setUp()

        # Create test document types
        self.doc_type_invoice = DocumentType.objects.create(name="Invoice")
        self.doc_type_receipt = DocumentType.objects.create(name="Receipt")

        # Create test tags
        self.tag_important = Tag.objects.create(name="Important")
        self.tag_tax = Tag.objects.create(name="Tax")

        # Create test correspondent
        self.correspondent = Correspondent.objects.create(name="Test Company")

        # Create test documents
        self.doc1 = Document.objects.create(
            title="Test Document 1",
            content="This is a test invoice document with important information.",
            mime_type="application/pdf",
            checksum="ABC123",
        )

        self.doc2 = Document.objects.create(
            title="Test Document 2",
            content="This is another test receipt document.",
            mime_type="application/pdf",
            checksum="DEF456",
            document_type=self.doc_type_receipt,
        )

        self.doc3 = Document.objects.create(
            title="Test Document 3",
            content="A third document for testing date ranges.",
            mime_type="application/pdf",
            checksum="GHI789",
            created=timezone.now() - timezone.timedelta(days=365),
        )

    def test_command_requires_filter(self):
        """Test that command requires at least one filter option."""
        with self.assertRaises(CommandError) as cm:
            call_command("scan_documents_ai")

        self.assertIn("at least one filter", str(cm.exception))

    def test_command_all_flag(self):
        """Test command with --all flag."""
        # Mock the AI scanner
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            # Create a mock scan result
            mock_result = AIScanResult()
            mock_result.tags = [(self.tag_important.id, 0.85)]
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            output = out.getvalue()
            self.assertIn("Processing Complete", output)
            self.assertIn("Documents processed:", output)

    def test_command_filter_by_type(self):
        """Test command with --filter-by-type option."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--filter-by-type",
                str(self.doc_type_receipt.id),
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            # Should only scan doc2 which has the receipt type
            self.assertEqual(mock_instance.scan_document.call_count, 1)

    def test_command_invalid_document_type(self):
        """Test command with invalid document type ID."""
        with self.assertRaises(CommandError) as cm:
            call_command(
                "scan_documents_ai",
                "--filter-by-type",
                "99999",
                "--dry-run",
            )

        self.assertIn("does not exist", str(cm.exception))

    def test_command_date_range(self):
        """Test command with --date-range option."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            # Test with a date range that includes recent documents
            today = timezone.now().date()
            yesterday = (timezone.now() - timezone.timedelta(days=1)).date()

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--date-range",
                str(yesterday),
                str(today),
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            # Should scan doc1 and doc2 (recent), not doc3 (old)
            self.assertGreaterEqual(mock_instance.scan_document.call_count, 2)

    def test_command_invalid_date_range(self):
        """Test command with invalid date range."""
        with self.assertRaises(CommandError) as cm:
            call_command(
                "scan_documents_ai",
                "--date-range",
                "2024-12-31",
                "2024-01-01",  # End before start
                "--dry-run",
            )

        self.assertIn("Start date must be before end date", str(cm.exception))

    def test_command_invalid_date_format(self):
        """Test command with invalid date format."""
        with self.assertRaises(CommandError) as cm:
            call_command(
                "scan_documents_ai",
                "--date-range",
                "01/01/2024",  # Wrong format
                "12/31/2024",
                "--dry-run",
            )

        self.assertIn("Invalid date format", str(cm.exception))

    def test_command_id_range(self):
        """Test command with --id-range option."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--id-range",
                str(self.doc1.id),
                str(self.doc1.id),
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            # Should only scan doc1
            self.assertEqual(mock_instance.scan_document.call_count, 1)

    def test_command_confidence_threshold(self):
        """Test command with custom confidence threshold."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            # Create mock result with low confidence
            mock_result = AIScanResult()
            mock_result.tags = [(self.tag_important.id, 0.50)]  # Low confidence
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--confidence-threshold",
                "0.40",  # Lower threshold
                "--no-progress-bar",
                stdout=out,
            )

            output = out.getvalue()
            # Should show suggestions with low confidence
            self.assertIn("suggestions generated", output.lower())

    def test_command_invalid_confidence_threshold(self):
        """Test command with invalid confidence threshold."""
        with self.assertRaises(CommandError) as cm:
            call_command(
                "scan_documents_ai",
                "--all",
                "--confidence-threshold",
                "1.5",  # Invalid (> 1.0)
                "--dry-run",
            )

        self.assertIn("between 0.0 and 1.0", str(cm.exception))

    def test_command_auto_apply(self):
        """Test command with --auto-apply-high-confidence."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            # Create mock result with high confidence
            mock_result = AIScanResult()
            mock_result.tags = [(self.tag_important.id, 0.90)]
            mock_instance.scan_document.return_value = mock_result

            # Mock apply_scan_results
            mock_instance.apply_scan_results.return_value = {
                "applied": {
                    "tags": [{"id": self.tag_important.id, "name": "Important"}],
                },
                "suggestions": {},
            }

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--auto-apply-high-confidence",
                "--no-progress-bar",
                stdout=out,
            )

            # Should call apply_scan_results with auto_apply=True
            self.assertTrue(mock_instance.apply_scan_results.called)
            call_args = mock_instance.apply_scan_results.call_args
            self.assertTrue(call_args[1]["auto_apply"])

    def test_command_dry_run_does_not_apply(self):
        """Test that dry run mode does not apply changes."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_result.tags = [(self.tag_important.id, 0.90)]
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--auto-apply-high-confidence",  # Should be ignored
                "--no-progress-bar",
                stdout=out,
            )

            # Should not call apply_scan_results in dry-run mode
            self.assertFalse(mock_instance.apply_scan_results.called)

            output = out.getvalue()
            self.assertIn("DRY RUN", output)

    def test_command_handles_document_without_content(self):
        """Test that command handles documents without content gracefully."""
        # Create document without content
        doc_no_content = Document.objects.create(
            title="No Content Doc",
            content="",  # Empty content
            mime_type="application/pdf",
            checksum="EMPTY123",
        )

        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--id-range",
                str(doc_no_content.id),
                str(doc_no_content.id),
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            # Should not call scan_document for empty content
            self.assertEqual(mock_instance.scan_document.call_count, 0)

    def test_command_handles_scanner_error(self):
        """Test that command handles scanner errors gracefully."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            # Make scan_document raise an exception
            mock_instance.scan_document.side_effect = Exception("Scanner error")

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            output = out.getvalue()
            # Should report errors
            self.assertIn("Errors encountered:", output)

    def test_command_batch_processing(self):
        """Test that command processes documents in batches."""
        # Create more documents
        for i in range(10):
            Document.objects.create(
                title=f"Batch Doc {i}",
                content=f"Content {i}",
                mime_type="application/pdf",
                checksum=f"BATCH{i}",
            )

        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--batch-size",
                "5",
                "--no-progress-bar",
                stdout=out,
            )

            # Should process all documents
            self.assertGreaterEqual(mock_instance.scan_document.call_count, 10)

    def test_command_displays_suggestions(self):
        """Test that command displays suggestions in output."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            # Create comprehensive scan result
            mock_result = AIScanResult()
            mock_result.tags = [(self.tag_important.id, 0.85)]
            mock_result.correspondent = (self.correspondent.id, 0.80)
            mock_result.document_type = (self.doc_type_invoice.id, 0.90)
            mock_result.title_suggestion = "Suggested Title"
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            call_command(
                "scan_documents_ai",
                "--id-range",
                str(self.doc1.id),
                str(self.doc1.id),
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            output = out.getvalue()
            # Should display various suggestion types
            self.assertIn("Sample Suggestions", output)
            self.assertIn("Tags:", output)
            self.assertIn("Correspondent:", output)
            self.assertIn("Document Type:", output)

    @override_settings(PAPERLESS_ENABLE_AI_SCANNER=False)
    def test_command_works_when_ai_disabled(self):
        """Test that command can run even if AI scanner is disabled in settings."""
        with mock.patch(
            "documents.management.commands.scan_documents_ai.get_ai_scanner",
        ) as mock_scanner:
            mock_instance = mock.Mock()
            mock_scanner.return_value = mock_instance

            mock_result = AIScanResult()
            mock_instance.scan_document.return_value = mock_result

            out = StringIO()
            # Should not raise an error
            call_command(
                "scan_documents_ai",
                "--all",
                "--dry-run",
                "--no-progress-bar",
                stdout=out,
            )

            output = out.getvalue()
            self.assertIn("Processing Complete", output)
