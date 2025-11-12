"""
AI Scanner Module for IntelliDocs-ngx

This module provides comprehensive AI-powered document scanning and metadata management.
It automatically analyzes documents on upload/consumption and manages:
- Tags
- Correspondents
- Document Types
- Storage Paths
- Custom Fields
- Workflow Assignments

According to agents.md requirements:
- AI scans every consumed/uploaded document
- AI suggests metadata for all manageable aspects
- AI cannot delete files without explicit user authorization
- AI must inform users comprehensively before any destructive action
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple

from django.conf import settings
from django.db import transaction

if TYPE_CHECKING:
    from documents.models import (
        Document,
        Tag,
        Correspondent,
        DocumentType,
        StoragePath,
        CustomField,
        Workflow,
    )

logger = logging.getLogger("paperless.ai_scanner")


class AIScanResult:
    """
    Container for AI scan results with confidence scores and suggestions.
    """

    def __init__(self):
        self.tags: List[Tuple[int, float]] = []  # [(tag_id, confidence), ...]
        self.correspondent: Optional[Tuple[int, float]] = None  # (correspondent_id, confidence)
        self.document_type: Optional[Tuple[int, float]] = None  # (document_type_id, confidence)
        self.storage_path: Optional[Tuple[int, float]] = None  # (storage_path_id, confidence)
        self.custom_fields: Dict[int, Tuple[Any, float]] = {}  # {field_id: (value, confidence), ...}
        self.workflows: List[Tuple[int, float]] = []  # [(workflow_id, confidence), ...]
        self.extracted_entities: Dict[str, Any] = {}  # NER results
        self.title_suggestion: Optional[str] = None
        self.metadata: Dict[str, Any] = {}  # Additional metadata

    def to_dict(self) -> Dict[str, Any]:
        """Convert scan results to dictionary for logging/serialization."""
        return {
            "tags": self.tags,
            "correspondent": self.correspondent,
            "document_type": self.document_type,
            "storage_path": self.storage_path,
            "custom_fields": self.custom_fields,
            "workflows": self.workflows,
            "extracted_entities": self.extracted_entities,
            "title_suggestion": self.title_suggestion,
            "metadata": self.metadata,
        }


class AIDocumentScanner:
    """
    Comprehensive AI scanner for automatic document metadata management.
    
    This scanner integrates all ML/AI capabilities to provide automatic:
    - Tag assignment based on content analysis
    - Correspondent detection from document text
    - Document type classification
    - Storage path suggestion based on content/type
    - Custom field extraction using NER
    - Workflow assignment based on document characteristics
    
    Features:
    - High confidence threshold (>80%) for automatic application
    - Medium confidence (60-80%) for suggestions requiring user review
    - Low confidence (<60%) logged but not suggested
    - All decisions are logged for auditing
    - No destructive operations without user confirmation
    """

    def __init__(
        self,
        auto_apply_threshold: float = 0.80,
        suggest_threshold: float = 0.60,
        enable_ml_features: bool = None,
        enable_advanced_ocr: bool = None,
    ):
        """
        Initialize AI scanner.
        
        Args:
            auto_apply_threshold: Confidence threshold for automatic application (default: 0.80)
            suggest_threshold: Confidence threshold for suggestions (default: 0.60)
            enable_ml_features: Override for ML features (uses settings if None)
            enable_advanced_ocr: Override for advanced OCR (uses settings if None)
        """
        self.auto_apply_threshold = auto_apply_threshold
        self.suggest_threshold = suggest_threshold
        
        # Check settings for ML/OCR enablement
        self.ml_enabled = (
            enable_ml_features
            if enable_ml_features is not None
            else getattr(settings, "PAPERLESS_ENABLE_ML_FEATURES", True)
        )
        self.advanced_ocr_enabled = (
            enable_advanced_ocr
            if enable_advanced_ocr is not None
            else getattr(settings, "PAPERLESS_ENABLE_ADVANCED_OCR", True)
        )
        
        # Lazy loading of ML components
        self._classifier = None
        self._ner_extractor = None
        self._semantic_search = None
        self._table_extractor = None
        
        logger.info(
            f"AIDocumentScanner initialized - ML: {self.ml_enabled}, "
            f"Advanced OCR: {self.advanced_ocr_enabled}"
        )

    def _get_classifier(self):
        """Lazy load the ML classifier."""
        if self._classifier is None and self.ml_enabled:
            try:
                from documents.ml.classifier import TransformerDocumentClassifier
                self._classifier = TransformerDocumentClassifier()
                logger.info("ML classifier loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load ML classifier: {e}")
                self.ml_enabled = False
        return self._classifier

    def _get_ner_extractor(self):
        """Lazy load the NER extractor."""
        if self._ner_extractor is None and self.ml_enabled:
            try:
                from documents.ml.ner import DocumentNER
                self._ner_extractor = DocumentNER()
                logger.info("NER extractor loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load NER extractor: {e}")
        return self._ner_extractor

    def _get_semantic_search(self):
        """Lazy load semantic search."""
        if self._semantic_search is None and self.ml_enabled:
            try:
                from documents.ml.semantic_search import SemanticSearch
                self._semantic_search = SemanticSearch()
                logger.info("Semantic search loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load semantic search: {e}")
        return self._semantic_search

    def _get_table_extractor(self):
        """Lazy load table extractor."""
        if self._table_extractor is None and self.advanced_ocr_enabled:
            try:
                from documents.ocr.table_extractor import TableExtractor
                self._table_extractor = TableExtractor()
                logger.info("Table extractor loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load table extractor: {e}")
        return self._table_extractor

    def scan_document(
        self,
        document: Document,
        document_text: str,
        original_file_path: str = None,
    ) -> AIScanResult:
        """
        Perform comprehensive AI scan of a document.
        
        This is the main entry point for document scanning. It orchestrates
        all AI/ML components to analyze the document and generate suggestions.
        
        Args:
            document: The Document model instance
            document_text: The extracted text content
            original_file_path: Path to original file (for OCR/image analysis)
            
        Returns:
            AIScanResult containing all suggestions and extracted data
        """
        logger.info(f"Starting AI scan for document: {document.title} (ID: {document.pk})")
        
        result = AIScanResult()
        
        # Extract entities using NER
        result.extracted_entities = self._extract_entities(document_text)
        
        # Analyze and suggest tags
        result.tags = self._suggest_tags(document, document_text, result.extracted_entities)
        
        # Detect correspondent
        result.correspondent = self._detect_correspondent(
            document, document_text, result.extracted_entities
        )
        
        # Classify document type
        result.document_type = self._classify_document_type(
            document, document_text, result.extracted_entities
        )
        
        # Suggest storage path
        result.storage_path = self._suggest_storage_path(
            document, document_text, result
        )
        
        # Extract custom fields
        result.custom_fields = self._extract_custom_fields(
            document, document_text, result.extracted_entities
        )
        
        # Suggest workflows
        result.workflows = self._suggest_workflows(document, document_text, result)
        
        # Generate improved title suggestion
        result.title_suggestion = self._suggest_title(
            document, document_text, result.extracted_entities
        )
        
        # Extract tables if advanced OCR enabled
        if self.advanced_ocr_enabled and original_file_path:
            result.metadata["tables"] = self._extract_tables(original_file_path)
        
        logger.info(f"AI scan completed for document {document.pk}")
        logger.debug(f"Scan results: {result.to_dict()}")
        
        return result

    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract named entities from document text using NER.
        
        Returns:
            Dictionary with extracted entities (persons, orgs, dates, amounts, etc.)
        """
        ner = self._get_ner_extractor()
        if not ner:
            return {}
        
        try:
            # Use extract_all to get comprehensive entity extraction
            entities = ner.extract_all(text)
            
            # Convert string lists to dict format for consistency
            for key in ["persons", "organizations", "locations", "misc"]:
                if key in entities and isinstance(entities[key], list):
                    entities[key] = [{"text": e} if isinstance(e, str) else e for e in entities[key]]
            
            for key in ["dates", "amounts"]:
                if key in entities and isinstance(entities[key], list):
                    entities[key] = [{"text": e} if isinstance(e, str) else e for e in entities[key]]
            
            logger.debug(f"Extracted entities from NER")
            return entities
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}", exc_info=True)
            return {}

    def _suggest_tags(
        self,
        document: Document,
        text: str,
        entities: Dict[str, Any],
    ) -> List[Tuple[int, float]]:
        """
        Suggest relevant tags based on document content and entities.
        
        Uses a combination of:
        - Keyword matching with existing tag patterns
        - ML classification if available
        - Entity-based suggestions (e.g., organization -> company tag)
        
        Returns:
            List of (tag_id, confidence) tuples
        """
        from documents.models import Tag
        from documents.matching import match_tags
        
        suggestions = []
        
        try:
            # Use existing matching logic
            matched_tags = match_tags(document, self._get_classifier())
            
            # Add confidence scores based on matching strength
            for tag in matched_tags:
                confidence = 0.85  # High confidence for matched tags
                suggestions.append((tag.id, confidence))
            
            # Additional entity-based suggestions
            if entities:
                # Suggest tags based on detected entities
                all_tags = Tag.objects.all()
                
                # Check for organization entities -> company/business tags
                if entities.get("organizations"):
                    for tag in all_tags.filter(name__icontains="company"):
                        suggestions.append((tag.id, 0.70))
                
                # Check for date entities -> tax/financial tags if year-end
                if entities.get("dates"):
                    for tag in all_tags.filter(name__icontains="tax"):
                        suggestions.append((tag.id, 0.65))
            
            # Remove duplicates, keep highest confidence
            seen = {}
            for tag_id, conf in suggestions:
                if tag_id not in seen or conf > seen[tag_id]:
                    seen[tag_id] = conf
            
            suggestions = [(tid, conf) for tid, conf in seen.items()]
            suggestions.sort(key=lambda x: x[1], reverse=True)
            
            logger.debug(f"Suggested {len(suggestions)} tags")
            
        except Exception as e:
            logger.error(f"Tag suggestion failed: {e}", exc_info=True)
        
        return suggestions

    def _detect_correspondent(
        self,
        document: Document,
        text: str,
        entities: Dict[str, Any],
    ) -> Optional[Tuple[int, float]]:
        """
        Detect correspondent based on document content and entities.
        
        Uses:
        - Organization entities from NER
        - Email domains
        - Existing correspondent matching patterns
        
        Returns:
            (correspondent_id, confidence) or None
        """
        from documents.models import Correspondent
        from documents.matching import match_correspondents
        
        try:
            # Use existing matching logic
            matched_correspondents = match_correspondents(document, self._get_classifier())
            
            if matched_correspondents:
                correspondent = matched_correspondents[0]
                confidence = 0.85
                logger.debug(
                    f"Detected correspondent: {correspondent.name} "
                    f"(confidence: {confidence})"
                )
                return (correspondent.id, confidence)
            
            # Try to match based on NER organizations
            if entities.get("organizations"):
                org_name = entities["organizations"][0]["text"]
                # Try to find existing correspondent with similar name
                correspondents = Correspondent.objects.filter(
                    name__icontains=org_name[:20]  # First 20 chars
                )
                if correspondents.exists():
                    correspondent = correspondents.first()
                    confidence = 0.70
                    logger.debug(
                        f"Detected correspondent from NER: {correspondent.name} "
                        f"(confidence: {confidence})"
                    )
                    return (correspondent.id, confidence)
        
        except Exception as e:
            logger.error(f"Correspondent detection failed: {e}", exc_info=True)
        
        return None

    def _classify_document_type(
        self,
        document: Document,
        text: str,
        entities: Dict[str, Any],
    ) -> Optional[Tuple[int, float]]:
        """
        Classify document type using ML and content analysis.
        
        Returns:
            (document_type_id, confidence) or None
        """
        from documents.models import DocumentType
        from documents.matching import match_document_types
        
        try:
            # Use existing matching logic
            matched_types = match_document_types(document, self._get_classifier())
            
            if matched_types:
                doc_type = matched_types[0]
                confidence = 0.85
                logger.debug(
                    f"Classified document type: {doc_type.name} "
                    f"(confidence: {confidence})"
                )
                return (doc_type.id, confidence)
            
            # ML-based classification if available
            classifier = self._get_classifier()
            if classifier and hasattr(classifier, "predict"):
                # This would need a trained model with document type labels
                # For now, fall back to pattern matching
                pass
        
        except Exception as e:
            logger.error(f"Document type classification failed: {e}", exc_info=True)
        
        return None

    def _suggest_storage_path(
        self,
        document: Document,
        text: str,
        scan_result: AIScanResult,
    ) -> Optional[Tuple[int, float]]:
        """
        Suggest appropriate storage path based on document characteristics.
        
        Returns:
            (storage_path_id, confidence) or None
        """
        from documents.models import StoragePath
        from documents.matching import match_storage_paths
        
        try:
            # Use existing matching logic
            matched_paths = match_storage_paths(document, self._get_classifier())
            
            if matched_paths:
                storage_path = matched_paths[0]
                confidence = 0.80
                logger.debug(
                    f"Suggested storage path: {storage_path.name} "
                    f"(confidence: {confidence})"
                )
                return (storage_path.id, confidence)
        
        except Exception as e:
            logger.error(f"Storage path suggestion failed: {e}", exc_info=True)
        
        return None

    def _extract_custom_fields(
        self,
        document: Document,
        text: str,
        entities: Dict[str, Any],
    ) -> Dict[int, Tuple[Any, float]]:
        """
        Extract values for custom fields using NER and pattern matching.
        
        Returns:
            Dictionary mapping field_id to (value, confidence)
        """
        from documents.models import CustomField
        
        extracted_fields = {}
        
        try:
            custom_fields = CustomField.objects.all()
            
            for field in custom_fields:
                # Try to extract field value based on field name and type
                value, confidence = self._extract_field_value(
                    field, text, entities
                )
                
                if value is not None and confidence >= self.suggest_threshold:
                    extracted_fields[field.id] = (value, confidence)
                    logger.debug(
                        f"Extracted custom field '{field.name}': {value} "
                        f"(confidence: {confidence})"
                    )
        
        except Exception as e:
            logger.error(f"Custom field extraction failed: {e}", exc_info=True)
        
        return extracted_fields

    def _extract_field_value(
        self,
        field: CustomField,
        text: str,
        entities: Dict[str, Any],
    ) -> Tuple[Any, float]:
        """
        Extract a single custom field value.
        
        Returns:
            (value, confidence) tuple
        """
        field_name_lower = field.name.lower()
        
        # Date fields
        if "date" in field_name_lower:
            dates = entities.get("dates", [])
            if dates:
                return (dates[0]["text"], 0.75)
        
        # Amount/price fields
        if any(keyword in field_name_lower for keyword in ["amount", "price", "cost", "total"]):
            amounts = entities.get("amounts", [])
            if amounts:
                return (amounts[0]["text"], 0.75)
        
        # Invoice number fields
        if "invoice" in field_name_lower:
            invoice_numbers = entities.get("invoice_numbers", [])
            if invoice_numbers:
                return (invoice_numbers[0], 0.80)
        
        # Email fields
        if "email" in field_name_lower:
            emails = entities.get("emails", [])
            if emails:
                return (emails[0], 0.85)
        
        # Phone fields
        if "phone" in field_name_lower:
            phones = entities.get("phones", [])
            if phones:
                return (phones[0], 0.85)
        
        # Person name fields
        if "name" in field_name_lower or "person" in field_name_lower:
            persons = entities.get("persons", [])
            if persons:
                return (persons[0]["text"], 0.70)
        
        # Organization fields
        if "company" in field_name_lower or "organization" in field_name_lower:
            orgs = entities.get("organizations", [])
            if orgs:
                return (orgs[0]["text"], 0.70)
        
        return (None, 0.0)

    def _suggest_workflows(
        self,
        document: Document,
        text: str,
        scan_result: AIScanResult,
    ) -> List[Tuple[int, float]]:
        """
        Suggest relevant workflows based on document characteristics.
        
        Returns:
            List of (workflow_id, confidence) tuples
        """
        from documents.models import Workflow, WorkflowTrigger
        
        suggestions = []
        
        try:
            # Get all workflows with consumption triggers
            workflows = Workflow.objects.filter(
                enabled=True,
                triggers__type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
            ).distinct()
            
            for workflow in workflows:
                # Evaluate workflow conditions against scan results
                confidence = self._evaluate_workflow_match(
                    workflow, document, scan_result
                )
                
                if confidence >= self.suggest_threshold:
                    suggestions.append((workflow.id, confidence))
                    logger.debug(
                        f"Suggested workflow: {workflow.name} "
                        f"(confidence: {confidence})"
                    )
        
        except Exception as e:
            logger.error(f"Workflow suggestion failed: {e}", exc_info=True)
        
        return suggestions

    def _evaluate_workflow_match(
        self,
        workflow: Workflow,
        document: Document,
        scan_result: AIScanResult,
    ) -> float:
        """
        Evaluate how well a workflow matches the document.
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        # This is a simplified evaluation
        # In practice, you'd check workflow triggers and conditions
        
        confidence = 0.5  # Base confidence
        
        # Increase confidence if document type matches workflow expectations
        if scan_result.document_type and workflow.actions.exists():
            confidence += 0.2
        
        # Increase confidence if correspondent matches
        if scan_result.correspondent:
            confidence += 0.15
        
        # Increase confidence if tags match
        if scan_result.tags:
            confidence += 0.15
        
        return min(confidence, 1.0)

    def _suggest_title(
        self,
        document: Document,
        text: str,
        entities: Dict[str, Any],
    ) -> Optional[str]:
        """
        Generate an improved title suggestion based on document content.
        
        Returns:
            Suggested title or None
        """
        try:
            # Extract key information for title
            title_parts = []
            
            # Add document type if detected
            if entities.get("document_type"):
                title_parts.append(entities["document_type"])
            
            # Add primary organization
            orgs = entities.get("organizations", [])
            if orgs:
                title_parts.append(orgs[0]["text"][:30])  # Limit length
            
            # Add date if available
            dates = entities.get("dates", [])
            if dates:
                title_parts.append(dates[0]["text"])
            
            if title_parts:
                suggested_title = " - ".join(title_parts)
                logger.debug(f"Generated title suggestion: {suggested_title}")
                return suggested_title[:127]  # Respect title length limit
        
        except Exception as e:
            logger.error(f"Title suggestion failed: {e}", exc_info=True)
        
        return None

    def _extract_tables(self, file_path: str) -> List[Dict[str, Any]]:
        """
        Extract tables from document using advanced OCR.
        
        Returns:
            List of extracted tables with data and metadata
        """
        extractor = self._get_table_extractor()
        if not extractor:
            return []
        
        try:
            tables = extractor.extract_tables_from_image(file_path)
            logger.debug(f"Extracted {len(tables)} tables from document")
            return tables
        except Exception as e:
            logger.error(f"Table extraction failed: {e}", exc_info=True)
            return []

    def apply_scan_results(
        self,
        document: Document,
        scan_result: AIScanResult,
        auto_apply: bool = True,
        user_confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Apply AI scan results to document.
        
        Args:
            document: Document to update
            scan_result: AI scan results
            auto_apply: Whether to auto-apply high confidence suggestions
            user_confirmed: Whether user has confirmed low-confidence changes
            
        Returns:
            Dictionary with applied changes and pending suggestions
        """
        from documents.models import Tag, Correspondent, DocumentType, StoragePath
        
        applied = {
            "tags": [],
            "correspondent": None,
            "document_type": None,
            "storage_path": None,
            "custom_fields": {},
        }
        
        suggestions = {
            "tags": [],
            "correspondent": None,
            "document_type": None,
            "storage_path": None,
            "custom_fields": {},
        }
        
        applied_fields = []  # Track which fields were auto-applied for webhook
        
        try:
            with transaction.atomic():
                # Apply tags
                for tag_id, confidence in scan_result.tags:
                    if confidence >= self.auto_apply_threshold and auto_apply:
                        tag = Tag.objects.get(pk=tag_id)
                        document.add_nested_tags([tag])
                        applied["tags"].append({"id": tag_id, "name": tag.name})
                        applied_fields.append("tags")
                        logger.info(f"Auto-applied tag: {tag.name}")
                    elif confidence >= self.suggest_threshold:
                        tag = Tag.objects.get(pk=tag_id)
                        suggestions["tags"].append({
                            "id": tag_id,
                            "name": tag.name,
                            "confidence": confidence,
                        })
                
                # Apply correspondent
                if scan_result.correspondent:
                    corr_id, confidence = scan_result.correspondent
                    if confidence >= self.auto_apply_threshold and auto_apply:
                        correspondent = Correspondent.objects.get(pk=corr_id)
                        document.correspondent = correspondent
                        applied["correspondent"] = {
                            "id": corr_id,
                            "name": correspondent.name,
                        }
                        applied_fields.append("correspondent")
                        logger.info(f"Auto-applied correspondent: {correspondent.name}")
                    elif confidence >= self.suggest_threshold:
                        correspondent = Correspondent.objects.get(pk=corr_id)
                        suggestions["correspondent"] = {
                            "id": corr_id,
                            "name": correspondent.name,
                            "confidence": confidence,
                        }
                
                # Apply document type
                if scan_result.document_type:
                    type_id, confidence = scan_result.document_type
                    if confidence >= self.auto_apply_threshold and auto_apply:
                        doc_type = DocumentType.objects.get(pk=type_id)
                        document.document_type = doc_type
                        applied["document_type"] = {
                            "id": type_id,
                            "name": doc_type.name,
                        }
                        applied_fields.append("document_type")
                        logger.info(f"Auto-applied document type: {doc_type.name}")
                    elif confidence >= self.suggest_threshold:
                        doc_type = DocumentType.objects.get(pk=type_id)
                        suggestions["document_type"] = {
                            "id": type_id,
                            "name": doc_type.name,
                            "confidence": confidence,
                        }
                
                # Apply storage path
                if scan_result.storage_path:
                    path_id, confidence = scan_result.storage_path
                    if confidence >= self.auto_apply_threshold and auto_apply:
                        storage_path = StoragePath.objects.get(pk=path_id)
                        document.storage_path = storage_path
                        applied["storage_path"] = {
                            "id": path_id,
                            "name": storage_path.name,
                        }
                        applied_fields.append("storage_path")
                        logger.info(f"Auto-applied storage path: {storage_path.name}")
                    elif confidence >= self.suggest_threshold:
                        storage_path = StoragePath.objects.get(pk=path_id)
                        suggestions["storage_path"] = {
                            "id": path_id,
                            "name": storage_path.name,
                            "confidence": confidence,
                        }
                
                # Save document with changes
                document.save()
                
                # Send webhooks for auto-applied suggestions
                if applied_fields:
                    try:
                        from documents.webhooks import send_suggestion_applied_webhook
                        send_suggestion_applied_webhook(
                            document,
                            scan_result.to_dict(),
                            applied_fields,
                        )
                    except Exception as webhook_error:
                        logger.warning(
                            f"Failed to send suggestion applied webhook: {webhook_error}",
                            exc_info=True,
                        )
                
                # Send webhook for scan completion
                try:
                    from documents.webhooks import send_scan_completed_webhook
                    auto_applied_count = len(applied_fields)
                    suggestions_count = sum([
                        len(suggestions.get("tags", [])),
                        1 if suggestions.get("correspondent") else 0,
                        1 if suggestions.get("document_type") else 0,
                        1 if suggestions.get("storage_path") else 0,
                    ])
                    send_scan_completed_webhook(
                        document,
                        scan_result.to_dict(),
                        auto_applied_count,
                        suggestions_count,
                    )
                except Exception as webhook_error:
                    logger.warning(
                        f"Failed to send scan completed webhook: {webhook_error}",
                        exc_info=True,
                    )
        
        except Exception as e:
            logger.error(f"Failed to apply scan results: {e}", exc_info=True)
        
        return {
            "applied": applied,
            "suggestions": suggestions,
        }


# Global scanner instance (lazy initialized)
_scanner_instance = None


def get_ai_scanner() -> AIDocumentScanner:
    """
    Get or create the global AI scanner instance.
    
    Returns:
        AIDocumentScanner instance
    """
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = AIDocumentScanner()
    return _scanner_instance
