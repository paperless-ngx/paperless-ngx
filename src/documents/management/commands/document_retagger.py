import logging

import tqdm
from django.core.management.base import BaseCommand

from documents.classifier import load_classifier
from documents.models import Document
from ...signals.handlers import set_correspondent, set_document_type, set_tags


logger = logging.getLogger("paperless.management.retagger")


class Command(BaseCommand):

    help = """
        Using the current classification model, assigns correspondents, tags
        and document types to all documents, effectively allowing you to
        back-tag all previously indexed documents with metadata created (or
        modified) after their initial import.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument(
            "-c", "--correspondent",
            default=False,
            action="store_true"
        )
        parser.add_argument(
            "-T", "--tags",
            default=False,
            action="store_true"
        )
        parser.add_argument(
            "-t", "--document_type",
            default=False,
            action="store_true"
        )
        parser.add_argument(
            "-i", "--inbox-only",
            default=False,
            action="store_true"
        )
        parser.add_argument(
            "--use-first",
            default=False,
            action="store_true",
            help="By default this command won't try to assign a correspondent "
                 "if more than one matches the document.  Use this flag if "
                 "you'd rather it just pick the first one it finds."
        )
        parser.add_argument(
            "-f", "--overwrite",
            default=False,
            action="store_true",
            help="If set, the document retagger will overwrite any previously"
                 "set correspondent, document and remove correspondents, types"
                 "and tags that do not match anymore due to changed rules."
        )
        parser.add_argument(
            "--no-progress-bar",
            default=False,
            action="store_true",
            help="If set, the progress bar will not be shown"
        )
        parser.add_argument(
            "--suggest",
            default=False,
            action="store_true",
            help="Return the suggestion, don't change anything."
        )
        parser.add_argument(
            "--base-url",
            help="The base URL to use to build the link to the documents."
        )

    def handle(self, *args, **options):
        # Detect if we support color
        color = self.style.ERROR("test") != "test"

        if options["inbox_only"]:
            queryset = Document.objects.filter(tags__is_inbox_tag=True)
        else:
            queryset = Document.objects.all()
        documents = queryset.distinct()

        classifier = load_classifier()

        for document in tqdm.tqdm(
            documents,
            disable=options['no_progress_bar']
        ):

            if options['correspondent']:
                set_correspondent(
                    sender=None,
                    document=document,
                    classifier=classifier,
                    replace=options['overwrite'],
                    use_first=options['use_first'],
                    suggest=options['suggest'],
                    base_url=options['base_url'],
                    color=color)

            if options['document_type']:
                set_document_type(sender=None,
                                  document=document,
                                  classifier=classifier,
                                  replace=options['overwrite'],
                                  use_first=options['use_first'],
                                  suggest=options['suggest'],
                                  base_url=options['base_url'],
                                  color=color)

            if options['tags']:
                set_tags(
                    sender=None,
                    document=document,
                    classifier=classifier,
                    replace=options['overwrite'],
                    suggest=options['suggest'],
                    base_url=options['base_url'],
                    color=color)
