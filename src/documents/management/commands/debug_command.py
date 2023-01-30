from pathlib import Path

from django.core.management.base import BaseCommand
from documents import barcodes


class Command(BaseCommand):
    def handle(self, *args, **options):
        path = Path("./documents/tests/samples/barcodes/barcode-39-asn-123.pdf")
        doc_barcode_info = barcodes.scan_file_for_barcodes(path)
        _ = barcodes.get_separating_barcodes(doc_barcode_info.barcodes)
        print(doc_barcode_info)
