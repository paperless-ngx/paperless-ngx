from django.apps import AppConfig


class DocumentsConfig(AppConfig):

    name = "documents"

    def ready(self):

        from .signals import document_consumption_started
        from .signals import document_consumption_finished
        from .signals.handlers import (
            set_correspondent, set_tags, run_pre_consume_script,
            run_post_consume_script)

        document_consumption_started.connect(run_pre_consume_script)

        document_consumption_finished.connect(set_tags)
        document_consumption_finished.connect(set_correspondent)
        document_consumption_finished.connect(run_post_consume_script)

        AppConfig.ready(self)
