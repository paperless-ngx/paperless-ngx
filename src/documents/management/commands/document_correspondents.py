from django.core.management.base import BaseCommand

from documents.models import Document, Correspondent

from ...mixins import Renderable


class Command(Renderable, BaseCommand):
    help = """
        Using the current set of correspondent rules, apply said rules to all
        documents in the database, effectively allowing you to back-tag all
        previously indexed documents with correspondent created (or modified)
        after their initial import.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        for document in Document.objects.all():
            # No matching correspondents, so no need to continue
            if document.correspondent:
                continue

            potential_correspondents = list(
                Correspondent.match_all(document.content))
            if not potential_correspondents:
                continue

            potential_count = len(potential_correspondents)

            selected = potential_correspondents[0]
            if potential_count > 1:
                message = "Detected {} potential correspondents for {}, " \
                          "so we've opted for {}"
                print(message.format(potential_count, document, selected))

            print('Tagging {} with correspondent "{}"'.format(document,
                                                              selected))
            document.correspondent = selected
            document.save(update_fields=("correspondent",))
