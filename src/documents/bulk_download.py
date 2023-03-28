import os
from zipfile import ZipFile

from documents.models import Document


class BulkArchiveStrategy:
    def __init__(self, zipf: ZipFile, follow_formatting: bool = False):
        self.zipf = zipf
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
            if filename in self.zipf.namelist():
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
        self.zipf.write(doc.source_path, self.make_unique_filename(doc))


class ArchiveOnlyStrategy(BulkArchiveStrategy):
    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.zipf.write(
                doc.archive_path,
                self.make_unique_filename(doc, archive=True),
            )
        else:
            self.zipf.write(doc.source_path, self.make_unique_filename(doc))


class OriginalAndArchiveStrategy(BulkArchiveStrategy):
    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.zipf.write(
                doc.archive_path,
                self.make_unique_filename(doc, archive=True, folder="archive/"),
            )

        self.zipf.write(
            doc.source_path,
            self.make_unique_filename(doc, folder="originals/"),
        )
