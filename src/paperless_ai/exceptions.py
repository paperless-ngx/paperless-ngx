class LLMTimeoutError(Exception):
    pass


class SuggestionProviderError(Exception):
    """Provider failed; messages exclude response bodies and credentials."""


class SuggestionProviderUnavailable(SuggestionProviderError):
    """A transport failure or retryable HTTP response."""


class StaleSuggestions(SuggestionProviderError):
    """Document state changed while suggestions were being generated."""
