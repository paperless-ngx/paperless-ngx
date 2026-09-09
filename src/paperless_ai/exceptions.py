class LLMTimeoutError(Exception):
    pass


class LLMProviderError(Exception):
    """The LLM backend rejected the request."""
