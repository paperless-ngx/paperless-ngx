from django.apps import AppConfig

from paperless_video.signals import video_consumer_declaration


class PaperlessVideoConfig(AppConfig):
    name = "paperless_video"

    def ready(self):
        from documents.signals import document_consumer_declaration

        document_consumer_declaration.connect(video_consumer_declaration)

        AppConfig.ready(self)
