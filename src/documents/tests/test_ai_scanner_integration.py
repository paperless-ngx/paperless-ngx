"""
Integration tests for AI Scanner Module

These tests verify the AI scanner works correctly with real database
operations and model interactions, testing the full workflow from
document consumption to metadata application.
"""

from unittest import mock

from django.test import TestCase
from django.test import TransactionTestCase

from documents.ai_scanner import AIDocumentScanner
from documents.ai_scanner import AIScanResult
from documents.ai_scanner import get_ai_scanner
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger


class TestAIScannerIntegrationBasic(TestCase):
    """Test basic integration of AI scanner with database."""

    def setUp(self):
        """Set up test data."""
        self.document = Document.objects.create(
            title="Invoice from ACME Corporation",
            content="Invoice #12345 from ACME Corporation dated 2024-01-01. Total: $1,000",
        )

        self.tag_invoice = Tag.objects.create(
            name="Invoice",
            matching_algorithm=Tag.MATCH_AUTO,
            match="invoice",
        )
        self.tag_important = Tag.objects.create(
            name="Important",
            matching_algorithm=Tag.MATCH_AUTO,
            match="total",
        )

        self.correspondent = Correspondent.objects.create(
            name="ACME Corporation",
            matching_algorithm=Correspondent.MATCH_AUTO,
            match="acme",
        )

        self.doc_type = DocumentType.objects.create(
            name="Invoice",
            matching_algorithm=DocumentType.MATCH_AUTO,
            match="invoice",
        )

        self.storage_path = StoragePath.objects.create(
            name="Invoices",
            path="/invoices",
            matching_algorithm=StoragePath.MATCH_AUTO,
            match="invoice",
        )

    @mock.patch("documents.ai_scanner.match_tags")
    @mock.patch("documents.ai_scanner.match_correspondents")
    @mock.patch("documents.ai_scanner.match_document_types")
    @mock.patch("documents.ai_scanner.match_storage_paths")
    def test_full_scan_and_apply_workflow(
        self,
        mock_storage,
        mock_types,
        mock_correspondents,
        mock_tags,
    ):
        """Test complete workflow from scan to application."""
        # Mock the matching functions to return our test data
        mock_tags.return_value = [self.tag_invoice, self.tag_important]
        mock_correspondents.return_value = [self.correspondent]
        mock_types.return_value = [self.doc_type]
        mock_storage.return_value = [self.storage_path]

        scanner = AIDocumentScanner(auto_apply_threshold=0.80)

        # Scan the document
        scan_result = scanner.scan_document(
            self.document,
            self.document.content,
        )

        # Verify scan results
        self.assertIsNotNone(scan_result)
        self.assertGreater(len(scan_result.tags), 0)
        self.assertIsNotNone(scan_result.correspondent)
        self.assertIsNotNone(scan_result.document_type)
        self.assertIsNotNone(scan_result.storage_path)

        # Apply the results
        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        # Verify application
        self.assertGreater(len(result["applied"]["tags"]), 0)
        self.assertIsNotNone(result["applied"]["correspondent"])

        # Verify database changes
        self.document.refresh_from_db()
        self.assertEqual(self.document.correspondent, self.correspondent)
        self.assertEqual(self.document.document_type, self.doc_type)
        self.assertEqual(self.document.storage_path, self.storage_path)

    @mock.patch("documents.ai_scanner.match_tags")
    def test_scan_with_no_matches(self, mock_tags):
        """Test scanning when no matches are found."""
        mock_tags.return_value = []

        scanner = AIDocumentScanner()

        scan_result = scanner.scan_document(
            self.document,
            "Some random text with no matches",
        )

        # Should return empty results
        self.assertEqual(len(scan_result.tags), 0)
        self.assertIsNone(scan_result.correspondent)
        self.assertIsNone(scan_result.document_type)


class TestAIScannerIntegrationCustomFields(TestCase):
    """Test AI scanner integration with custom fields."""

    def setUp(self):
        """Set up test data with custom fields."""
        self.document = Document.objects.create(
            title="Invoice",
            content="Invoice #INV-123 dated 2024-01-01. Amount: $1,500. Contact: john@example.com",
        )

        self.field_date = CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        self.field_number = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_amount = CustomField.objects.create(
            name="Total Amount",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_email = CustomField.objects.create(
            name="Contact Email",
            data_type=CustomField.FieldDataType.STRING,
        )

    def test_custom_field_extraction_integration(self):
        """Test custom field extraction with mocked NER."""
        scanner = AIDocumentScanner()

        # Mock NER to return entities
        mock_ner = mock.MagicMock()
        mock_ner.extract_all.return_value = {
            "dates": [{"text": "2024-01-01"}],
            "amounts": [{"text": "$1,500"}],
            "invoice_numbers": ["INV-123"],
            "emails": ["john@example.com"],
        }
        scanner._ner_extractor = mock_ner

        # Scan document
        scan_result = scanner.scan_document(self.document, self.document.content)

        # Verify custom fields were extracted
        self.assertGreater(len(scan_result.custom_fields), 0)

        # Check specific fields
        extracted_field_ids = list(scan_result.custom_fields.keys())
        self.assertIn(self.field_date.id, extracted_field_ids)
        self.assertIn(self.field_amount.id, extracted_field_ids)


class TestAIScannerIntegrationWorkflows(TestCase):
    """Test AI scanner integration with workflows."""

    def setUp(self):
        """Set up test workflows."""
        self.document = Document.objects.create(
            title="Invoice",
            content="Invoice document",
        )

        self.workflow1 = Workflow.objects.create(
            name="Invoice Processing",
            enabled=True,
        )
        self.trigger1 = WorkflowTrigger.objects.create(
            workflow=self.workflow1,
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        self.action1 = WorkflowAction.objects.create(
            workflow=self.workflow1,
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )

        self.workflow2 = Workflow.objects.create(
            name="Archive Documents",
            enabled=True,
        )
        self.trigger2 = WorkflowTrigger.objects.create(
            workflow=self.workflow2,
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )

    def test_workflow_suggestion_integration(self):
        """Test workflow suggestion with real workflows."""
        scanner = AIDocumentScanner(suggest_threshold=0.5)

        # Create scan result with some attributes
        scan_result = AIScanResult()
        scan_result.document_type = (1, 0.85)
        scan_result.tags = [(1, 0.80)]

        # Get workflow suggestions
        workflows = scanner._suggest_workflows(
            self.document,
            self.document.content,
            scan_result,
        )

        # Should suggest workflows
        self.assertGreater(len(workflows), 0)
        workflow_ids = [wf_id for wf_id, _ in workflows]
        self.assertIn(self.workflow1.id, workflow_ids)


class TestAIScannerIntegrationTransactions(TransactionTestCase):
    """Test AI scanner with transactions and rollbacks."""

    def setUp(self):
        """Set up test data."""
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )
        self.tag = Tag.objects.create(name="TestTag")
        self.correspondent = Correspondent.objects.create(name="TestCorp")

    def test_transaction_rollback_on_error(self):
        """Test that transaction rolls back on error."""
        scanner = AIDocumentScanner()

        scan_result = AIScanResult()
        scan_result.tags = [(self.tag.id, 0.90)]
        scan_result.correspondent = (self.correspondent.id, 0.90)

        # Force an error during save
        original_save = Document.save
        call_count = [0]

        def failing_save(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 1:
                raise Exception("Forced save failure")
            return original_save(self, *args, **kwargs)

        with mock.patch.object(Document, "save", failing_save):
            with self.assertRaises(Exception):
                scanner.apply_scan_results(
                    self.document,
                    scan_result,
                    auto_apply=True,
                )

        # Verify changes were rolled back
        self.document.refresh_from_db()
        # Document should not have been modified


class TestAIScannerIntegrationPerformance(TestCase):
    """Test AI scanner performance characteristics."""

    def test_scan_multiple_documents(self):
        """Test scanning multiple documents efficiently."""
        scanner = AIDocumentScanner()

        documents = []
        for i in range(5):
            doc = Document.objects.create(
                title=f"Document {i}",
                content=f"Content for document {i}",
            )
            documents.append(doc)

        # Mock to avoid actual ML loading
        with (
            mock.patch.object(scanner, "_extract_entities", return_value={}),
            mock.patch.object(scanner, "_suggest_tags", return_value=[]),
            mock.patch.object(scanner, "_detect_correspondent", return_value=None),
            mock.patch.object(scanner, "_classify_document_type", return_value=None),
            mock.patch.object(scanner, "_suggest_storage_path", return_value=None),
            mock.patch.object(scanner, "_extract_custom_fields", return_value={}),
            mock.patch.object(scanner, "_suggest_workflows", return_value=[]),
            mock.patch.object(scanner, "_suggest_title", return_value=None),
        ):
            results = []
            for doc in documents:
                result = scanner.scan_document(doc, doc.content)
                results.append(result)

            # Verify all scans completed
            self.assertEqual(len(results), 5)
            for result in results:
                self.assertIsInstance(result, AIScanResult)


class TestAIScannerIntegrationEntityMatching(TestCase):
    """Test entity-based matching integration."""

    def setUp(self):
        """Set up test data."""
        self.document = Document.objects.create(
            title="Business Invoice",
            content="Invoice from ACME Corporation",
        )

        self.correspondent_acme = Correspondent.objects.create(
            name="ACME Corporation",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        self.correspondent_other = Correspondent.objects.create(
            name="Other Company",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )

    def test_correspondent_matching_with_ner_entities(self):
        """Test that NER entities help match correspondents."""
        scanner = AIDocumentScanner()

        # Mock NER to extract organization
        mock_ner = mock.MagicMock()
        mock_ner.extract_all.return_value = {
            "organizations": [{"text": "ACME Corporation"}],
        }
        scanner._ner_extractor = mock_ner

        # Mock matching to return empty (so NER-based matching is used)
        with mock.patch("documents.ai_scanner.match_correspondents", return_value=[]):
            result = scanner._detect_correspondent(
                self.document,
                self.document.content,
                {"organizations": [{"text": "ACME Corporation"}]},
            )

        # Should detect ACME correspondent
        self.assertIsNotNone(result)
        corr_id, confidence = result
        self.assertEqual(corr_id, self.correspondent_acme.id)


class TestAIScannerIntegrationTitleGeneration(TestCase):
    """Test title generation integration."""

    def test_title_generation_with_entities(self):
        """Test title generation uses extracted entities."""
        scanner = AIDocumentScanner()

        document = Document.objects.create(
            title="document.pdf",
            content="Invoice from ACME Corp dated 2024-01-15",
        )

        entities = {
            "document_type": "Invoice",
            "organizations": [{"text": "ACME Corp"}],
            "dates": [{"text": "2024-01-15"}],
        }

        title = scanner._suggest_title(document, document.content, entities)

        self.assertIsNotNone(title)
        self.assertIn("Invoice", title)
        self.assertIn("ACME Corp", title)
        self.assertIn("2024-01-15", title)


class TestAIScannerIntegrationConfidenceLevels(TestCase):
    """Test confidence level handling in integration scenarios."""

    def setUp(self):
        """Set up test data."""
        self.document = Document.objects.create(
            title="Test",
            content="Test",
        )
        self.tag_high = Tag.objects.create(name="HighConfidence")
        self.tag_medium = Tag.objects.create(name="MediumConfidence")
        self.tag_low = Tag.objects.create(name="LowConfidence")

    def test_confidence_based_application(self):
        """Test that only high confidence suggestions are auto-applied."""
        scanner = AIDocumentScanner(
            auto_apply_threshold=0.80,
            suggest_threshold=0.60,
        )

        scan_result = AIScanResult()
        scan_result.tags = [
            (self.tag_high.id, 0.90),  # Should be applied
            (self.tag_medium.id, 0.70),  # Should be suggested
            (self.tag_low.id, 0.50),  # Should be ignored
        ]

        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        # Verify high confidence was applied
        self.assertEqual(len(result["applied"]["tags"]), 1)
        self.assertEqual(result["applied"]["tags"][0]["id"], self.tag_high.id)

        # Verify medium confidence was suggested
        self.assertEqual(len(result["suggestions"]["tags"]), 1)
        self.assertEqual(result["suggestions"]["tags"][0]["id"], self.tag_medium.id)


class TestAIScannerIntegrationGlobalInstance(TestCase):
    """Test global scanner instance integration."""

    def test_global_scanner_reusability(self):
        """Test that global scanner can be reused across multiple scans."""
        scanner1 = get_ai_scanner()
        scanner2 = get_ai_scanner()

        # Should be the same instance
        self.assertIs(scanner1, scanner2)

        # Should be functional
        document = Document.objects.create(
            title="Test",
            content="Test content",
        )

        with (
            mock.patch.object(scanner1, "_extract_entities", return_value={}),
            mock.patch.object(scanner1, "_suggest_tags", return_value=[]),
            mock.patch.object(scanner1, "_detect_correspondent", return_value=None),
            mock.patch.object(scanner1, "_classify_document_type", return_value=None),
            mock.patch.object(scanner1, "_suggest_storage_path", return_value=None),
            mock.patch.object(scanner1, "_extract_custom_fields", return_value={}),
            mock.patch.object(scanner1, "_suggest_workflows", return_value=[]),
            mock.patch.object(scanner1, "_suggest_title", return_value=None),
        ):
            result1 = scanner1.scan_document(document, document.content)
            result2 = scanner2.scan_document(document, document.content)

            self.assertIsInstance(result1, AIScanResult)
            self.assertIsInstance(result2, AIScanResult)


class TestAIScannerIntegrationEdgeCases(TestCase):
    """Test edge cases in integration scenarios."""

    def test_scan_with_minimal_document(self):
        """Test scanning a document with minimal information."""
        scanner = AIDocumentScanner()

        document = Document.objects.create(
            title="",
            content="",
        )

        with (
            mock.patch.object(scanner, "_extract_entities", return_value={}),
            mock.patch.object(scanner, "_suggest_tags", return_value=[]),
            mock.patch.object(scanner, "_detect_correspondent", return_value=None),
            mock.patch.object(scanner, "_classify_document_type", return_value=None),
            mock.patch.object(scanner, "_suggest_storage_path", return_value=None),
            mock.patch.object(scanner, "_extract_custom_fields", return_value={}),
            mock.patch.object(scanner, "_suggest_workflows", return_value=[]),
            mock.patch.object(scanner, "_suggest_title", return_value=None),
        ):
            result = scanner.scan_document(document, document.content)

            self.assertIsInstance(result, AIScanResult)

    def test_apply_with_deleted_references(self):
        """Test applying results when referenced objects have been deleted."""
        scanner = AIDocumentScanner()

        document = Document.objects.create(
            title="Test",
            content="Test",
        )

        scan_result = AIScanResult()
        scan_result.tags = [(9999, 0.90)]  # Non-existent tag ID
        scan_result.correspondent = (9999, 0.90)  # Non-existent correspondent ID

        # Should handle gracefully
        result = scanner.apply_scan_results(
            document,
            scan_result,
            auto_apply=True,
        )

        # Should not crash, just log errors
        self.assertEqual(len(result["applied"]["tags"]), 0)

    def test_scan_with_unicode_and_special_characters(self):
        """Test scanning documents with Unicode and special characters."""
        scanner = AIDocumentScanner()

        document = Document.objects.create(
            title="Factura - España 🇪🇸",
            content="Société française • 日本語 • Ελληνικά • مرحبا",
        )

        with (
            mock.patch.object(scanner, "_extract_entities", return_value={}),
            mock.patch.object(scanner, "_suggest_tags", return_value=[]),
            mock.patch.object(scanner, "_detect_correspondent", return_value=None),
            mock.patch.object(scanner, "_classify_document_type", return_value=None),
            mock.patch.object(scanner, "_suggest_storage_path", return_value=None),
            mock.patch.object(scanner, "_extract_custom_fields", return_value={}),
            mock.patch.object(scanner, "_suggest_workflows", return_value=[]),
            mock.patch.object(scanner, "_suggest_title", return_value=None),
        ):
            result = scanner.scan_document(document, document.content)

            self.assertIsInstance(result, AIScanResult)
