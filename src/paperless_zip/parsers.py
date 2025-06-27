import mimetypes
import shutil
import tempfile
import zipfile
from pathlib import Path

from django.conf import settings

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.parsers import DocumentParser
from documents.parsers import ParseError
from documents.parsers import get_parser_class_for_mime_type
from documents.skip_import import SkipImportException
from documents.tasks import consume_file


class ZipDocumentParser(DocumentParser):
    """
    Parser for ZIP files. Extracts files to a temp folder and adds supported types to the consumable_file list.
    * Skips hidden files.
    * Does not add the ZIP itself as a document.
    """

    def get_settings(self):
        return settings

    def parse(self, document_path, mime_type, file_name=None):
        temp_extract_dir = Path(
            tempfile.mkdtemp(prefix="paperless-zip-", dir=self.tempdir),
        )
        persistent_dir = Path(settings.SCRATCH_DIR)
        persistent_dir.mkdir(parents=True, exist_ok=True)
        found_supported = False
        zip_name = Path(document_path).name  # Includes .zip extension
        try:
            with zipfile.ZipFile(document_path, "r") as zip_ref:
                # replacing the one-liner "zip_ref.extractall(temp_extract_dir)"
                # for a bit of security to prevent Zip Slip by checking the resolved path
                # and ensuring it does not escape the temp directory.
                for member in zip_ref.infolist():
                    extracted_path = temp_extract_dir / member.filename
                    try:
                        abs_extracted_path = extracted_path.resolve()
                    except Exception:
                        continue  # Skip invalid paths
                    if not str(abs_extracted_path).startswith(
                        str(temp_extract_dir.resolve()),
                    ):
                        continue  # Unsafe path, skip
                    zip_ref.extract(member, temp_extract_dir)
            for file in temp_extract_dir.rglob("*"):
                if file.is_file():
                    # Skip hidden files (dotfiles, AppleDouble, etc.)
                    if file.name.startswith("."):
                        continue
                    mime = mimetypes.guess_type(str(file))[0]
                    parser_class = (
                        get_parser_class_for_mime_type(mime) if mime else None
                    )
                    if parser_class is not None:
                        # Rename file to zipname#originalname before moving
                        new_name = f"{zip_name}#{file.name}"
                        dest = persistent_dir / new_name
                        shutil.move(str(file), str(dest))
                        source = getattr(self, "source", DocumentSource.ConsumeFolder)
                        # Set document title to the PDF name only (without ZIP)
                        pdf_title = Path(file.name).stem
                        overrides = DocumentMetadataOverrides(
                            filename=new_name,
                            title=pdf_title,
                        )
                        input_doc = ConsumableDocument(
                            source=source,
                            original_file=dest,
                        )
                        consume_file.delay(input_doc, overrides)
                        found_supported = True
            if not found_supported:
                raise ParseError("No supported files found in ZIP archive.")
            self.text = ""
            # Raise SkipImportException to skip the ZIP itself
            raise SkipImportException(
                f"ZIP '{zip_name}' extracted and files enqueued for import.",
            )
        finally:
            shutil.rmtree(temp_extract_dir, ignore_errors=True)
