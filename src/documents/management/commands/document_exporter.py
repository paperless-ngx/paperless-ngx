import gnupg
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from paperless.db import GnuPG


class Command(BaseCommand):

    help = """
        Decrypt and rename all files in our collection into a given target
        directory.  Note that we don't export any of the parsed data since
        that can always be re-collected via the consumer.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument("target")

    def __init__(self, *args, **kwargs):
        self.verbosity = 0
        self.target = None
        self.gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):

        self.verbosity = options["verbosity"]
        self.target = options["target"]

        if not os.path.exists(self.target):
            raise CommandError("That path doesn't exist")

        if not os.access(self.target, os.W_OK):
            raise CommandError("That path doesn't appear to be writable")

        if not settings.PASSPHRASE:
            settings.PASSPHRASE = input("Please enter the passphrase: ")

        for document in Document.objects.all():

            target = os.path.join(self.target, document.parseable_file_name)

            self._render("Exporting: {}".format(target), 1)

            with open(target, "wb") as f:
                f.write(GnuPG.decrypted(document.pdf))

    def _render(self, text, verbosity):
        if self.verbosity >= verbosity:
            print(text)
