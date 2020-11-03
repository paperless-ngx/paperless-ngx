import argparse
import threading
from multiprocessing import Pool
from multiprocessing.pool import ThreadPool

from django.core.management.base import BaseCommand

from documents.consumer import Consumer
from documents.models import Log, Document
from documents.parsers import get_parser_class


def process_document(doc):
    parser_class = get_parser_class(doc.file_name)
    if not parser_class:
        print("no parser available")
    else:
        print("Parser: {}".format(parser_class.__name__))
        parser = parser_class(doc.source_path, None)
        try:
            text = parser.get_text()
            doc.content = text
            doc.save()
        finally:
            parser.cleanup()


def document_index(value):
    ivalue = int(value)
    if not (1 <= ivalue <= Document.objects.count()):
        raise argparse.ArgumentTypeError(
            "{} is not a valid document index (out of range)".format(value))

    return ivalue


class Command(BaseCommand):

    help = "Performs OCR on all documents again!"


    def add_arguments(self, parser):
        parser.add_argument(
            "-s", "--start_index",
            default=None,
            type=document_index
        )

    def handle(self, *args, **options):

        docs = Document.objects.all().order_by("added")

        indices = range(options['start_index']-1, len(docs)) if options['start_index'] else range(len(docs))

        for i in indices:
            doc = docs[i]
            print("==================================")
            print("{} out of {}: {}".format(i+1, len(docs), doc.file_name))
            print("==================================")
            process_document(doc)
