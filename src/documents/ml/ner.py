"""
Named Entity Recognition (NER) for IntelliDocs-ngx.

Extracts structured information from documents:
- Names of people, organizations, locations
- Dates, amounts, invoice numbers
- Email addresses, phone numbers
- And more...

This enables automatic metadata extraction and better document understanding.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from transformers import pipeline

from documents.ml.model_cache import ModelCacheManager

if TYPE_CHECKING:
    pass

logger = logging.getLogger("paperless.ml.ner")


class DocumentNER:
    """
    Extract named entities from documents using BERT-based NER.
    
    Uses pre-trained NER models to automatically extract:
    - Person names (PER)
    - Organization names (ORG)
    - Locations (LOC)
    - Miscellaneous entities (MISC)
    
    Plus custom regex extraction for:
    - Dates
    - Amounts/Prices
    - Invoice numbers
    - Email addresses
    - Phone numbers
    """

    def __init__(
        self,
        model_name: str = "dslim/bert-base-NER",
        use_cache: bool = True,
    ):
        """
        Initialize NER extractor.
        
        Args:
            model_name: HuggingFace NER model
                       Default: dslim/bert-base-NER (good general purpose)
                       Alternatives:
                       - dslim/bert-base-NER-uncased
                       - dbmdz/bert-large-cased-finetuned-conll03-english
            use_cache: Whether to use model cache (default: True)
        """
        logger.info(f"Initializing NER with model: {model_name} (caching: {use_cache})")

        self.model_name = model_name
        self.use_cache = use_cache
        self.cache_manager = ModelCacheManager.get_instance() if use_cache else None
        
        # Cache key for this model
        cache_key = f"ner_{model_name}"
        
        if self.use_cache and self.cache_manager:
            # Load from cache or create new
            def loader():
                return pipeline(
                    "ner",
                    model=model_name,
                    aggregation_strategy="simple",
                )
            
            self.ner_pipeline = self.cache_manager.get_or_load_model(
                cache_key,
                loader,
            )
        else:
            # Load without caching
            self.ner_pipeline = pipeline(
                "ner",
                model=model_name,
                aggregation_strategy="simple",
            )

        # Compile regex patterns for efficiency
        self._compile_patterns()

        logger.info("DocumentNER initialized successfully")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for common entities."""
        # Date patterns
        self.date_patterns = [
            re.compile(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"),  # MM/DD/YYYY, DD-MM-YYYY
            re.compile(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}"),  # YYYY-MM-DD
            re.compile(
                r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}",
                re.IGNORECASE,
            ),  # Month DD, YYYY
        ]

        # Amount patterns
        self.amount_patterns = [
            re.compile(r"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"),  # $1,234.56
            re.compile(r"\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?USD"),  # 1,234.56 USD
            re.compile(r"€\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"),  # €1,234.56
            re.compile(r"£\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?"),  # £1,234.56
        ]

        # Invoice number patterns
        self.invoice_patterns = [
            re.compile(r"(?:Invoice|Inv\.?)\s*#?\s*(\w+)", re.IGNORECASE),
            re.compile(r"(?:Invoice|Inv\.?)\s*(?:Number|No\.?)\s*:?\s*(\w+)", re.IGNORECASE),
        ]

        # Email pattern
        self.email_pattern = re.compile(
            r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        )

        # Phone pattern (US/International)
        self.phone_pattern = re.compile(
            r"(?:\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
        )

    def extract_entities(self, text: str) -> dict[str, list[str]]:
        """
        Extract named entities from text.
        
        Args:
            text: Document text
            
        Returns:
            dict: Dictionary of entity types and their values
                  {
                      'persons': ['John Doe', ...],
                      'organizations': ['Acme Corp', ...],
                      'locations': ['New York', ...],
                      'misc': [...],
                  }
        """
        # Run NER model
        entities = self.ner_pipeline(text[:5000])  # Limit to first 5000 chars

        # Organize by type
        organized = {
            "persons": [],
            "organizations": [],
            "locations": [],
            "misc": [],
        }

        for entity in entities:
            entity_type = entity["entity_group"]
            entity_text = entity["word"].strip()

            if entity_type == "PER":
                organized["persons"].append(entity_text)
            elif entity_type == "ORG":
                organized["organizations"].append(entity_text)
            elif entity_type == "LOC":
                organized["locations"].append(entity_text)
            else:
                organized["misc"].append(entity_text)

        # Remove duplicates while preserving order
        for key in organized:
            seen = set()
            organized[key] = [
                x for x in organized[key] if not (x in seen or seen.add(x))
            ]

        logger.debug(f"Extracted entities: {organized}")
        return organized

    def extract_dates(self, text: str) -> list[str]:
        """
        Extract dates from text.
        
        Args:
            text: Document text
            
        Returns:
            list: List of date strings found
        """
        dates = []
        for pattern in self.date_patterns:
            dates.extend(pattern.findall(text))

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in dates if not (x in seen or seen.add(x))]

    def extract_amounts(self, text: str) -> list[str]:
        """
        Extract monetary amounts from text.
        
        Args:
            text: Document text
            
        Returns:
            list: List of amount strings found
        """
        amounts = []
        for pattern in self.amount_patterns:
            amounts.extend(pattern.findall(text))

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in amounts if not (x in seen or seen.add(x))]

    def extract_invoice_numbers(self, text: str) -> list[str]:
        """
        Extract invoice numbers from text.
        
        Args:
            text: Document text
            
        Returns:
            list: List of invoice numbers found
        """
        invoice_numbers = []
        for pattern in self.invoice_patterns:
            invoice_numbers.extend(pattern.findall(text))

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in invoice_numbers if not (x in seen or seen.add(x))]

    def extract_emails(self, text: str) -> list[str]:
        """
        Extract email addresses from text.
        
        Args:
            text: Document text
            
        Returns:
            list: List of email addresses found
        """
        emails = self.email_pattern.findall(text)

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in emails if not (x in seen or seen.add(x))]

    def extract_phones(self, text: str) -> list[str]:
        """
        Extract phone numbers from text.
        
        Args:
            text: Document text
            
        Returns:
            list: List of phone numbers found
        """
        phones = self.phone_pattern.findall(text)

        # Remove duplicates while preserving order
        seen = set()
        return [x for x in phones if not (x in seen or seen.add(x))]

    def extract_all(self, text: str) -> dict[str, list[str]]:
        """
        Extract all types of entities from text.
        
        This is the main method that combines NER and regex extraction.
        
        Args:
            text: Document text
            
        Returns:
            dict: Complete extraction results
                  {
                      'persons': [...],
                      'organizations': [...],
                      'locations': [...],
                      'misc': [...],
                      'dates': [...],
                      'amounts': [...],
                      'invoice_numbers': [...],
                      'emails': [...],
                      'phones': [...],
                  }
        """
        logger.info("Extracting all entities from document")

        # Get NER entities
        result = self.extract_entities(text)

        # Add regex-based extractions
        result["dates"] = self.extract_dates(text)
        result["amounts"] = self.extract_amounts(text)
        result["invoice_numbers"] = self.extract_invoice_numbers(text)
        result["emails"] = self.extract_emails(text)
        result["phones"] = self.extract_phones(text)

        logger.info(
            f"Extracted: {sum(len(v) for v in result.values())} total entities",
        )

        return result

    def extract_invoice_data(self, text: str) -> dict[str, any]:
        """
        Extract invoice-specific data from text.
        
        Specialized method for invoices that extracts common fields.
        
        Args:
            text: Invoice text
            
        Returns:
            dict: Invoice data
                  {
                      'invoice_numbers': [...],
                      'dates': [...],
                      'amounts': [...],
                      'vendors': [...],  # from organizations
                      'emails': [...],
                      'phones': [...],
                  }
        """
        logger.info("Extracting invoice-specific data")

        # Extract all entities
        all_entities = self.extract_all(text)

        # Create invoice-specific structure
        invoice_data = {
            "invoice_numbers": all_entities["invoice_numbers"],
            "dates": all_entities["dates"],
            "amounts": all_entities["amounts"],
            "vendors": all_entities["organizations"],  # Organizations = Vendors
            "emails": all_entities["emails"],
            "phones": all_entities["phones"],
        }

        # Try to identify total amount (usually the largest)
        if invoice_data["amounts"]:
            # Parse amounts to find largest
            try:
                parsed_amounts = []
                for amt in invoice_data["amounts"]:
                    # Remove currency symbols and commas
                    cleaned = re.sub(r"[$€£,]", "", amt)
                    cleaned = re.sub(r"\s", "", cleaned)
                    if cleaned:
                        parsed_amounts.append(float(cleaned))

                if parsed_amounts:
                    max_amount = max(parsed_amounts)
                    invoice_data["total_amount"] = max_amount
            except (ValueError, TypeError):
                pass

        return invoice_data

    def suggest_correspondent(self, text: str) -> str | None:
        """
        Suggest a correspondent based on extracted entities.
        
        Args:
            text: Document text
            
        Returns:
            str or None: Suggested correspondent name
        """
        entities = self.extract_entities(text)

        # Priority: organizations > persons
        if entities["organizations"]:
            return entities["organizations"][0]  # Return first org

        if entities["persons"]:
            return entities["persons"][0]  # Return first person

        return None

    def suggest_tags(self, text: str) -> list[str]:
        """
        Suggest tags based on extracted entities.
        
        Args:
            text: Document text
            
        Returns:
            list: Suggested tag names
        """
        tags = []

        # Check for invoice indicators
        if re.search(r"\binvoice\b", text, re.IGNORECASE):
            tags.append("invoice")

        # Check for receipt indicators
        if re.search(r"\breceipt\b", text, re.IGNORECASE):
            tags.append("receipt")

        # Check for contract indicators
        if re.search(r"\bcontract\b|\bagreement\b", text, re.IGNORECASE):
            tags.append("contract")

        # Check for letter indicators
        if re.search(r"\bdear\b|\bsincerely\b", text, re.IGNORECASE):
            tags.append("letter")

        return tags
