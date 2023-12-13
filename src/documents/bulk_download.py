import os

from documents.models import Document
from documents.parsers import merge_pdfs


class MergedPdfFile:
    def __init__(self, output_file_path):
        self._output_file_path = output_file_path
        self._input_file_paths = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        merge_pdfs(self._input_file_paths, self._output_file_path)

    def namelist(self):
        return self._input_file_paths

    def write(self, document_path, _):
        self._input_file_paths.append(document_path)


class BulkArchiveStrategy:
    def __init__(self, writer, follow_formatting: bool = False):
        self.writer = writer
        if follow_formatting:
            self.make_unique_filename = self._formatted_filepath
        else:
            self.make_unique_filename = self._filename_only

    def _filename_only(
        self,
        doc: Document,
        archive: bool = False,
        folder: str = "",
    ):
        """
        Constructs a unique name for the given document to be used inside the
        zip file.

        The filename might not be unique enough, so a counter is appended if needed
        """
        counter = 0
        while True:
            filename = folder + doc.get_public_filename(archive, counter)
            if filename in self.writer.namelist():
                counter += 1
            else:
                return filename

    def _formatted_filepath(
        self,
        doc: Document,
        archive: bool = False,
        folder: str = "",
    ):
        """
        Constructs a full file path for the given document to be used inside
        the zipfile.

        The path is already unique, as handled when a document is consumed or updated
        """
        if archive and doc.has_archive_version:
            in_archive_path = os.path.join(folder, doc.archive_filename)
        else:
            in_archive_path = os.path.join(folder, doc.filename)

        return in_archive_path

    def add_document(self, doc: Document):
        raise NotImplementedError  # pragma: no cover


class OriginalsOnlyStrategy(BulkArchiveStrategy):
    def add_document(self, doc: Document):
        self.writer.write(doc.source_path, self.make_unique_filename(doc))


class ArchiveOnlyStrategy(BulkArchiveStrategy):
    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.writer.write(
                doc.archive_path,
                self.make_unique_filename(doc, archive=True),
            )
        else:
            self.writer.write(doc.source_path, self.make_unique_filename(doc))


class OriginalAndArchiveStrategy(BulkArchiveStrategy):
    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.writer.write(
                doc.archive_path,
                self.make_unique_filename(doc, archive=True, folder="archive/"),
            )

        self.writer.write(
            doc.source_path,
            self.make_unique_filename(doc, folder="originals/"),
        )
