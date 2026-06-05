from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from documents import bulk_edit
from documents.models import Document
from documents.models import Folder
from documents.models import get_default_folder
from documents.signals.handlers import set_folder
from documents.tests.utils import DirectoriesMixin


class TestFolderModel(DirectoriesMixin, TestCase):
    def test_default_folder_created_on_demand(self) -> None:
        """
        GIVEN:
            - No folders exist
        WHEN:
            - The default folder is requested
        THEN:
            - A single default "Inbox" folder is created and reused
        """
        # Start from a clean slate (the data migration may have created one)
        Folder.objects.all().delete()
        self.assertEqual(Folder.objects.count(), 0)
        default = get_default_folder()
        self.assertEqual(default.name, "Inbox")
        self.assertTrue(default.is_default)
        # Calling again returns the same folder, does not create another
        again = get_default_folder()
        self.assertEqual(default.pk, again.pk)
        self.assertEqual(Folder.objects.filter(is_default=True).count(), 1)

    def test_hierarchy_and_full_path(self) -> None:
        root = Folder.objects.create(name="Personal")
        sub = Folder.objects.create(name="Taxes", parent=root)
        leaf = Folder.objects.create(name="2023", parent=sub)

        self.assertEqual(leaf.full_path, "Personal/Taxes/2023")
        self.assertEqual([f.pk for f in leaf.get_ancestors()], [sub.pk, root.pk])
        descendant_pks = {f.pk for f in root.get_descendants()}
        self.assertSetEqual(descendant_pks, {sub.pk, leaf.pk})

    def test_cannot_set_self_as_parent(self) -> None:
        folder = Folder.objects.create(name="A")
        folder.parent = folder
        with self.assertRaises(ValidationError):
            folder.clean()

    def test_cannot_set_descendant_as_parent(self) -> None:
        root = Folder.objects.create(name="root")
        child = Folder.objects.create(name="child", parent=root)
        root.parent = child
        with self.assertRaises(ValidationError):
            root.clean()

    def test_max_nesting_depth(self) -> None:
        parent = None
        folders = []
        for i in range(Folder.MAX_NESTING_DEPTH):
            parent = Folder.objects.create(name=f"f{i}", parent=parent)
            folders.append(parent)
        # One more level beyond the max should fail validation
        too_deep = Folder(name="too_deep", parent=folders[-1])
        with self.assertRaises(ValidationError):
            too_deep.clean()


class TestSetFolderSignal(DirectoriesMixin, TestCase):
    def test_unfiled_document_gets_default_folder(self) -> None:
        doc = Document.objects.create(checksum="A", title="A")
        self.assertIsNone(doc.folder)
        set_folder(sender=None, document=doc)
        doc.refresh_from_db()
        self.assertIsNotNone(doc.folder)
        self.assertTrue(doc.folder.is_default)

    def test_existing_folder_is_kept(self) -> None:
        folder = Folder.objects.create(name="Keep")
        doc = Document.objects.create(checksum="B", title="B", folder=folder)
        set_folder(sender=None, document=doc)
        doc.refresh_from_db()
        self.assertEqual(doc.folder_id, folder.pk)


class TestBulkEditFolder(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.f1 = Folder.objects.create(name="f1")
        self.f2 = Folder.objects.create(name="f2")
        self.doc1 = Document.objects.create(
            checksum="A",
            title="A",
            created=date(2023, 1, 1),
            folder=self.f1,
        )
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            created=date(2023, 1, 2),
            folder=self.f1,
        )

    def test_set_folder_single(self) -> None:
        bulk_edit.set_folder([self.doc1.id], self.f2.id)
        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.folder_id, self.f2.id)
        # doc2 untouched
        self.doc2.refresh_from_db()
        self.assertEqual(self.doc2.folder_id, self.f1.id)

    def test_set_folder_multiple(self) -> None:
        bulk_edit.set_folder([self.doc1.id, self.doc2.id], self.f2.id)
        self.assertEqual(
            Document.objects.filter(folder=self.f2).count(),
            2,
        )

    def test_set_folder_none_falls_back_to_default(self) -> None:
        bulk_edit.set_folder([self.doc1.id], None)
        self.doc1.refresh_from_db()
        self.assertIsNotNone(self.doc1.folder)
        self.assertTrue(self.doc1.folder.is_default)
