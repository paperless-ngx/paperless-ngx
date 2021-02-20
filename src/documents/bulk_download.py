from zipfile import ZipFile

from documents.models import Document


class BulkArchiveStrategy:

    def __init__(self, zipf: ZipFile):
        self.zipf = zipf

    def make_unique_filename(self,
                             doc: Document,
                             archive: bool = False,
                             folder: str = ""):
        counter = 0
        while True:
            filename = folder + doc.get_public_filename(archive, counter)
            if filename in self.zipf.namelist():
                counter += 1
            else:
                return filename

    def add_document(self, doc: Document):
        raise NotImplementedError()  # pragma: no cover


class OriginalsOnlyStrategy(BulkArchiveStrategy):

    def add_document(self, doc: Document):
        self.zipf.write(doc.source_path, self.make_unique_filename(doc))


class ArchiveOnlyStrategy(BulkArchiveStrategy):

    def __init__(self, zipf):
        super(ArchiveOnlyStrategy, self).__init__(zipf)

    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.zipf.write(doc.archive_path,
                            self.make_unique_filename(doc, archive=True))
        else:
            self.zipf.write(doc.source_path,
                            self.make_unique_filename(doc))


class OriginalAndArchiveStrategy(BulkArchiveStrategy):

    def add_document(self, doc: Document):
        if doc.has_archive_version:
            self.zipf.write(
                doc.archive_path, self.make_unique_filename(
                    doc, archive=True, folder="archive/"
                )
            )

        self.zipf.write(
            doc.source_path,
            self.make_unique_filename(doc, folder="originals/")
        )
