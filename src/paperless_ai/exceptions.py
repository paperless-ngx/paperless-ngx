class LLMTimeoutError(Exception):
    pass


class LLMProviderError(Exception):
    """The LLM backend rejected the request."""


class LLMGenerationFailedError(Exception):
    """A concurrent generation of the same suggestions failed."""
