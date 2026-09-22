class LLMTimeoutError(Exception):
    pass


class LLMProviderError(Exception):
    """The LLM backend rejected the request."""


class LLMBlockedError(Exception):
    """The outbound request policy refused the connection to the LLM backend."""
