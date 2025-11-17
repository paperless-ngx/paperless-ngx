"""
Machine Learning module for IntelliDocs-ngx.

Provides AI/ML capabilities including:
- BERT-based document classification
- Named Entity Recognition (NER)
- Semantic search
"""

from __future__ import annotations

__all__ = [
    "DocumentNER",
    "SemanticSearch",
    "TransformerDocumentClassifier",
]

# Lazy imports to avoid loading heavy ML libraries unless needed
def __getattr__(name):
    if name == "TransformerDocumentClassifier":
        from documents.ml.classifier import TransformerDocumentClassifier
        return TransformerDocumentClassifier
    elif name == "DocumentNER":
        from documents.ml.ner import DocumentNER
        return DocumentNER
    elif name == "SemanticSearch":
        from documents.ml.semantic_search import SemanticSearch
        return SemanticSearch
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
