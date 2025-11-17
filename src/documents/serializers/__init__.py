"""Serializers package for documents app."""

from .ai_suggestions import AISuggestionFeedbackSerializer
from .ai_suggestions import AISuggestionsSerializer
from .ai_suggestions import AISuggestionStatsSerializer
from .ai_suggestions import ApplySuggestionSerializer
from .ai_suggestions import RejectSuggestionSerializer

__all__ = [
    "AISuggestionFeedbackSerializer",
    "AISuggestionStatsSerializer",
    "AISuggestionsSerializer",
    "ApplySuggestionSerializer",
    "RejectSuggestionSerializer",
]
