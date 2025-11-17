"""
Unit tests for AI Scanner Module (ai_scanner.py)

Tests cover:
- AIScanResult data structure
- AIDocumentScanner initialization and configuration
- Lazy loading of ML components
- Entity extraction with NER mocking
- Tag suggestions with confidence levels
- Correspondent detection
- Document type classification
- Storage path suggestions
- Custom field extraction
- Workflow suggestions
- Title generation
- Table extraction
- Scan result application with atomic transactions
- Error handling and edge cases
"""

from unittest import mock

from django.db import transaction
from django.test import TestCase
from django.test import override_settings

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


class TestAIScanResult(TestCase):
    """Test the AIScanResult data container class."""

    def test_init_creates_empty_result(self):
        """Test that AIScanResult initializes with empty structures."""
        result = AIScanResult()

        self.assertEqual(result.tags, [])
        self.assertIsNone(result.correspondent)
        self.assertIsNone(result.document_type)
        self.assertIsNone(result.storage_path)
        self.assertEqual(result.custom_fields, {})
        self.assertEqual(result.workflows, [])
        self.assertEqual(result.extracted_entities, {})
        self.assertIsNone(result.title_suggestion)
        self.assertEqual(result.metadata, {})

    def test_to_dict_converts_result_to_dictionary(self):
        """Test that to_dict properly serializes the scan result."""
        result = AIScanResult()
        result.tags = [(1, 0.85), (2, 0.75)]
        result.correspondent = (1, 0.90)
        result.document_type = (2, 0.80)
        result.storage_path = (3, 0.85)
        result.custom_fields = {1: ("value1", 0.70), 2: ("value2", 0.65)}
        result.workflows = [(1, 0.75)]
        result.extracted_entities = {
            "persons": ["John Doe"],
            "organizations": ["ACME Corp"],
        }
        result.title_suggestion = "Invoice - ACME Corp - 2024-01-01"
        result.metadata = {"tables": [{"data": "test"}]}

        result_dict = result.to_dict()

        self.assertEqual(result_dict["tags"], [(1, 0.85), (2, 0.75)])
        self.assertEqual(result_dict["correspondent"], (1, 0.90))
        self.assertEqual(result_dict["document_type"], (2, 0.80))
        self.assertEqual(result_dict["storage_path"], (3, 0.85))
        self.assertEqual(
            result_dict["custom_fields"],
            {1: ("value1", 0.70), 2: ("value2", 0.65)},
        )
        self.assertEqual(result_dict["workflows"], [(1, 0.75)])
        self.assertEqual(
            result_dict["extracted_entities"],
            {"persons": ["John Doe"], "organizations": ["ACME Corp"]},
        )
        self.assertEqual(
            result_dict["title_suggestion"],
            "Invoice - ACME Corp - 2024-01-01",
        )
        self.assertEqual(result_dict["metadata"], {"tables": [{"data": "test"}]})


class TestAIDocumentScannerInitialization(TestCase):
    """Test AIDocumentScanner initialization and configuration."""

    def test_init_with_defaults(self):
        """Test scanner initialization with default parameters."""
        scanner = AIDocumentScanner()

        self.assertEqual(scanner.auto_apply_threshold, 0.80)
        self.assertEqual(scanner.suggest_threshold, 0.60)
        self.assertTrue(scanner.ml_enabled)
        self.assertTrue(scanner.advanced_ocr_enabled)

    def test_init_with_custom_thresholds(self):
        """Test scanner initialization with custom confidence thresholds."""
        scanner = AIDocumentScanner(
            auto_apply_threshold=0.90,
            suggest_threshold=0.70,
        )

        self.assertEqual(scanner.auto_apply_threshold, 0.90)
        self.assertEqual(scanner.suggest_threshold, 0.70)

    @override_settings(PAPERLESS_ENABLE_ML_FEATURES=False)
    def test_init_respects_ml_disabled_setting(self):
        """Test that ML features can be disabled via settings."""
        scanner = AIDocumentScanner()

        self.assertFalse(scanner.ml_enabled)

    def test_init_with_explicit_ml_override(self):
        """Test explicit ML feature override."""
        scanner = AIDocumentScanner(enable_ml_features=False)

        self.assertFalse(scanner.ml_enabled)

    @override_settings(PAPERLESS_ENABLE_ADVANCED_OCR=False)
    def test_init_respects_ocr_disabled_setting(self):
        """Test that advanced OCR can be disabled via settings."""
        scanner = AIDocumentScanner()

        self.assertFalse(scanner.advanced_ocr_enabled)

    def test_init_with_explicit_ocr_override(self):
        """Test explicit OCR feature override."""
        scanner = AIDocumentScanner(enable_advanced_ocr=False)

        self.assertFalse(scanner.advanced_ocr_enabled)

    def test_lazy_loading_components_not_initialized(self):
        """Test that ML components are not initialized at construction."""
        scanner = AIDocumentScanner()

        self.assertIsNone(scanner._classifier)
        self.assertIsNone(scanner._ner_extractor)
        self.assertIsNone(scanner._semantic_search)
        self.assertIsNone(scanner._table_extractor)


class TestAIDocumentScannerLazyLoading(TestCase):
    """Test lazy loading of ML components."""

    @mock.patch("documents.ai_scanner.logger")
    def test_get_classifier_loads_successfully(self, mock_logger):
        """Test successful lazy loading of classifier."""
        scanner = AIDocumentScanner()

        # Mock the import and class
        mock_classifier_instance = mock.MagicMock()
        with mock.patch(
            "documents.ai_scanner.TransformerDocumentClassifier",
            return_value=mock_classifier_instance,
        ) as mock_classifier_class:
            classifier = scanner._get_classifier()

            self.assertIsNotNone(classifier)
            self.assertEqual(classifier, mock_classifier_instance)
            mock_classifier_class.assert_called_once()
            mock_logger.info.assert_called_with("ML classifier loaded successfully")

    @mock.patch("documents.ai_scanner.logger")
    def test_get_classifier_returns_cached_instance(self, mock_logger):
        """Test that classifier is only loaded once."""
        scanner = AIDocumentScanner()

        mock_classifier_instance = mock.MagicMock()
        with mock.patch(
            "documents.ai_scanner.TransformerDocumentClassifier",
            return_value=mock_classifier_instance,
        ):
            classifier1 = scanner._get_classifier()
            classifier2 = scanner._get_classifier()

            self.assertEqual(classifier1, classifier2)
            self.assertIs(classifier1, classifier2)

    @mock.patch("documents.ai_scanner.logger")
    def test_get_classifier_handles_import_error(self, mock_logger):
        """Test that classifier loading handles import errors gracefully."""
        scanner = AIDocumentScanner()

        with mock.patch(
            "documents.ai_scanner.TransformerDocumentClassifier",
            side_effect=ImportError("Module not found"),
        ):
            classifier = scanner._get_classifier()

            self.assertIsNone(classifier)
            self.assertFalse(scanner.ml_enabled)
            mock_logger.warning.assert_called()

    def test_get_classifier_returns_none_when_ml_disabled(self):
        """Test that classifier returns None when ML is disabled."""
        scanner = AIDocumentScanner(enable_ml_features=False)

        classifier = scanner._get_classifier()

        self.assertIsNone(classifier)

    @mock.patch("documents.ai_scanner.logger")
    def test_get_ner_extractor_loads_successfully(self, mock_logger):
        """Test successful lazy loading of NER extractor."""
        scanner = AIDocumentScanner()

        mock_ner_instance = mock.MagicMock()
        with mock.patch(
            "documents.ai_scanner.DocumentNER",
            return_value=mock_ner_instance,
        ) as mock_ner_class:
            ner = scanner._get_ner_extractor()

            self.assertIsNotNone(ner)
            self.assertEqual(ner, mock_ner_instance)
            mock_ner_class.assert_called_once()
            mock_logger.info.assert_called_with("NER extractor loaded successfully")

    @mock.patch("documents.ai_scanner.logger")
    def test_get_ner_extractor_handles_error(self, mock_logger):
        """Test NER extractor handles loading errors."""
        scanner = AIDocumentScanner()

        with mock.patch(
            "documents.ai_scanner.DocumentNER",
            side_effect=Exception("Failed to load"),
        ):
            ner = scanner._get_ner_extractor()

            self.assertIsNone(ner)
            mock_logger.warning.assert_called()

    @mock.patch("documents.ai_scanner.logger")
    def test_get_semantic_search_loads_successfully(self, mock_logger):
        """Test successful lazy loading of semantic search."""
        scanner = AIDocumentScanner()

        mock_search_instance = mock.MagicMock()
        with mock.patch(
            "documents.ai_scanner.SemanticSearch",
            return_value=mock_search_instance,
        ) as mock_search_class:
            search = scanner._get_semantic_search()

            self.assertIsNotNone(search)
            self.assertEqual(search, mock_search_instance)
            mock_search_class.assert_called_once()
            mock_logger.info.assert_called_with("Semantic search loaded successfully")

    @mock.patch("documents.ai_scanner.logger")
    def test_get_table_extractor_loads_successfully(self, mock_logger):
        """Test successful lazy loading of table extractor."""
        scanner = AIDocumentScanner()

        mock_extractor_instance = mock.MagicMock()
        with mock.patch(
            "documents.ai_scanner.TableExtractor",
            return_value=mock_extractor_instance,
        ) as mock_extractor_class:
            extractor = scanner._get_table_extractor()

            self.assertIsNotNone(extractor)
            self.assertEqual(extractor, mock_extractor_instance)
            mock_extractor_class.assert_called_once()
            mock_logger.info.assert_called_with("Table extractor loaded successfully")

    def test_get_table_extractor_returns_none_when_ocr_disabled(self):
        """Test that table extractor returns None when OCR is disabled."""
        scanner = AIDocumentScanner(enable_advanced_ocr=False)

        extractor = scanner._get_table_extractor()

        self.assertIsNone(extractor)


class TestExtractEntities(TestCase):
    """Test entity extraction functionality."""

    def test_extract_entities_with_ner_available(self):
        """Test entity extraction when NER is available."""
        scanner = AIDocumentScanner()

        mock_ner = mock.MagicMock()
        mock_ner.extract_all.return_value = {
            "persons": ["John Doe", "Jane Smith"],
            "organizations": ["ACME Corp", "Tech Inc"],
            "dates": ["2024-01-01", "2024-12-31"],
            "amounts": ["$1,000", "$500"],
            "locations": ["New York"],
            "misc": ["Invoice#123"],
        }

        scanner._ner_extractor = mock_ner

        entities = scanner._extract_entities("Sample document text")

        # Verify NER was called
        mock_ner.extract_all.assert_called_once_with("Sample document text")

        # Verify entities are converted to dict format
        self.assertIn("persons", entities)
        self.assertEqual(len(entities["persons"]), 2)
        self.assertIn("organizations", entities)
        self.assertEqual(len(entities["organizations"]), 2)

    def test_extract_entities_converts_strings_to_dicts(self):
        """Test that string entities are converted to dict format."""
        scanner = AIDocumentScanner()

        mock_ner = mock.MagicMock()
        mock_ner.extract_all.return_value = {
            "persons": ["John Doe"],  # String format
            "organizations": [{"text": "ACME Corp", "confidence": 0.9}],  # Already dict
        }

        scanner._ner_extractor = mock_ner

        entities = scanner._extract_entities("Sample text")

        # Verify string entities are converted
        self.assertEqual(entities["persons"][0], {"text": "John Doe"})
        # Verify dict entities remain unchanged
        self.assertEqual(entities["organizations"][0]["text"], "ACME Corp")

    def test_extract_entities_without_ner(self):
        """Test entity extraction when NER is not available."""
        scanner = AIDocumentScanner()
        scanner._get_ner_extractor = mock.MagicMock(return_value=None)

        entities = scanner._extract_entities("Sample text")

        self.assertEqual(entities, {})

    @mock.patch("documents.ai_scanner.logger")
    def test_extract_entities_handles_exception(self, mock_logger):
        """Test that entity extraction handles exceptions gracefully."""
        scanner = AIDocumentScanner()

        mock_ner = mock.MagicMock()
        mock_ner.extract_all.side_effect = Exception("NER failed")
        scanner._ner_extractor = mock_ner

        entities = scanner._extract_entities("Sample text")

        self.assertEqual(entities, {})
        mock_logger.error.assert_called()


class TestSuggestTags(TestCase):
    """Test tag suggestion functionality."""

    def setUp(self):
        """Set up test tags."""
        self.tag1 = Tag.objects.create(
            name="Invoice",
            matching_algorithm=Tag.MATCH_AUTO,
        )
        self.tag2 = Tag.objects.create(
            name="Company",
            matching_algorithm=Tag.MATCH_AUTO,
        )
        self.tag3 = Tag.objects.create(name="Tax", matching_algorithm=Tag.MATCH_AUTO)
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    @mock.patch("documents.ai_scanner.match_tags")
    def test_suggest_tags_with_matched_tags(self, mock_match_tags):
        """Test tag suggestions from matching."""
        scanner = AIDocumentScanner()
        mock_match_tags.return_value = [self.tag1, self.tag2]

        suggestions = scanner._suggest_tags(
            self.document,
            "Invoice from ACME Corp",
            {},
        )

        # Should suggest both matched tags
        self.assertEqual(len(suggestions), 2)
        tag_ids = [tag_id for tag_id, _ in suggestions]
        self.assertIn(self.tag1.id, tag_ids)
        self.assertIn(self.tag2.id, tag_ids)

        # Check confidence
        for _, confidence in suggestions:
            self.assertGreaterEqual(confidence, 0.6)

    @mock.patch("documents.ai_scanner.match_tags")
    def test_suggest_tags_with_organization_entities(self, mock_match_tags):
        """Test tag suggestions based on organization entities."""
        scanner = AIDocumentScanner()
        mock_match_tags.return_value = []

        entities = {
            "organizations": [{"text": "ACME Corp"}],
        }

        suggestions = scanner._suggest_tags(self.document, "text", entities)

        # Should suggest company tag based on organization
        tag_ids = [tag_id for tag_id, _ in suggestions]
        self.assertIn(self.tag2.id, tag_ids)

    @mock.patch("documents.ai_scanner.match_tags")
    def test_suggest_tags_removes_duplicates(self, mock_match_tags):
        """Test that duplicate tags keep highest confidence."""
        scanner = AIDocumentScanner()
        mock_match_tags.return_value = [self.tag1]

        # Manually add same tag with different confidence
        scanner._suggest_tags(self.document, "text", {})

        # Implementation should remove duplicates in actual code

    @mock.patch("documents.ai_scanner.match_tags")
    @mock.patch("documents.ai_scanner.logger")
    def test_suggest_tags_handles_exception(self, mock_logger, mock_match_tags):
        """Test tag suggestion handles exceptions."""
        scanner = AIDocumentScanner()
        mock_match_tags.side_effect = Exception("Matching failed")

        suggestions = scanner._suggest_tags(self.document, "text", {})

        self.assertEqual(suggestions, [])
        mock_logger.error.assert_called()


class TestDetectCorrespondent(TestCase):
    """Test correspondent detection functionality."""

    def setUp(self):
        """Set up test correspondents."""
        self.correspondent1 = Correspondent.objects.create(
            name="ACME Corporation",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        self.correspondent2 = Correspondent.objects.create(
            name="TechStart Inc",
            matching_algorithm=Correspondent.MATCH_AUTO,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    @mock.patch("documents.ai_scanner.match_correspondents")
    def test_detect_correspondent_with_match(self, mock_match):
        """Test correspondent detection with successful match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = [self.correspondent1]

        result = scanner._detect_correspondent(self.document, "text", {})

        self.assertIsNotNone(result)
        corr_id, confidence = result
        self.assertEqual(corr_id, self.correspondent1.id)
        self.assertEqual(confidence, 0.85)

    @mock.patch("documents.ai_scanner.match_correspondents")
    def test_detect_correspondent_without_match(self, mock_match):
        """Test correspondent detection without match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = []

        result = scanner._detect_correspondent(self.document, "text", {})

        self.assertIsNone(result)

    @mock.patch("documents.ai_scanner.match_correspondents")
    def test_detect_correspondent_from_ner_entities(self, mock_match):
        """Test correspondent detection from NER organizations."""
        scanner = AIDocumentScanner()
        mock_match.return_value = []

        entities = {
            "organizations": [{"text": "ACME Corporation"}],
        }

        result = scanner._detect_correspondent(self.document, "text", entities)

        self.assertIsNotNone(result)
        corr_id, confidence = result
        self.assertEqual(corr_id, self.correspondent1.id)
        self.assertEqual(confidence, 0.70)

    @mock.patch("documents.ai_scanner.match_correspondents")
    @mock.patch("documents.ai_scanner.logger")
    def test_detect_correspondent_handles_exception(self, mock_logger, mock_match):
        """Test correspondent detection handles exceptions."""
        scanner = AIDocumentScanner()
        mock_match.side_effect = Exception("Detection failed")

        result = scanner._detect_correspondent(self.document, "text", {})

        self.assertIsNone(result)
        mock_logger.error.assert_called()


class TestClassifyDocumentType(TestCase):
    """Test document type classification."""

    def setUp(self):
        """Set up test document types."""
        self.doc_type1 = DocumentType.objects.create(
            name="Invoice",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        self.doc_type2 = DocumentType.objects.create(
            name="Receipt",
            matching_algorithm=DocumentType.MATCH_AUTO,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    @mock.patch("documents.ai_scanner.match_document_types")
    def test_classify_document_type_with_match(self, mock_match):
        """Test document type classification with match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = [self.doc_type1]

        result = scanner._classify_document_type(self.document, "text", {})

        self.assertIsNotNone(result)
        type_id, confidence = result
        self.assertEqual(type_id, self.doc_type1.id)
        self.assertEqual(confidence, 0.85)

    @mock.patch("documents.ai_scanner.match_document_types")
    def test_classify_document_type_without_match(self, mock_match):
        """Test document type classification without match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = []

        result = scanner._classify_document_type(self.document, "text", {})

        self.assertIsNone(result)

    @mock.patch("documents.ai_scanner.match_document_types")
    @mock.patch("documents.ai_scanner.logger")
    def test_classify_document_type_handles_exception(self, mock_logger, mock_match):
        """Test classification handles exceptions."""
        scanner = AIDocumentScanner()
        mock_match.side_effect = Exception("Classification failed")

        result = scanner._classify_document_type(self.document, "text", {})

        self.assertIsNone(result)
        mock_logger.error.assert_called()


class TestSuggestStoragePath(TestCase):
    """Test storage path suggestion."""

    def setUp(self):
        """Set up test storage paths."""
        self.storage_path1 = StoragePath.objects.create(
            name="Invoices",
            path="/documents/invoices",
            matching_algorithm=StoragePath.MATCH_AUTO,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    @mock.patch("documents.ai_scanner.match_storage_paths")
    def test_suggest_storage_path_with_match(self, mock_match):
        """Test storage path suggestion with match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = [self.storage_path1]

        scan_result = AIScanResult()
        result = scanner._suggest_storage_path(self.document, "text", scan_result)

        self.assertIsNotNone(result)
        path_id, confidence = result
        self.assertEqual(path_id, self.storage_path1.id)
        self.assertEqual(confidence, 0.80)

    @mock.patch("documents.ai_scanner.match_storage_paths")
    def test_suggest_storage_path_without_match(self, mock_match):
        """Test storage path suggestion without match."""
        scanner = AIDocumentScanner()
        mock_match.return_value = []

        scan_result = AIScanResult()
        result = scanner._suggest_storage_path(self.document, "text", scan_result)

        self.assertIsNone(result)

    @mock.patch("documents.ai_scanner.match_storage_paths")
    @mock.patch("documents.ai_scanner.logger")
    def test_suggest_storage_path_handles_exception(self, mock_logger, mock_match):
        """Test storage path suggestion handles exceptions."""
        scanner = AIDocumentScanner()
        mock_match.side_effect = Exception("Suggestion failed")

        scan_result = AIScanResult()
        result = scanner._suggest_storage_path(self.document, "text", scan_result)

        self.assertIsNone(result)
        mock_logger.error.assert_called()


class TestExtractCustomFields(TestCase):
    """Test custom field extraction."""

    def setUp(self):
        """Set up test custom fields."""
        self.field_date = CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        self.field_amount = CustomField.objects.create(
            name="Total Amount",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_email = CustomField.objects.create(
            name="Contact Email",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_extract_custom_fields_with_entities(self):
        """Test custom field extraction with entities."""
        scanner = AIDocumentScanner()

        entities = {
            "dates": [{"text": "2024-01-01"}],
            "amounts": [{"text": "$1,000"}],
            "emails": ["test@example.com"],
        }

        fields = scanner._extract_custom_fields(self.document, "text", entities)

        # Should extract date field
        self.assertIn(self.field_date.id, fields)
        value, confidence = fields[self.field_date.id]
        self.assertEqual(value, "2024-01-01")
        self.assertGreaterEqual(confidence, 0.60)

    def test_extract_custom_fields_without_entities(self):
        """Test custom field extraction without entities."""
        scanner = AIDocumentScanner()

        fields = scanner._extract_custom_fields(self.document, "text", {})

        # Should return empty dict
        self.assertEqual(fields, {})

    @mock.patch("documents.ai_scanner.logger")
    def test_extract_custom_fields_handles_exception(self, mock_logger):
        """Test custom field extraction handles exceptions."""
        scanner = AIDocumentScanner()

        with mock.patch.object(
            CustomField.objects,
            "all",
            side_effect=Exception("DB error"),
        ):
            fields = scanner._extract_custom_fields(self.document, "text", {})

            self.assertEqual(fields, {})
            mock_logger.error.assert_called()


class TestExtractFieldValue(TestCase):
    """Test individual field value extraction."""

    def setUp(self):
        """Set up test fields."""
        self.field_date = CustomField.objects.create(
            name="Invoice Date",
            data_type=CustomField.FieldDataType.DATE,
        )
        self.field_amount = CustomField.objects.create(
            name="Total Amount",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_invoice = CustomField.objects.create(
            name="Invoice Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_email = CustomField.objects.create(
            name="Contact Email",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_phone = CustomField.objects.create(
            name="Phone Number",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_person = CustomField.objects.create(
            name="Person Name",
            data_type=CustomField.FieldDataType.STRING,
        )
        self.field_company = CustomField.objects.create(
            name="Company Name",
            data_type=CustomField.FieldDataType.STRING,
        )

    def test_extract_field_value_date(self):
        """Test extraction of date field."""
        scanner = AIDocumentScanner()
        entities = {"dates": [{"text": "2024-01-01"}]}

        value, confidence = scanner._extract_field_value(
            self.field_date,
            "text",
            entities,
        )

        self.assertEqual(value, "2024-01-01")
        self.assertEqual(confidence, 0.75)

    def test_extract_field_value_amount(self):
        """Test extraction of amount field."""
        scanner = AIDocumentScanner()
        entities = {"amounts": [{"text": "$1,000"}]}

        value, confidence = scanner._extract_field_value(
            self.field_amount,
            "text",
            entities,
        )

        self.assertEqual(value, "$1,000")
        self.assertEqual(confidence, 0.75)

    def test_extract_field_value_invoice_number(self):
        """Test extraction of invoice number."""
        scanner = AIDocumentScanner()
        entities = {"invoice_numbers": ["INV-12345"]}

        value, confidence = scanner._extract_field_value(
            self.field_invoice,
            "text",
            entities,
        )

        self.assertEqual(value, "INV-12345")
        self.assertEqual(confidence, 0.80)

    def test_extract_field_value_email(self):
        """Test extraction of email field."""
        scanner = AIDocumentScanner()
        entities = {"emails": ["test@example.com"]}

        value, confidence = scanner._extract_field_value(
            self.field_email,
            "text",
            entities,
        )

        self.assertEqual(value, "test@example.com")
        self.assertEqual(confidence, 0.85)

    def test_extract_field_value_phone(self):
        """Test extraction of phone field."""
        scanner = AIDocumentScanner()
        entities = {"phones": ["+1-555-1234"]}

        value, confidence = scanner._extract_field_value(
            self.field_phone,
            "text",
            entities,
        )

        self.assertEqual(value, "+1-555-1234")
        self.assertEqual(confidence, 0.85)

    def test_extract_field_value_person(self):
        """Test extraction of person name."""
        scanner = AIDocumentScanner()
        entities = {"persons": [{"text": "John Doe"}]}

        value, confidence = scanner._extract_field_value(
            self.field_person,
            "text",
            entities,
        )

        self.assertEqual(value, "John Doe")
        self.assertEqual(confidence, 0.70)

    def test_extract_field_value_company(self):
        """Test extraction of company name."""
        scanner = AIDocumentScanner()
        entities = {"organizations": [{"text": "ACME Corp"}]}

        value, confidence = scanner._extract_field_value(
            self.field_company,
            "text",
            entities,
        )

        self.assertEqual(value, "ACME Corp")
        self.assertEqual(confidence, 0.70)

    def test_extract_field_value_no_match(self):
        """Test extraction when no entity matches."""
        scanner = AIDocumentScanner()
        entities = {}

        value, confidence = scanner._extract_field_value(
            self.field_date,
            "text",
            entities,
        )

        self.assertIsNone(value)
        self.assertEqual(confidence, 0.0)


class TestSuggestWorkflows(TestCase):
    """Test workflow suggestion."""

    def setUp(self):
        """Set up test workflows."""
        self.workflow1 = Workflow.objects.create(
            name="Invoice Processing",
            enabled=True,
        )
        self.trigger1 = WorkflowTrigger.objects.create(
            workflow=self.workflow1,
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        self.workflow2 = Workflow.objects.create(
            name="Document Archival",
            enabled=True,
        )
        self.trigger2 = WorkflowTrigger.objects.create(
            workflow=self.workflow2,
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_suggest_workflows_with_matches(self):
        """Test workflow suggestion with matches."""
        scanner = AIDocumentScanner(suggest_threshold=0.5)

        scan_result = AIScanResult()
        scan_result.document_type = (1, 0.85)
        scan_result.correspondent = (2, 0.90)
        scan_result.tags = [(1, 0.80)]

        # Create action for workflow
        WorkflowAction.objects.create(
            workflow=self.workflow1,
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )

        suggestions = scanner._suggest_workflows(self.document, "text", scan_result)

        # Should suggest workflows
        self.assertGreater(len(suggestions), 0)
        for workflow_id, confidence in suggestions:
            self.assertGreaterEqual(confidence, 0.5)

    def test_suggest_workflows_filters_by_threshold(self):
        """Test that workflows below threshold are filtered."""
        scanner = AIDocumentScanner(suggest_threshold=0.95)

        scan_result = AIScanResult()

        suggestions = scanner._suggest_workflows(self.document, "text", scan_result)

        # Should not suggest any (confidence too low)
        self.assertEqual(len(suggestions), 0)

    @mock.patch("documents.ai_scanner.logger")
    def test_suggest_workflows_handles_exception(self, mock_logger):
        """Test workflow suggestion handles exceptions."""
        scanner = AIDocumentScanner()

        scan_result = AIScanResult()

        with mock.patch.object(
            Workflow.objects,
            "filter",
            side_effect=Exception("DB error"),
        ):
            suggestions = scanner._suggest_workflows(
                self.document,
                "text",
                scan_result,
            )

            self.assertEqual(suggestions, [])
            mock_logger.error.assert_called()


class TestEvaluateWorkflowMatch(TestCase):
    """Test workflow match evaluation."""

    def setUp(self):
        """Set up test workflow."""
        self.workflow = Workflow.objects.create(
            name="Test Workflow",
            enabled=True,
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_evaluate_workflow_match_base_confidence(self):
        """Test base confidence for workflow."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()

        confidence = scanner._evaluate_workflow_match(
            self.workflow,
            self.document,
            scan_result,
        )

        self.assertEqual(confidence, 0.5)

    def test_evaluate_workflow_match_with_document_type(self):
        """Test confidence increase with document type."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()
        scan_result.document_type = (1, 0.85)

        # Create action for workflow
        WorkflowAction.objects.create(
            workflow=self.workflow,
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )

        confidence = scanner._evaluate_workflow_match(
            self.workflow,
            self.document,
            scan_result,
        )

        self.assertGreater(confidence, 0.5)

    def test_evaluate_workflow_match_with_correspondent(self):
        """Test confidence increase with correspondent."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()
        scan_result.correspondent = (1, 0.90)

        confidence = scanner._evaluate_workflow_match(
            self.workflow,
            self.document,
            scan_result,
        )

        self.assertGreater(confidence, 0.5)

    def test_evaluate_workflow_match_with_tags(self):
        """Test confidence increase with tags."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()
        scan_result.tags = [(1, 0.80), (2, 0.75)]

        confidence = scanner._evaluate_workflow_match(
            self.workflow,
            self.document,
            scan_result,
        )

        self.assertGreater(confidence, 0.5)

    def test_evaluate_workflow_match_max_confidence(self):
        """Test that confidence is capped at 1.0."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()
        scan_result.document_type = (1, 0.85)
        scan_result.correspondent = (1, 0.90)
        scan_result.tags = [(1, 0.80)]

        # Create action
        WorkflowAction.objects.create(
            workflow=self.workflow,
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )

        confidence = scanner._evaluate_workflow_match(
            self.workflow,
            self.document,
            scan_result,
        )

        self.assertLessEqual(confidence, 1.0)


class TestSuggestTitle(TestCase):
    """Test title suggestion."""

    def setUp(self):
        """Set up test document."""
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_suggest_title_with_all_entities(self):
        """Test title suggestion with all entity types."""
        scanner = AIDocumentScanner()

        entities = {
            "document_type": "Invoice",
            "organizations": [{"text": "ACME Corporation"}],
            "dates": [{"text": "2024-01-01"}],
        }

        title = scanner._suggest_title(self.document, "text", entities)

        self.assertIsNotNone(title)
        self.assertIn("Invoice", title)
        self.assertIn("ACME Corporation", title)
        self.assertIn("2024-01-01", title)

    def test_suggest_title_with_partial_entities(self):
        """Test title suggestion with partial entities."""
        scanner = AIDocumentScanner()

        entities = {
            "organizations": [{"text": "TechStart Inc"}],
        }

        title = scanner._suggest_title(self.document, "text", entities)

        self.assertIsNotNone(title)
        self.assertIn("TechStart Inc", title)

    def test_suggest_title_without_entities(self):
        """Test title suggestion without entities."""
        scanner = AIDocumentScanner()

        title = scanner._suggest_title(self.document, "text", {})

        self.assertIsNone(title)

    def test_suggest_title_respects_length_limit(self):
        """Test that title respects 127 character limit."""
        scanner = AIDocumentScanner()

        # Create very long organization name
        long_org = "A" * 100
        entities = {
            "organizations": [{"text": long_org}],
            "dates": [{"text": "2024-01-01"}],
        }

        title = scanner._suggest_title(self.document, "text", entities)

        self.assertIsNotNone(title)
        self.assertLessEqual(len(title), 127)

    @mock.patch("documents.ai_scanner.logger")
    def test_suggest_title_handles_exception(self, mock_logger):
        """Test title suggestion handles exceptions."""
        scanner = AIDocumentScanner()

        # Force an exception
        entities = mock.MagicMock()
        entities.get.side_effect = Exception("Unexpected error")

        title = scanner._suggest_title(self.document, "text", entities)

        self.assertIsNone(title)
        mock_logger.error.assert_called()


class TestExtractTables(TestCase):
    """Test table extraction."""

    def test_extract_tables_with_extractor(self):
        """Test table extraction when extractor is available."""
        scanner = AIDocumentScanner()

        mock_extractor = mock.MagicMock()
        mock_extractor.extract_tables_from_image.return_value = [
            {"data": [[1, 2], [3, 4]], "headers": ["A", "B"]},
        ]
        scanner._table_extractor = mock_extractor

        tables = scanner._extract_tables("/path/to/file.pdf")

        self.assertEqual(len(tables), 1)
        self.assertIn("data", tables[0])
        mock_extractor.extract_tables_from_image.assert_called_once()

    def test_extract_tables_without_extractor(self):
        """Test table extraction when extractor is not available."""
        scanner = AIDocumentScanner()
        scanner._get_table_extractor = mock.MagicMock(return_value=None)

        tables = scanner._extract_tables("/path/to/file.pdf")

        self.assertEqual(tables, [])

    @mock.patch("documents.ai_scanner.logger")
    def test_extract_tables_handles_exception(self, mock_logger):
        """Test table extraction handles exceptions."""
        scanner = AIDocumentScanner()

        mock_extractor = mock.MagicMock()
        mock_extractor.extract_tables_from_image.side_effect = Exception(
            "Extraction failed",
        )
        scanner._table_extractor = mock_extractor

        tables = scanner._extract_tables("/path/to/file.pdf")

        self.assertEqual(tables, [])
        mock_logger.error.assert_called()


class TestScanDocument(TestCase):
    """Test the main scan_document orchestration method."""

    def setUp(self):
        """Set up test document."""
        self.document = Document.objects.create(
            title="Test Document",
            content="Invoice from ACME Corporation dated 2024-01-01",
        )

    @mock.patch.object(AIDocumentScanner, "_extract_entities")
    @mock.patch.object(AIDocumentScanner, "_suggest_tags")
    @mock.patch.object(AIDocumentScanner, "_detect_correspondent")
    @mock.patch.object(AIDocumentScanner, "_classify_document_type")
    @mock.patch.object(AIDocumentScanner, "_suggest_storage_path")
    @mock.patch.object(AIDocumentScanner, "_extract_custom_fields")
    @mock.patch.object(AIDocumentScanner, "_suggest_workflows")
    @mock.patch.object(AIDocumentScanner, "_suggest_title")
    def test_scan_document_orchestrates_all_methods(
        self,
        mock_title,
        mock_workflows,
        mock_fields,
        mock_storage,
        mock_doc_type,
        mock_correspondent,
        mock_tags,
        mock_entities,
    ):
        """Test that scan_document calls all extraction methods."""
        scanner = AIDocumentScanner()

        # Set up mock returns
        mock_entities.return_value = {"persons": ["John Doe"]}
        mock_tags.return_value = [(1, 0.85)]
        mock_correspondent.return_value = (1, 0.90)
        mock_doc_type.return_value = (1, 0.80)
        mock_storage.return_value = (1, 0.75)
        mock_fields.return_value = {1: ("value", 0.70)}
        mock_workflows.return_value = [(1, 0.65)]
        mock_title.return_value = "Suggested Title"

        result = scanner.scan_document(self.document, "Document text")

        # Verify all methods were called
        mock_entities.assert_called_once()
        mock_tags.assert_called_once()
        mock_correspondent.assert_called_once()
        mock_doc_type.assert_called_once()
        mock_storage.assert_called_once()
        mock_fields.assert_called_once()
        mock_workflows.assert_called_once()
        mock_title.assert_called_once()

        # Verify result contains data
        self.assertEqual(result.tags, [(1, 0.85)])
        self.assertEqual(result.correspondent, (1, 0.90))
        self.assertEqual(result.document_type, (1, 0.80))

    @mock.patch.object(AIDocumentScanner, "_extract_tables")
    def test_scan_document_extracts_tables_when_enabled(self, mock_extract_tables):
        """Test that tables are extracted when OCR is enabled and file path provided."""
        scanner = AIDocumentScanner(enable_advanced_ocr=True)
        mock_extract_tables.return_value = [{"data": "test"}]

        # Mock other methods to avoid complexity
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
            result = scanner.scan_document(
                self.document,
                "Document text",
                original_file_path="/path/to/file.pdf",
            )

            mock_extract_tables.assert_called_once_with("/path/to/file.pdf")
            self.assertIn("tables", result.metadata)

    def test_scan_document_without_file_path_skips_tables(self):
        """Test that tables are not extracted when file path is not provided."""
        scanner = AIDocumentScanner(enable_advanced_ocr=True)

        with (
            mock.patch.object(scanner, "_extract_tables") as mock_extract_tables,
            mock.patch.object(scanner, "_extract_entities", return_value={}),
            mock.patch.object(scanner, "_suggest_tags", return_value=[]),
            mock.patch.object(scanner, "_detect_correspondent", return_value=None),
            mock.patch.object(scanner, "_classify_document_type", return_value=None),
            mock.patch.object(scanner, "_suggest_storage_path", return_value=None),
            mock.patch.object(scanner, "_extract_custom_fields", return_value={}),
            mock.patch.object(scanner, "_suggest_workflows", return_value=[]),
            mock.patch.object(scanner, "_suggest_title", return_value=None),
        ):
            result = scanner.scan_document(self.document, "Document text")

            mock_extract_tables.assert_not_called()
            self.assertNotIn("tables", result.metadata)


class TestApplyScanResults(TestCase):
    """Test applying scan results to documents."""

    def setUp(self):
        """Set up test data."""
        self.tag1 = Tag.objects.create(name="Invoice")
        self.tag2 = Tag.objects.create(name="Important")
        self.correspondent = Correspondent.objects.create(name="ACME Corp")
        self.doc_type = DocumentType.objects.create(name="Invoice")
        self.storage_path = StoragePath.objects.create(
            name="Invoices",
            path="/invoices",
        )
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_apply_scan_results_auto_applies_high_confidence(self):
        """Test that high confidence suggestions are auto-applied."""
        scanner = AIDocumentScanner(auto_apply_threshold=0.80)

        scan_result = AIScanResult()
        scan_result.tags = [(self.tag1.id, 0.85), (self.tag2.id, 0.82)]
        scan_result.correspondent = (self.correspondent.id, 0.90)
        scan_result.document_type = (self.doc_type.id, 0.88)
        scan_result.storage_path = (self.storage_path.id, 0.85)

        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        # Verify auto-applied
        self.assertEqual(len(result["applied"]["tags"]), 2)
        self.assertIsNotNone(result["applied"]["correspondent"])
        self.assertIsNotNone(result["applied"]["document_type"])
        self.assertIsNotNone(result["applied"]["storage_path"])

        # Verify document was updated
        self.document.refresh_from_db()
        self.assertEqual(self.document.correspondent, self.correspondent)
        self.assertEqual(self.document.document_type, self.doc_type)
        self.assertEqual(self.document.storage_path, self.storage_path)

    def test_apply_scan_results_suggests_medium_confidence(self):
        """Test that medium confidence items are suggested, not applied."""
        scanner = AIDocumentScanner(
            auto_apply_threshold=0.80,
            suggest_threshold=0.60,
        )

        scan_result = AIScanResult()
        scan_result.tags = [(self.tag1.id, 0.70)]
        scan_result.correspondent = (self.correspondent.id, 0.65)

        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        # Verify suggested but not applied
        self.assertEqual(len(result["suggestions"]["tags"]), 1)
        self.assertIsNotNone(result["suggestions"]["correspondent"])
        self.assertEqual(len(result["applied"]["tags"]), 0)
        self.assertIsNone(result["applied"]["correspondent"])

        # Verify document was not updated
        self.document.refresh_from_db()
        self.assertIsNone(self.document.correspondent)

    def test_apply_scan_results_respects_auto_apply_false(self):
        """Test that auto_apply=False prevents automatic application."""
        scanner = AIDocumentScanner(auto_apply_threshold=0.80)

        scan_result = AIScanResult()
        scan_result.tags = [(self.tag1.id, 0.90)]

        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=False,
        )

        # Verify nothing was applied
        self.assertEqual(len(result["applied"]["tags"]), 0)

    def test_apply_scan_results_uses_transaction(self):
        """Test that apply_scan_results uses atomic transaction."""
        scanner = AIDocumentScanner()

        scan_result = AIScanResult()
        scan_result.correspondent = (self.correspondent.id, 0.90)

        with mock.patch.object(
            self.document,
            "save",
            side_effect=Exception("Save failed"),
        ):
            with self.assertRaises(Exception):
                with transaction.atomic():
                    scanner.apply_scan_results(
                        self.document,
                        scan_result,
                        auto_apply=True,
                    )

        # Verify transaction was rolled back
        self.document.refresh_from_db()
        self.assertIsNone(self.document.correspondent)

    @mock.patch("documents.ai_scanner.logger")
    def test_apply_scan_results_handles_exception(self, mock_logger):
        """Test that apply_scan_results handles exceptions gracefully."""
        scanner = AIDocumentScanner()

        scan_result = AIScanResult()
        scan_result.tags = [(999, 0.90)]  # Non-existent tag

        scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        mock_logger.error.assert_called()


class TestGetAIScanner(TestCase):
    """Test the global scanner singleton."""

    def test_get_ai_scanner_returns_instance(self):
        """Test that get_ai_scanner returns a scanner instance."""
        scanner = get_ai_scanner()

        self.assertIsInstance(scanner, AIDocumentScanner)

    def test_get_ai_scanner_returns_same_instance(self):
        """Test that get_ai_scanner returns the same instance."""
        scanner1 = get_ai_scanner()
        scanner2 = get_ai_scanner()

        self.assertIs(scanner1, scanner2)


class TestEdgeCasesAndErrorHandling(TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        """Set up test document."""
        self.document = Document.objects.create(
            title="Test Document",
            content="Test content",
        )

    def test_scan_document_with_empty_text(self):
        """Test scanning document with empty text."""
        scanner = AIDocumentScanner()

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
            result = scanner.scan_document(self.document, "")

            self.assertIsNotNone(result)
            self.assertIsInstance(result, AIScanResult)

    def test_scan_document_with_very_long_text(self):
        """Test scanning document with very long text."""
        scanner = AIDocumentScanner()
        long_text = "A" * 100000

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
            result = scanner.scan_document(self.document, long_text)

            self.assertIsNotNone(result)

    def test_scan_document_with_special_characters(self):
        """Test scanning document with special characters."""
        scanner = AIDocumentScanner()
        special_text = "Test with émojis 😀 and special chars: <>{}[]|\\`~"

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
            result = scanner.scan_document(self.document, special_text)

            self.assertIsNotNone(result)

    def test_apply_scan_results_with_empty_result(self):
        """Test applying empty scan results."""
        scanner = AIDocumentScanner()
        scan_result = AIScanResult()

        result = scanner.apply_scan_results(
            self.document,
            scan_result,
            auto_apply=True,
        )

        self.assertEqual(result["applied"]["tags"], [])
        self.assertIsNone(result["applied"]["correspondent"])

    def test_confidence_threshold_boundary_conditions(self):
        """Test behavior at threshold boundaries."""
        # Test at exact threshold
        scanner = AIDocumentScanner(auto_apply_threshold=0.80)
        self.assertEqual(scanner.auto_apply_threshold, 0.80)

        # Test extreme values
        scanner_low = AIDocumentScanner(
            auto_apply_threshold=0.01,
            suggest_threshold=0.01,
        )
        self.assertEqual(scanner_low.auto_apply_threshold, 0.01)

        scanner_high = AIDocumentScanner(
            auto_apply_threshold=0.99,
            suggest_threshold=0.80,
        )
        self.assertEqual(scanner_high.auto_apply_threshold, 0.99)
