from django.core.management.base import BaseCommand

from documents.classifier import preprocess_content
from documents.models import Document
from ...mixins import Renderable


class Command(Renderable, BaseCommand):

    help = """
        There is no help.
    """.replace("    ", "")

    def __init__(self, *args, **kwargs):
        BaseCommand.__init__(self, *args, **kwargs)

    def handle(self, *args, **options):
        with open("dataset_tags.txt", "w") as f:
            for doc in Document.objects.exclude(tags__is_inbox_tag=True):
                labels = []
                for tag in doc.tags.filter(automatic_classification=True):
                    labels.append(tag.name)
                f.write(",".join(labels))
                f.write(";")
                f.write(preprocess_content(doc.content))
                f.write("\n")

        with open("dataset_types.txt", "w") as f:
            for doc in Document.objects.exclude(tags__is_inbox_tag=True):
                f.write(doc.document_type.name if doc.document_type is not None and doc.document_type.automatic_classification else "-")
                f.write(";")
                f.write(preprocess_content(doc.content))
                f.write("\n")

        with open("dataset_correspondents.txt", "w") as f:
            for doc in Document.objects.exclude(tags__is_inbox_tag=True):
                f.write(doc.correspondent.name if doc.correspondent is not None and doc.correspondent.automatic_classification else "-")
                f.write(";")
                f.write(preprocess_content(doc.content))
                f.write("\n")
