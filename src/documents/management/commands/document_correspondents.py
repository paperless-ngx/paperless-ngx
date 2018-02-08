import sys

from django.core.management.base import BaseCommand

from documents.models import Correspondent, Document

from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        Using the current set of correspondent rules, apply said rules to all
        documents in the database, effectively allowing you to back-tag all
        previously indexed documents with correspondent created (or modified)
        after their initial import.
    """.replace("    ", "")

    TOO_MANY_CONTINUE = (
        "Detected {} potential correspondents for {}, so we've opted for {}")
    TOO_MANY_SKIP = (
        "Detected {} potential correspondents for {}, so we're skipping it")
    CHANGE_MESSAGE = (
        'Document {}: "{}" was given the correspondent id {}: "{}"')

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        BaseCommand.__init__(self, *args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument(
            "--use-first",
            default=False,
            action="store_true",
            help="By default this command won't try to assign a correspondent "
                 "if more than one matches the document.  Use this flag if "
                 "you'd rather it just pick the first one it finds."
        )

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]

        for document in Document.objects.filter(correspondent__isnull=True):

            potential_correspondents = list(
                Correspondent.match_all(document.content))

            if not potential_correspondents:
                continue

            potential_count = len(potential_correspondents)
            correspondent = potential_correspondents[0]

            if potential_count > 1:
                if not options["use_first"]:
                    print(
                        self.TOO_MANY_SKIP.format(potential_count, document),
                        file=sys.stderr
                    )
                    continue
                print(
                    self.TOO_MANY_CONTINUE.format(
                        potential_count,
                        document,
                        correspondent
                    ),
                    file=sys.stderr
                )

            document.correspondent = correspondent
            document.save(update_fields=("correspondent",))

            print(
                self.CHANGE_MESSAGE.format(
                    document.pk,
                    document.title,
                    correspondent.pk,
                    correspondent.name
                ),
                file=sys.stderr
            )
