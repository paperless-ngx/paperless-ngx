import pytest
from django.db import DatabaseError
from django.db import models
from django.db import transaction

from documents.models import Correspondent
from documents.models import Document
from paperless_testing.factories import CorrespondentFactory
from paperless_testing.factories import DocumentFactory


@pytest.mark.django_db
class TestDocument:
    def test_correspondent_deletion_does_not_cascade(self) -> None:
        assert Correspondent.objects.count() == 0
        correspondent = CorrespondentFactory.create()
        assert Correspondent.objects.count() == 1

        assert Document.objects.count() == 0
        DocumentFactory.create(correspondent=correspondent)
        assert Document.objects.count() == 1
        assert Document.objects.first().correspondent is not None

        correspondent.delete()
        assert Correspondent.objects.count() == 0
        assert Document.objects.count() == 1
        assert Document.objects.first().correspondent is None


@pytest.mark.django_db
@pytest.mark.usefixtures("paperless_dirs")
class TestDocumentFilePathWrites:
    def test_full_save_does_not_write_file_paths(self) -> None:
        """
        GIVEN:
            - A document whose filename columns were changed in the DB after
              an instance was loaded
        WHEN:
            - The stale instance is saved without update_fields
        THEN:
            - The DB filename columns keep the newer values
            - Other fields from the stale instance are written
        """
        doc = DocumentFactory(filename="old.pdf", archive_filename="old.pdf")
        stale = Document.objects.get(pk=doc.pk)
        Document.objects.filter(pk=doc.pk).update(
            filename="new.pdf",
            archive_filename="new-archive.pdf",
        )

        stale.title = "changed"
        stale.save()

        doc.refresh_from_db()
        assert doc.filename == "new.pdf"
        assert doc.archive_filename == "new-archive.pdf"
        assert doc.title == "changed"

    @pytest.mark.parametrize(
        "save_kwargs",
        [
            pytest.param({"write_file_paths": True}, id="write-file-paths"),
            pytest.param(
                {"update_fields": ["filename", "archive_filename"]},
                id="explicit-update-fields",
            ),
        ],
    )
    def test_opt_in_writes_file_paths(self, save_kwargs: dict[str, object]) -> None:
        """
        GIVEN:
            - An existing document
        WHEN:
            - Its filename columns are changed in memory and saved with an
              explicit opt in
        THEN:
            - The DB filename columns are updated
        """
        doc = DocumentFactory(filename="old.pdf", archive_filename="old.pdf")

        doc.filename = "new.pdf"
        doc.archive_filename = "new.pdf"
        doc.save(**save_kwargs)

        doc.refresh_from_db()
        assert doc.filename == "new.pdf"
        assert doc.archive_filename == "new.pdf"

    def test_creation_writes_file_paths(self) -> None:
        """
        GIVEN:
            - A new, unsaved document with filename columns set
        WHEN:
            - It is saved
        THEN:
            - The filename columns are written
        """
        doc = DocumentFactory.build(filename="a.pdf", archive_filename="b.pdf")

        doc.save()

        doc.refresh_from_db()
        assert doc.filename == "a.pdf"
        assert doc.archive_filename == "b.pdf"

    def test_full_save_of_deleted_row_raises(self) -> None:
        """
        GIVEN:
            - An instance whose row was hard-deleted elsewhere
        WHEN:
            - The instance is saved without update_fields
        THEN:
            - A DatabaseError is raised instead of re-inserting the row
        """
        doc = DocumentFactory()
        stale = Document.objects.get(pk=doc.pk)
        # A plain QuerySet bypasses the soft-delete manager, so the row is
        # really gone (as after emptying the trash).
        models.QuerySet(model=Document).filter(pk=doc.pk).delete()

        # The savepoint keeps the failed UPDATE from poisoning the test transaction.
        with pytest.raises(DatabaseError), transaction.atomic():
            stale.save()

        assert not Document.global_objects.filter(pk=doc.pk).exists()
