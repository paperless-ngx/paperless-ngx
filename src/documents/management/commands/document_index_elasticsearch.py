from django.core.management import BaseCommand
from elasticsearch import Elasticsearch

from documents.management.commands.mixins import ProgressBarMixin
from documents.tasks import index_reindex_elasticsearch, \
    index_optimize_elasticsearch
from paperless.settings import ELASTIC_SEARCH_DOCUMENT_INDEX, \
    ELASTIC_SEARCH_HOST


class Command(ProgressBarMixin, BaseCommand):
    help = "Manages the document index elastic search."

    def add_arguments(self, parser):
        parser.add_argument("command", choices=["reindex"])
        self.add_argument_progress_bar_mixin(parser)

    def handle(self, *args, **options):
        self.handle_progress_bar_mixin(**options)
        if Elasticsearch(ELASTIC_SEARCH_HOST).indices.exists(index=ELASTIC_SEARCH_DOCUMENT_INDEX):
            index_optimize_elasticsearch(self.use_progress_bar)
        else:
            index_reindex_elasticsearch(
                progress_bar_disable=self.use_progress_bar)
