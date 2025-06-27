class SkipImportException(Exception):
    """
    Raised by a parser to indicate that the file should be skipped (not imported as a document),
    but should still be cleaned up by the consumer. This is not an error, just a signal to skip.
    """
