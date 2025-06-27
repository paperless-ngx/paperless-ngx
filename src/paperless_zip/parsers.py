from documents.parsers import DocumentParser
from documents.parsers import ParseError


# dummy registration of the zip mime type
# This is necessary to ensure that the zip parser is recognized by the system.
# The actual handling of ZIP files is done in the consumer, not here.
class ZipDocumentParser(DocumentParser):
    """
    Parser for ZIP files. Dummy implementation to announce zip support in paperless
    """

    def parse(self, document_path, mime_type, file_name=None):
        raise ParseError("ZIP archive needs to be handled directly.")
