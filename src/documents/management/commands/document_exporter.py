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
        parser.add_argument(
            "--legacy",
            action="store_true",
            help="Don't try to export all of the document data, just dump the "
                 "original document files out in a format that makes "
                 "re-consuming them easy."
        )

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

        if options["legacy"]:
            self.dump_legacy()
        else:
            self.dump()

    def dump(self):

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

    def dump_legacy(self):

        for document in Document.objects.all():

            target = os.path.join(
                self.target, self._get_legacy_file_name(document))

            print("Exporting: {}".format(target))

            with open(target, "wb") as f:
                f.write(GnuPG.decrypted(document.source_file))
                t = int(time.mktime(document.created.timetuple()))
                os.utime(target, times=(t, t))

    @staticmethod
    def _get_legacy_file_name(doc):
        if doc.correspondent and doc.title:
            tags = ",".join([t.slug for t in doc.tags.all()])
            if tags:
                return "{} - {} - {}.{}".format(
                    doc.correspondent, doc.title, tags, doc.file_type)
            return "{} - {}.{}".format(
                doc.correspondent, doc.title, doc.file_type)
        return os.path.basename(doc.source_path)
