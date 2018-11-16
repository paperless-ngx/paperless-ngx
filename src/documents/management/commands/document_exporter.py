import json
import os
import time
import shutil

from django.core.management.base import BaseCommand, CommandError
from django.core import serializers

from documents.models import Document, Correspondent, Tag
from paperless.db import GnuPG

from ...mixins import Renderable
from documents.settings import EXPORTER_FILE_NAME, EXPORTER_THUMBNAIL_NAME


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

        if options["legacy"]:
            self.dump_legacy()
        else:
            self.dump()

    def dump(self):

        documents = Document.objects.all()
        document_map = {d.pk: d for d in documents}
        manifest = json.loads(serializers.serialize("json", documents))

        for index, document_dict in enumerate(manifest):

            # Force output to unencrypted as that will be the current state.
            # The importer will make the decision to encrypt or not.
            manifest[index]["fields"]["storage_type"] = Document.STORAGE_TYPE_UNENCRYPTED  # NOQA: E501

            document = document_map[document_dict["pk"]]

            file_target = os.path.join(self.target, document.file_name)

            thumbnail_name = document.file_name + "-thumbnail.png"
            thumbnail_target = os.path.join(self.target, thumbnail_name)

            document_dict[EXPORTER_FILE_NAME] = document.file_name
            document_dict[EXPORTER_THUMBNAIL_NAME] = thumbnail_name

            print("Exporting: {}".format(file_target))

            t = int(time.mktime(document.created.timetuple()))
            if document.storage_type == Document.STORAGE_TYPE_GPG:

                with open(file_target, "wb") as f:
                    f.write(GnuPG.decrypted(document.source_file))
                    os.utime(file_target, times=(t, t))

                with open(thumbnail_target, "wb") as f:
                    f.write(GnuPG.decrypted(document.thumbnail_file))
                    os.utime(thumbnail_target, times=(t, t))

            else:

                shutil.copy(document.source_path, file_target)
                shutil.copy(document.thumbnail_path, thumbnail_target)

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

        if not doc.correspondent and not doc.title:
            return os.path.basename(doc.source_path)

        created = doc.created.strftime("%Y%m%d%H%M%SZ")
        tags = ",".join([t.slug for t in doc.tags.all()])

        if tags:
            return "{} - {} - {} - {}.{}".format(
                created, doc.correspondent, doc.title, tags, doc.file_type)

        return "{} - {} - {}.{}".format(
            created, doc.correspondent, doc.title, doc.file_type)
