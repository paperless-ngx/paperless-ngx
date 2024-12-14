from django.apps import AppConfig

from paperless_xml.signals import xml_consumer_declaration


class PaperlessXMLConfig(AppConfig):
    name = "paperless_xml"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(xml_consumer_declaration)

        AppConfig.ready(self)
