import json
import os
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core import serializers

from documents.models import Document, Correspondent, Tag
from paperless.db import GnuPG

from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        Decrypt and rename all files in our collection into a given target
        directory.  And include a manifest file containing document data for
        easy import.
    """.replace("    ", "")

    def add_arguments(self, parser):
        parser.add_argument("target")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)
        self.target = None

    def handle(self, *args, **options):

        self.target = options["target"]

        if not os.path.exists(self.target):
            raise CommandError("That path doesn't exist")

        if not os.access(self.target, os.W_OK):
            raise CommandError("That path doesn't appear to be writable")

        if not settings.PASSPHRASE:
            settings.PASSPHRASE = input("Please enter the passphrase: ")

        documents = Document.objects.all()
        document_map = {d.pk: d for d in documents}
        manifest = json.loads(serializers.serialize("json", documents))
        for document_dict in manifest:

            document = document_map[document_dict["pk"]]

            target = os.path.join(self.target, document.file_name)
            document_dict["__exported_file_name__"] = target

            print("Exporting: {}".format(target))

            with open(target, "wb") as f:
                f.write(GnuPG.decrypted(document.source_file))
                t = int(time.mktime(document.created.timetuple()))
                os.utime(target, times=(t, t))

        manifest += json.loads(
            serializers.serialize("json", Correspondent.objects.all()))

        manifest += json.loads(serializers.serialize(
            "json", Tag.objects.all()))

        with open(os.path.join(self.target, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
