import hashlib
import shutil
from datetime import date
from pathlib import Path
from unittest import mock

from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.test import TestCase
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_groups_with_perms
from guardian.shortcuts import get_users_with_perms

from documents import bulk_edit
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


class TestBulkEdit(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.owner = User.objects.create(username="test_owner")
        self.user1 = User.objects.create(username="user1")
        self.user2 = User.objects.create(username="user2")
        self.group1 = Group.objects.create(name="group1")
        self.group2 = Group.objects.create(name="group2")

        patcher = mock.patch("documents.bulk_edit.bulk_update_documents.delay")
        self.async_task = patcher.start()
        self.addCleanup(patcher.stop)
        self.c1 = Correspondent.objects.create(name="c1")
        self.c2 = Correspondent.objects.create(name="c2")
        self.dt1 = DocumentType.objects.create(name="dt1")
        self.dt2 = DocumentType.objects.create(name="dt2")
        self.t1 = Tag.objects.create(name="t1")
        self.t2 = Tag.objects.create(name="t2")
        self.doc1 = Document.objects.create(
            checksum="A",
            title="A",
            created=date(2023, 1, 1),
        )
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            correspondent=self.c1,
            document_type=self.dt1,
            created=date(2023, 1, 2),
        )
        self.doc3 = Document.objects.create(
            checksum="C",
            title="C",
            correspondent=self.c2,
            document_type=self.dt2,
            created=date(2023, 1, 3),
        )
        self.doc4 = Document.objects.create(checksum="D", title="D")
        self.doc5 = Document.objects.create(checksum="E", title="E")
        self.doc2.tags.add(self.t1)
        self.doc3.tags.add(self.t2)
        self.doc4.tags.add(self.t1, self.t2)
        self.sp1 = StoragePath.objects.create(name="sp1", path="Something/{checksum}")

    def test_set_correspondent(self) -> None:
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.c2.id,
        )
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 3)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_correspondent(self) -> None:
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 0)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_type(self) -> None:
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.dt2.id,
        )
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 3)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_document_type(self) -> None:
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 0)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_storage_path(self) -> None:
        """
        GIVEN:
            - 5 documents without defined storage path
        WHEN:
            - Bulk edit called to add storage path to 1 document
        THEN:
            - Single document storage path update
        """
        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            self.sp1.id,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 4)

        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_unset_document_storage_path(self) -> None:
        """
        GIVEN:
            - 4 documents without defined storage path
            - 1 document with a defined storage
        WHEN:
            - Bulk edit called to remove storage path from 1 document
        THEN:
            - Single document storage path removed
        """
        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            self.sp1.id,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 4)

        bulk_edit.set_storage_path(
            [self.doc1.id],
            None,
        )

        self.assertEqual(Document.objects.filter(storage_path=None).count(), 5)

        self.async_task.assert_called()
        _, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_add_tag(self) -> None:
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.add_tag(
            [self.doc1.id, self.doc2.id, self.doc3.id, self.doc4.id],
            self.t1.id,
        )
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 4)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc3.id])

    def test_remove_tag(self) -> None:
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.remove_tag([self.doc1.id, self.doc3.id, self.doc4.id], self.t1.id)
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 1)
        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc4.id])

    def test_modify_tags(self) -> None:
        tag_unrelated = Tag.objects.create(name="unrelated")
        self.doc2.tags.add(tag_unrelated)
        self.doc3.tags.add(tag_unrelated)
        bulk_edit.modify_tags(
            [self.doc2.id, self.doc3.id],
            add_tags=[self.t2.id],
            remove_tags=[self.t1.id],
        )

        self.assertCountEqual(list(self.doc2.tags.all()), [self.t2, tag_unrelated])
        self.assertCountEqual(list(self.doc3.tags.all()), [self.t2, tag_unrelated])

        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        # TODO: doc3 should not be affected, but the query for that is rather complicated
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_modify_custom_fields(self) -> None:
        """
        GIVEN:
            - 2 documents with custom fields
            - 3 custom fields
        WHEN:
            - Custom fields are modified using old format (list of ids)
        THEN:
            - Custom fields are modified for the documents
        """
        cf = CustomField.objects.create(
            name="cf1",
            data_type=CustomField.FieldDataType.STRING,
        )
        cf2 = CustomField.objects.create(
            name="cf2",
            data_type=CustomField.FieldDataType.INT,
        )
        cf3 = CustomField.objects.create(
            name="cf3",
            data_type=CustomField.FieldDataType.STRING,
        )
        CustomFieldInstance.objects.create(
            document=self.doc1,
            field=cf,
        )
        CustomFieldInstance.objects.create(
            document=self.doc2,
            field=cf,
        )
        CustomFieldInstance.objects.create(
            document=self.doc2,
            field=cf3,
        )
        bulk_edit.modify_custom_fields(
            [self.doc1.id, self.doc2.id],
            add_custom_fields=[cf2.id],
            remove_custom_fields=[cf.id],
        )

        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()

        self.assertEqual(
            self.doc1.custom_fields.count(),
            1,
        )
        self.assertEqual(
            self.doc2.custom_fields.count(),
            2,
        )

        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_modify_custom_fields_with_values(self) -> None:
        """
        GIVEN:
            - 2 documents with custom fields
            - 3 custom fields
        WHEN:
            - Custom fields are modified using new format (dict)
        THEN:
            - Custom fields are modified for the documents
        """
        cf = CustomField.objects.create(
            name="cf",
            data_type=CustomField.FieldDataType.STRING,
        )
        cf1 = CustomField.objects.create(
            name="cf1",
            data_type=CustomField.FieldDataType.STRING,
        )
        cf2 = CustomField.objects.create(
            name="cf2",
            data_type=CustomField.FieldDataType.MONETARY,
        )
        cf3 = CustomField.objects.create(
            name="cf3",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )
        CustomFieldInstance.objects.create(
            document=self.doc2,
            field=cf,
        )
        CustomFieldInstance.objects.create(
            document=self.doc2,
            field=cf1,
        )
        CustomFieldInstance.objects.create(
            document=self.doc2,
            field=cf3,
        )
        bulk_edit.modify_custom_fields(
            [self.doc1.id, self.doc2.id],
            add_custom_fields={cf2.id: None, cf3.id: [self.doc3.id]},
            remove_custom_fields=[cf.id],
        )

        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()

        self.assertEqual(
            self.doc1.custom_fields.count(),
            2,
        )
        self.assertEqual(
            self.doc1.custom_fields.get(field=cf2).value,
            None,
        )
        self.assertEqual(
            self.doc1.custom_fields.get(field=cf3).value,
            [self.doc3.id],
        )
        self.assertEqual(
            self.doc2.custom_fields.count(),
            3,
        )
        self.assertEqual(
            self.doc2.custom_fields.get(field=cf3).value,
            [self.doc3.id],
        )
        # assert reflect document link
        self.assertEqual(
            self.doc3.custom_fields.first().value,
            [self.doc2.id, self.doc1.id],
        )

        self.async_task.assert_called_once()
        _, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

        # removal of document link cf, should also remove symmetric link
        bulk_edit.modify_custom_fields(
            [self.doc3.id],
            add_custom_fields={},
            remove_custom_fields=[cf3.id],
        )
        self.assertNotIn(
            self.doc3.id,
            self.doc1.custom_fields.filter(field=cf3).first().value,
        )
        self.assertNotIn(
            self.doc3.id,
            self.doc2.custom_fields.filter(field=cf3).first().value,
        )

    def test_modify_custom_fields_doclink_self_link(self) -> None:
        """
        GIVEN:
            - 2 existing documents
            - Existing doc link custom field
        WHEN:
            - Doc link field is modified to include self link
        THEN:
            - Self link should not be created
        """
        cf = CustomField.objects.create(
            name="cf",
            data_type=CustomField.FieldDataType.DOCUMENTLINK,
        )
        bulk_edit.modify_custom_fields(
            [self.doc1.id, self.doc2.id],
            add_custom_fields={cf.id: [self.doc1.id]},
            remove_custom_fields=[],
        )

        self.assertEqual(
            self.doc1.custom_fields.first().value,
            [self.doc2.id],
        )
        self.assertEqual(
            self.doc2.custom_fields.first().value,
            [self.doc1.id],
        )

    def test_delete(self) -> None:
        self.assertEqual(Document.objects.count(), 5)
        bulk_edit.delete([self.doc1.id, self.doc2.id])
        self.assertEqual(Document.objects.count(), 3)
        self.assertCountEqual(
            [doc.id for doc in Document.objects.all()],
            [self.doc3.id, self.doc4.id, self.doc5.id],
        )

    @mock.patch("documents.tasks.bulk_update_documents.delay")
    def test_set_permissions(self, m) -> None:
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]

        assign_perm("view_document", self.group1, self.doc1)

        permissions = {
            "view": {
                "users": [self.user1.id, self.user2.id],
                "groups": [self.group2.id],
            },
            "change": {
                "users": [self.user1.id],
                "groups": [self.group2.id],
            },
        }

        bulk_edit.set_permissions(
            doc_ids,
            set_permissions=permissions,
            owner=self.owner,
            merge=False,
        )
        m.assert_called_once()

        self.assertEqual(Document.objects.filter(owner=self.owner).count(), 3)
        self.assertEqual(Document.objects.filter(id__in=doc_ids).count(), 3)

        users_with_perms = get_users_with_perms(
            self.doc1,
        )
        self.assertEqual(users_with_perms.count(), 2)

        # group1 should be replaced by group2
        groups_with_perms = get_groups_with_perms(
            self.doc1,
        )
        self.assertEqual(groups_with_perms.count(), 1)

    @mock.patch("documents.tasks.bulk_update_documents.delay")
    def test_set_permissions_merge(self, m) -> None:
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]

        self.doc1.owner = self.user1
        self.doc1.save()

        assign_perm("view_document", self.user1, self.doc1)
        assign_perm("view_document", self.group1, self.doc1)

        permissions = {
            "view": {
                "users": [self.user2.id],
                "groups": [self.group2.id],
            },
            "change": {
                "users": [self.user2.id],
                "groups": [self.group2.id],
            },
        }
        bulk_edit.set_permissions(
            doc_ids,
            set_permissions=permissions,
            owner=self.owner,
            merge=True,
        )
        m.assert_called_once()

        # when merge is true owner doesn't get replaced if its not empty
        self.assertEqual(Document.objects.filter(owner=self.owner).count(), 2)
        self.assertEqual(Document.objects.filter(id__in=doc_ids).count(), 3)

        # merge of user1 which was pre-existing and user2
        users_with_perms = get_users_with_perms(
            self.doc1,
        )
        self.assertEqual(users_with_perms.count(), 2)

        # group1 should be merged by group2
        groups_with_perms = get_groups_with_perms(
            self.doc1,
        )
        self.assertEqual(groups_with_perms.count(), 2)

    @mock.patch("documents.models.Document.delete")
    def test_delete_documents_old_uuid_field(self, m) -> None:
        m.side_effect = Exception("Data too long for column 'transaction_id' at row 1")
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]
        bulk_edit.delete(doc_ids)
        with self.assertLogs(level="WARNING") as cm:
            bulk_edit.delete(doc_ids)
            self.assertIn("possible incompatible database column", cm.output[0])


class TestPDFActions(DirectoriesMixin, TestCase):
    def setUp(self) -> None:
        super().setUp()
        sample1 = self.dirs.scratch_dir / "sample.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000001.pdf",
            sample1,
        )
        sample1_archive = self.dirs.archive_dir / "sample_archive.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000001.pdf",
            sample1_archive,
        )
        sample2 = self.dirs.scratch_dir / "sample2.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000002.pdf",
            sample2,
        )
        sample2_archive = self.dirs.archive_dir / "sample2_archive.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000002.pdf",
            sample2_archive,
        )
        sample3 = self.dirs.scratch_dir / "sample3.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000003.pdf",
            sample3,
        )
        self.doc1 = Document.objects.create(
            checksum="A",
            title="A",
            filename=sample1,
            mime_type="application/pdf",
        )
        self.doc1.archive_filename = sample1_archive
        self.doc1.save()
        self.doc2 = Document.objects.create(
            checksum="B",
            title="B",
            filename=sample2,
            mime_type="application/pdf",
            page_count=8,
            created=date(2023, 1, 2),
        )
        self.doc2.archive_filename = sample2_archive
        self.doc2.save()
        self.doc3 = Document.objects.create(
            checksum="C",
            title="C",
            filename=sample3,
            mime_type="application/pdf",
        )
        img_doc = self.dirs.scratch_dir / "sample_image.jpg"
        shutil.copy(
            Path(__file__).parent / "samples" / "simple.jpg",
            img_doc,
        )
        img_doc_archive = self.dirs.archive_dir / "sample_image.pdf"
        shutil.copy(
            Path(__file__).parent
            / "samples"
            / "documents"
            / "originals"
            / "0000001.pdf",
            img_doc_archive,
        )
        self.img_doc = Document.objects.create(
            checksum="D",
            title="D",
            filename=img_doc,
            mime_type="image/jpeg",
            created=date(2023, 1, 3),
        )
        self.img_doc.archive_filename = img_doc_archive
        self.img_doc.save()

    @mock.patch("documents.tasks.consume_file.s")
    def test_merge(self, mock_consume_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action is called with 3 documents
        THEN:
            - Consume file should be called
        """
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]
        metadata_document_id = self.doc2.id
        user = User.objects.create(username="test_user")

        result = bulk_edit.merge(
            doc_ids,
            metadata_document_id=None,
            delete_originals=False,
            user=user,
        )

        expected_filename = (
            f"{'_'.join([str(doc_id) for doc_id in doc_ids])[:100]}_merged.pdf"
        )

        mock_consume_file.assert_called()
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(
            Path(consume_file_args[0].original_file).name,
            expected_filename,
        )
        self.assertEqual(consume_file_args[1].title, None)
        # No metadata_document_id, delete_originals False, so ASN should be None
        self.assertIsNone(consume_file_args[1].asn)

        # With metadata_document_id overrides
        result = bulk_edit.merge(doc_ids, metadata_document_id=metadata_document_id)
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].title, "B (merged)")
        self.assertEqual(consume_file_args[1].created, self.doc2.created)

        self.assertEqual(result, "OK")

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    def test_merge_and_delete_originals(
        self,
        mock_consume_file,
        mock_delete_documents,
    ):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action with deleting documents is called with 3 documents
        THEN:
            - Consume file task should be called
            - Document deletion task should be called
        """
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]
        self.doc1.archive_serial_number = 101
        self.doc2.archive_serial_number = 102
        self.doc3.archive_serial_number = 103
        self.doc1.save()
        self.doc2.save()
        self.doc3.save()

        result = bulk_edit.merge(doc_ids, delete_originals=True)
        self.assertEqual(result, "OK")

        expected_filename = (
            f"{'_'.join([str(doc_id) for doc_id in doc_ids])[:100]}_merged.pdf"
        )

        mock_consume_file.assert_called()
        mock_delete_documents.assert_called()
        consume_sig = mock_consume_file.return_value
        consume_sig.apply_async.assert_called_once()

        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(
            Path(consume_file_args[0].original_file).name,
            expected_filename,
        )
        self.assertEqual(consume_file_args[1].title, None)
        self.assertEqual(consume_file_args[1].asn, 101)

        delete_documents_args, _ = mock_delete_documents.call_args
        self.assertEqual(
            delete_documents_args[0],
            doc_ids,
        )

        self.doc1.refresh_from_db()
        self.doc2.refresh_from_db()
        self.doc3.refresh_from_db()
        self.assertIsNone(self.doc1.archive_serial_number)
        self.assertIsNone(self.doc2.archive_serial_number)
        self.assertIsNone(self.doc3.archive_serial_number)

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    def test_merge_and_delete_originals_restore_on_failure(
        self,
        mock_consume_file,
        mock_delete_documents,
    ) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action with deleting documents is called with 1 document
            - Error occurs when queuing consume file task
        THEN:
            - Archive serial numbers are restored
        """
        doc_ids = [self.doc1.id]
        self.doc1.archive_serial_number = 111
        self.doc1.save()
        sig = mock.Mock()
        sig.apply_async.side_effect = Exception("boom")
        mock_consume_file.return_value = sig

        with self.assertRaises(Exception):
            bulk_edit.merge(doc_ids, delete_originals=True)

        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.archive_serial_number, 111)

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    def test_merge_and_delete_originals_metadata_handoff(
        self,
        mock_consume_file,
        mock_delete_documents,
    ) -> None:
        """
        GIVEN:
            - Existing documents with ASNs
        WHEN:
            - Merge with delete_originals=True and metadata_document_id set
        THEN:
            - Handoff ASN uses metadata document ASN
        """
        doc_ids = [self.doc1.id, self.doc2.id]
        self.doc1.archive_serial_number = 101
        self.doc2.archive_serial_number = 202
        self.doc1.save()
        self.doc2.save()

        result = bulk_edit.merge(
            doc_ids,
            metadata_document_id=self.doc2.id,
            delete_originals=True,
        )
        self.assertEqual(result, "OK")

        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].asn, 202)

    def test_restore_archive_serial_numbers_task(self) -> None:
        """
        GIVEN:
            - Existing document with no archive serial number
        WHEN:
            - Restore archive serial number task is called with backup data
        THEN:
            - Document archive serial number is restored
        """
        self.doc1.archive_serial_number = 444
        self.doc1.save()
        Document.objects.filter(pk=self.doc1.id).update(archive_serial_number=None)

        backup: dict[int, int | None] = {self.doc1.id: 444}
        bulk_edit.restore_archive_serial_numbers_task(backup)

        self.doc1.refresh_from_db()
        self.assertEqual(self.doc1.archive_serial_number, 444)

    @mock.patch("documents.tasks.consume_file.s")
    def test_merge_with_archive_fallback(self, mock_consume_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action is called with 2 documents, one of which is an image and archive_fallback is set to True
        THEN:
            - Image document should be included
        """
        doc_ids = [self.doc2.id, self.img_doc.id]

        result = bulk_edit.merge(doc_ids, archive_fallback=True)
        self.assertEqual(result, "OK")

        expected_filename = (
            f"{'_'.join([str(doc_id) for doc_id in doc_ids])[:100]}_merged.pdf"
        )

        mock_consume_file.assert_called()
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(
            Path(consume_file_args[0].original_file).name,
            expected_filename,
        )

    @mock.patch("documents.tasks.consume_file.delay")
    @mock.patch("pikepdf.open")
    def test_merge_with_errors(self, mock_open_pdf, mock_consume_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action is called with 2 documents
            - Error occurs when opening both files
        THEN:
            - Consume file should not be called
        """
        mock_open_pdf.side_effect = Exception("Error opening PDF")
        doc_ids = [self.doc2.id, self.doc3.id]

        with self.assertLogs("paperless.bulk_edit", level="ERROR") as cm:
            bulk_edit.merge(doc_ids)
            error_str = cm.output[0]
            expected_str = (
                "Error merging document 2, it will not be included in the merge"
            )
            self.assertIn(expected_str, error_str)

        mock_consume_file.assert_not_called()

    @mock.patch("documents.tasks.consume_file.s")
    def test_split(self, mock_consume_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Split action is called with 1 document and 2 pages
        THEN:
            - Consume file should be called twice
        """
        doc_ids = [self.doc2.id]
        pages = [[1, 2], [3]]
        user = User.objects.create(username="test_user")
        result = bulk_edit.split(doc_ids, pages, delete_originals=False, user=user)
        self.assertEqual(mock_consume_file.call_count, 2)
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].title, "B (split 2)")
        self.assertIsNone(consume_file_args[1].asn)

        self.assertEqual(result, "OK")

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.chord")
    def test_split_and_delete_originals(
        self,
        mock_chord,
        mock_consume_file,
        mock_delete_documents,
    ):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Split action with deleting documents is called with 1 document and 2 page groups
            - delete_originals is set to True
        THEN:
            - Consume file should be called twice
            - Document deletion task should be called
        """
        doc_ids = [self.doc2.id]
        pages = [[1, 2], [3]]
        self.doc2.archive_serial_number = 200
        self.doc2.save()

        result = bulk_edit.split(doc_ids, pages, delete_originals=True)
        self.assertEqual(result, "OK")

        self.assertEqual(mock_consume_file.call_count, 2)
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].title, "B (split 2)")

        mock_delete_documents.assert_called()
        mock_chord.assert_called_once()

        delete_documents_args, _ = mock_delete_documents.call_args
        self.assertEqual(
            delete_documents_args[0],
            doc_ids,
        )

        self.doc2.refresh_from_db()
        self.assertIsNone(self.doc2.archive_serial_number)

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.chord")
    def test_split_restore_on_failure(
        self,
        mock_chord,
        mock_consume_file,
        mock_delete_documents,
    ) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Split action with deleting documents is called with 1 document and 2 page groups
            - Error occurs when queuing chord task
        THEN:
            - Archive serial numbers are restored
        """
        doc_ids = [self.doc2.id]
        pages = [[1, 2]]
        self.doc2.archive_serial_number = 222
        self.doc2.save()

        sig = mock.Mock()
        sig.apply_async.side_effect = Exception("boom")
        mock_chord.return_value = sig

        result = bulk_edit.split(doc_ids, pages, delete_originals=True)
        self.assertEqual(result, "OK")

        self.doc2.refresh_from_db()
        self.assertEqual(self.doc2.archive_serial_number, 222)

    @mock.patch("documents.tasks.consume_file.delay")
    @mock.patch("pikepdf.Pdf.save")
    def test_split_with_errors(self, mock_save_pdf, mock_consume_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Split action is called with 1 document and 2 page groups
            - Error occurs when saving the files
        THEN:
            - Consume file should not be called
        """
        mock_save_pdf.side_effect = Exception("Error saving PDF")
        doc_ids = [self.doc2.id]
        pages = [[1, 2], [3]]

        with self.assertLogs("paperless.bulk_edit", level="ERROR") as cm:
            bulk_edit.split(doc_ids, pages)
            error_str = cm.output[0]
            expected_str = "Error splitting document 2"
            self.assertIn(expected_str, error_str)

        mock_consume_file.assert_not_called()

    @mock.patch("documents.tasks.bulk_update_documents.si")
    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.s")
    @mock.patch("celery.chord.delay")
    def test_rotate(
        self,
        mock_chord,
        mock_update_document,
        mock_update_documents,
    ) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Rotate action is called with 2 documents
        THEN:
            - Rotate action should be called twice
        """
        doc_ids = [self.doc1.id, self.doc2.id]
        result = bulk_edit.rotate(doc_ids, 90)
        self.assertEqual(mock_update_document.call_count, 2)
        mock_update_documents.assert_called_once()
        mock_chord.assert_called_once()
        self.assertEqual(result, "OK")

    @mock.patch("documents.tasks.bulk_update_documents.si")
    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.s")
    @mock.patch("pikepdf.Pdf.save")
    def test_rotate_with_error(
        self,
        mock_pdf_save,
        mock_update_archive_file,
        mock_update_documents,
    ):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Rotate action is called with 2 documents
            - PikePDF raises an error
        THEN:
            - Rotate action should be called 0 times
        """
        mock_pdf_save.side_effect = Exception("Error saving PDF")
        doc_ids = [self.doc2.id, self.doc3.id]

        with self.assertLogs("paperless.bulk_edit", level="ERROR") as cm:
            bulk_edit.rotate(doc_ids, 90)
            error_str = cm.output[0]
            expected_str = "Error rotating document"
            self.assertIn(expected_str, error_str)
            mock_update_archive_file.assert_not_called()

    @mock.patch("documents.tasks.bulk_update_documents.si")
    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.s")
    @mock.patch("celery.chord.delay")
    def test_rotate_non_pdf(
        self,
        mock_chord,
        mock_update_document,
        mock_update_documents,
    ):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Rotate action is called with 2 documents, one of which is not a PDF
        THEN:
            - Rotate action should be performed 1 time, with the non-PDF document skipped
        """
        with self.assertLogs("paperless.bulk_edit", level="INFO") as cm:
            result = bulk_edit.rotate([self.doc2.id, self.img_doc.id], 90)
            output_str = cm.output[1]
            expected_str = "Document 4 is not a PDF, skipping rotation"
            self.assertIn(expected_str, output_str)
            self.assertEqual(mock_update_document.call_count, 1)
            mock_update_documents.assert_called_once()
            mock_chord.assert_called_once()
            self.assertEqual(result, "OK")

    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.delay")
    @mock.patch("pikepdf.Pdf.save")
    def test_delete_pages(self, mock_pdf_save, mock_update_archive_file) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Delete pages action is called with 1 document and 2 pages
        THEN:
            - Save should be called once
            - Archive file should be updated once
            - The document's page_count should be reduced by the number of deleted pages
        """
        doc_ids = [self.doc2.id]
        initial_page_count = self.doc2.page_count
        pages = [1, 3]
        result = bulk_edit.delete_pages(doc_ids, pages)
        mock_pdf_save.assert_called_once()
        mock_update_archive_file.assert_called_once()
        self.assertEqual(result, "OK")

        expected_page_count = initial_page_count - len(pages)
        self.doc2.refresh_from_db()
        self.assertEqual(self.doc2.page_count, expected_page_count)

    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.delay")
    @mock.patch("pikepdf.Pdf.save")
    def test_delete_pages_with_error(
        self,
        mock_pdf_save,
        mock_update_archive_file,
    ) -> None:
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Delete pages action is called with 1 document and 2 pages
            - PikePDF raises an error
        THEN:
            - Save should be called once
            - Archive file should not be updated
        """
        mock_pdf_save.side_effect = Exception("Error saving PDF")
        doc_ids = [self.doc2.id]
        pages = [1, 3]

        with self.assertLogs("paperless.bulk_edit", level="ERROR") as cm:
            bulk_edit.delete_pages(doc_ids, pages)
            error_str = cm.output[0]
            expected_str = "Error deleting pages from document"
            self.assertIn(expected_str, error_str)
            mock_update_archive_file.assert_not_called()

    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_basic_operations(self, mock_consume_file, mock_group) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with two operations to split the doc and rotate pages
        THEN:
            - A grouped task is generated and delay() is called
        """
        mock_group.return_value.delay.return_value = None
        doc_ids = [self.doc2.id]
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": 1, "rotate": 90}]

        result = bulk_edit.edit_pdf(doc_ids, operations)
        self.assertEqual(result, "OK")
        mock_group.return_value.delay.assert_called_once()

    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_with_user_override(self, mock_consume_file, mock_group) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with user override
        THEN:
            - Task is created with user context
        """
        mock_group.return_value.delay.return_value = None
        doc_ids = [self.doc2.id]
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": 1}]
        user = User.objects.create(username="editor")

        result = bulk_edit.edit_pdf(doc_ids, operations, user=user)
        self.assertEqual(result, "OK")
        mock_group.return_value.delay.assert_called_once()

    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_with_delete_original(self, mock_consume_file, mock_chord) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with delete_original=True
        THEN:
            - Task group is triggered
        """
        mock_chord.return_value.delay.return_value = None
        doc_ids = [self.doc2.id]
        operations = [{"page": 1}, {"page": 2}]
        self.doc2.archive_serial_number = 250
        self.doc2.save()

        result = bulk_edit.edit_pdf(doc_ids, operations, delete_original=True)
        self.assertEqual(result, "OK")
        mock_chord.assert_called_once()
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].asn, 250)
        self.doc2.refresh_from_db()
        self.assertIsNone(self.doc2.archive_serial_number)

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.chord")
    def test_edit_pdf_restore_on_failure(
        self,
        mock_chord: mock.Mock,
        mock_consume_file: mock.Mock,
        mock_delete_documents: mock.Mock,
    ) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with delete_original=True
            - Error occurs when queuing chord task
        THEN:
            - Archive serial numbers are restored
        """
        doc_ids = [self.doc2.id]
        operations = [{"page": 1}]
        self.doc2.archive_serial_number = 333
        self.doc2.save()

        sig = mock.Mock()
        sig.apply_async.side_effect = Exception("boom")
        mock_chord.return_value = sig

        with self.assertRaises(Exception):
            bulk_edit.edit_pdf(doc_ids, operations, delete_original=True)

        self.doc2.refresh_from_db()
        self.assertEqual(self.doc2.archive_serial_number, 333)

    @mock.patch("documents.tasks.update_document_content_maybe_archive_file.delay")
    def test_edit_pdf_with_update_document(
        self,
        mock_update_document: mock.Mock,
    ) -> None:
        """
        GIVEN:
            - A single existing PDF document
        WHEN:
            - edit_pdf is called with update_document=True and a single output
        THEN:
            - The original document is updated in-place
            - The update_document_content_maybe_archive_file task is triggered
        """
        doc_ids = [self.doc2.id]
        operations = [{"page": 1}, {"page": 2}]
        original_checksum = self.doc2.checksum
        original_page_count = self.doc2.page_count

        result = bulk_edit.edit_pdf(
            doc_ids,
            operations=operations,
            update_document=True,
            delete_original=False,
        )

        self.assertEqual(result, "OK")
        self.doc2.refresh_from_db()
        self.assertNotEqual(self.doc2.checksum, original_checksum)
        self.assertNotEqual(self.doc2.page_count, original_page_count)
        mock_update_document.assert_called_once_with(document_id=self.doc2.id)

    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_without_metadata(
        self,
        mock_consume_file: mock.Mock,
        mock_group: mock.Mock,
    ) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with include_metadata=False
        THEN:
            - Tasks are created with empty metadata
        """
        mock_group.return_value.delay.return_value = None
        doc_ids = [self.doc2.id]
        operations = [{"page": 1}]

        result = bulk_edit.edit_pdf(doc_ids, operations, include_metadata=False)
        self.assertEqual(result, "OK")
        mock_group.return_value.delay.assert_called_once()

    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_open_failure(
        self,
        mock_consume_file: mock.Mock,
        mock_group: mock.Mock,
    ) -> None:
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf fails to open PDF
        THEN:
            - Task group is not called
        """
        doc_ids = [self.doc2.id]
        operations = [
            {"page": 9999},  # invalid page, forces error during PDF load
        ]
        with self.assertLogs("paperless.bulk_edit", level="ERROR"):
            with self.assertRaises(Exception):
                bulk_edit.edit_pdf(doc_ids, operations)
        mock_group.assert_not_called()
        mock_consume_file.assert_not_called()

    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    def test_edit_pdf_multiple_outputs_with_update_flag_errors(
        self,
        mock_consume_file,
        mock_group,
    ):
        """
        GIVEN:
            - Existing document
        WHEN:
            - edit_pdf is called with multiple outputs and update_document=True
        THEN:
            - An error is logged and task group is not called
        """
        doc_ids = [self.doc2.id]
        operations = [
            {"page": 1, "doc": 0},
            {"page": 2, "doc": 1},
        ]
        with self.assertLogs("paperless.bulk_edit", level="ERROR"):
            with self.assertRaises(ValueError):
                bulk_edit.edit_pdf(doc_ids, operations, update_document=True)
        mock_group.assert_not_called()
        mock_consume_file.assert_not_called()

    @mock.patch("documents.bulk_edit.update_document_content_maybe_archive_file.delay")
    @mock.patch("pikepdf.open")
    def test_remove_password_update_document(self, mock_open, mock_update_document):
        doc = self.doc1
        original_checksum = doc.checksum

        fake_pdf = mock.MagicMock()
        fake_pdf.pages = [mock.Mock(), mock.Mock(), mock.Mock()]

        def save_side_effect(target_path):
            Path(target_path).write_bytes(b"new pdf content")

        fake_pdf.save.side_effect = save_side_effect
        mock_open.return_value.__enter__.return_value = fake_pdf

        result = bulk_edit.remove_password(
            [doc.id],
            password="secret",
            update_document=True,
        )

        self.assertEqual(result, "OK")
        mock_open.assert_called_once_with(doc.source_path, password="secret")
        fake_pdf.remove_unreferenced_resources.assert_called_once()
        doc.refresh_from_db()
        self.assertNotEqual(doc.checksum, original_checksum)
        expected_checksum = hashlib.md5(doc.source_path.read_bytes()).hexdigest()
        self.assertEqual(doc.checksum, expected_checksum)
        self.assertEqual(doc.page_count, len(fake_pdf.pages))
        mock_update_document.assert_called_once_with(document_id=doc.id)

    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.tempfile.mkdtemp")
    @mock.patch("pikepdf.open")
    def test_remove_password_creates_consumable_document(
        self,
        mock_open,
        mock_mkdtemp,
        mock_consume_file,
        mock_group,
        mock_chord,
    ):
        doc = self.doc2
        temp_dir = self.dirs.scratch_dir / "remove-password"
        temp_dir.mkdir(parents=True, exist_ok=True)
        mock_mkdtemp.return_value = str(temp_dir)

        fake_pdf = mock.MagicMock()
        fake_pdf.pages = [mock.Mock(), mock.Mock()]

        def save_side_effect(target_path):
            Path(target_path).write_bytes(b"password removed")

        fake_pdf.save.side_effect = save_side_effect
        mock_open.return_value.__enter__.return_value = fake_pdf
        mock_group.return_value.delay.return_value = None

        user = User.objects.create(username="owner")

        result = bulk_edit.remove_password(
            [doc.id],
            password="secret",
            include_metadata=False,
            update_document=False,
            delete_original=False,
            user=user,
        )

        self.assertEqual(result, "OK")
        mock_open.assert_called_once_with(doc.source_path, password="secret")
        mock_consume_file.assert_called_once()
        consume_args, _ = mock_consume_file.call_args
        consumable_document = consume_args[0]
        overrides = consume_args[1]
        expected_path = temp_dir / f"{doc.id}_unprotected.pdf"
        self.assertTrue(expected_path.exists())
        self.assertEqual(
            Path(consumable_document.original_file).resolve(),
            expected_path.resolve(),
        )
        self.assertEqual(overrides.owner_id, user.id)
        mock_group.assert_called_once_with([mock_consume_file.return_value])
        mock_group.return_value.delay.assert_called_once()
        mock_chord.assert_not_called()

    @mock.patch("documents.bulk_edit.delete")
    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("documents.bulk_edit.group")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.tempfile.mkdtemp")
    @mock.patch("pikepdf.open")
    def test_remove_password_deletes_original(
        self,
        mock_open,
        mock_mkdtemp,
        mock_consume_file,
        mock_group,
        mock_chord,
        mock_delete,
    ):
        doc = self.doc2
        temp_dir = self.dirs.scratch_dir / "remove-password-delete"
        temp_dir.mkdir(parents=True, exist_ok=True)
        mock_mkdtemp.return_value = str(temp_dir)

        fake_pdf = mock.MagicMock()
        fake_pdf.pages = [mock.Mock(), mock.Mock()]

        def save_side_effect(target_path):
            Path(target_path).write_bytes(b"password removed")

        fake_pdf.save.side_effect = save_side_effect
        mock_open.return_value.__enter__.return_value = fake_pdf
        mock_chord.return_value.delay.return_value = None

        result = bulk_edit.remove_password(
            [doc.id],
            password="secret",
            include_metadata=False,
            update_document=False,
            delete_original=True,
        )

        self.assertEqual(result, "OK")
        mock_open.assert_called_once_with(doc.source_path, password="secret")
        mock_consume_file.assert_called_once()
        mock_group.assert_not_called()
        mock_chord.assert_called_once()
        mock_chord.return_value.delay.assert_called_once()
        mock_delete.si.assert_called_once_with([doc.id])

    @mock.patch("pikepdf.open")
    def test_remove_password_open_failure(self, mock_open):
        mock_open.side_effect = RuntimeError("wrong password")

        with self.assertLogs("paperless.bulk_edit", level="ERROR") as cm:
            with self.assertRaises(ValueError) as exc:
                bulk_edit.remove_password([self.doc1.id], password="secret")

        self.assertIn("wrong password", str(exc.exception))
        self.assertIn("Error removing password from document", cm.output[0])
