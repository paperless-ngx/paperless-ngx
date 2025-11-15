"""Serializers package for documents app."""

from .ai_suggestions import (
    AISuggestionFeedbackSerializer,
    AISuggestionsSerializer,
    AISuggestionStatsSerializer,
    ApplySuggestionSerializer,
    RejectSuggestionSerializer,
)

__all__ = [
    'AISuggestionFeedbackSerializer',
    'AISuggestionsSerializer',
    'AISuggestionStatsSerializer',
    'ApplySuggestionSerializer',
    'RejectSuggestionSerializer',
]
