from django.apps import AppConfig

from documents.parsers import ParseError

# dummy registration of the zip mime type
# This is necessary to ensure that the zip parser is recognized by the system.
# The actual handling of ZIP files is done in the consumer.py, not here.


def get_parser(*args, **kwargs):
    raise ParseError("ZIP archive needs to be handled directly.")


def zip_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "application/zip": ".zip",
        },
    }


class PaperlessZipConfig(AppConfig):
    name = "paperless_zip"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(zip_consumer_declaration)
        AppConfig.ready(self)
