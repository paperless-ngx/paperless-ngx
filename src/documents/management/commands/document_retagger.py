from django.core.management.base import BaseCommand

from documents.models import Document, Tag

from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        Using the current set of tagging rules, apply said rules to all
        documents in the database, effectively allowing you to back-tag all
        previously indexed documents with tags created (or modified) after
        their initial import.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        for document in Document.objects.all():

            tags = Tag.objects.exclude(
                pk__in=document.tags.values_list("pk", flat=True))

            for tag in Tag.match_all(document.content, tags):
                print('Tagging {} with "{}"'.format(document, tag))
                document.tags.add(tag)
