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
from documents.bulk_edit import get_reorganized_title
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.tests.utils import DirectoriesMixin


class TestBulkEdit(DirectoriesMixin, TestCase):
    def setUp(self):
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

    def test_set_correspondent(self):
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.c2.id,
        )
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 3)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_correspondent(self):
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 1)
        bulk_edit.set_correspondent([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(correspondent=self.c2).count(), 0)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_type(self):
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type(
            [self.doc1.id, self.doc2.id, self.doc3.id],
            self.dt2.id,
        )
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 3)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_unset_document_type(self):
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 1)
        bulk_edit.set_document_type([self.doc1.id, self.doc2.id, self.doc3.id], None)
        self.assertEqual(Document.objects.filter(document_type=self.dt2).count(), 0)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_set_document_storage_path(self):
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
        args, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_unset_document_storage_path(self):
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
        args, kwargs = self.async_task.call_args

        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id])

    def test_add_tag(self):
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.add_tag(
            [self.doc1.id, self.doc2.id, self.doc3.id, self.doc4.id],
            self.t1.id,
        )
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 4)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc3.id])

    def test_remove_tag(self):
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 2)
        bulk_edit.remove_tag([self.doc1.id, self.doc3.id, self.doc4.id], self.t1.id)
        self.assertEqual(Document.objects.filter(tags__id=self.t1.id).count(), 1)
        self.async_task.assert_called_once()
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc4.id])

    def test_modify_tags(self):
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
        args, kwargs = self.async_task.call_args
        # TODO: doc3 should not be affected, but the query for that is rather complicated
        self.assertCountEqual(kwargs["document_ids"], [self.doc2.id, self.doc3.id])

    def test_modify_custom_fields(self):
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
        args, kwargs = self.async_task.call_args
        self.assertCountEqual(kwargs["document_ids"], [self.doc1.id, self.doc2.id])

    def test_modify_custom_fields_with_values(self):
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
        args, kwargs = self.async_task.call_args
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

    def test_modify_custom_fields_doclink_self_link(self):
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

    def test_delete(self):
        self.assertEqual(Document.objects.count(), 5)
        bulk_edit.delete([self.doc1.id, self.doc2.id])
        self.assertEqual(Document.objects.count(), 3)
        self.assertCountEqual(
            [doc.id for doc in Document.objects.all()],
            [self.doc3.id, self.doc4.id, self.doc5.id],
        )

    @mock.patch("documents.tasks.bulk_update_documents.delay")
    def test_set_permissions(self, m):
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
    def test_set_permissions_merge(self, m):
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
    def test_delete_documents_old_uuid_field(self, m):
        m.side_effect = Exception("Data too long for column 'transaction_id' at row 1")
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]
        bulk_edit.delete(doc_ids)
        with self.assertLogs(level="WARNING") as cm:
            bulk_edit.delete(doc_ids)
            self.assertIn("possible incompatible database column", cm.output[0])


class TestReorganizedTitleGeneration(TestCase):
    """
    Test the get_reorganized_title function that handles smart renaming
    of reorganized documents with incremental numbering.
    """

    def test_first_reorganization(self):
        """
        GIVEN:
            - A document title without any reorganized suffix
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should add "(reorganized)" suffix
        """
        result = get_reorganized_title("My Document")
        self.assertEqual(result, "My Document (reorganized)")

    def test_second_reorganization(self):
        """
        GIVEN:
            - A document title with "(reorganized)" suffix
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should change to "(reorganized 1)" suffix
        """
        result = get_reorganized_title("My Document (reorganized)")
        self.assertEqual(result, "My Document (reorganized 1)")

    def test_increment_numbered_reorganization(self):
        """
        GIVEN:
            - A document title with "(reorganized N)" suffix
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should increment the number to "(reorganized N+1)"
        """
        result1 = get_reorganized_title("My Document (reorganized 1)")
        self.assertEqual(result1, "My Document (reorganized 2)")

        result2 = get_reorganized_title("My Document (reorganized 5)")
        self.assertEqual(result2, "My Document (reorganized 6)")

        result3 = get_reorganized_title("My Document (reorganized 99)")
        self.assertEqual(result3, "My Document (reorganized 100)")

    def test_custom_suffix_word(self):
        """
        GIVEN:
            - A custom suffix word instead of "reorganized"
        WHEN:
            - get_reorganized_title is called with custom suffix_word
        THEN:
            - Should use the custom word in the suffix
        """
        result1 = get_reorganized_title("My Document", "processed")
        self.assertEqual(result1, "My Document (processed)")

        result2 = get_reorganized_title("My Document (processed)", "processed")
        self.assertEqual(result2, "My Document (processed 1)")

        result3 = get_reorganized_title("My Document (processed 3)", "processed")
        self.assertEqual(result3, "My Document (processed 4)")

    def test_with_extra_spaces(self):
        """
        GIVEN:
            - A document title with extra spaces before the suffix
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should handle the spaces correctly
        """
        result1 = get_reorganized_title("My Document  (reorganized)")
        self.assertEqual(result1, "My Document (reorganized 1)")

        result2 = get_reorganized_title("My Document   (reorganized 2)")
        self.assertEqual(result2, "My Document (reorganized 3)")

    def test_no_false_positives(self):
        """
        GIVEN:
            - Document titles that contain similar but different patterns
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should not match false positives and add new suffix
        """
        # These should not be detected as reorganized documents
        result1 = get_reorganized_title("Document about reorganized companies")
        self.assertEqual(result1, "Document about reorganized companies (reorganized)")

        result2 = get_reorganized_title("My (reorganized) thoughts")
        self.assertEqual(result2, "My (reorganized) thoughts (reorganized)")

        result3 = get_reorganized_title("Document (reorganized in middle) content")
        self.assertEqual(
            result3,
            "Document (reorganized in middle) content (reorganized)",
        )

    def test_empty_and_edge_cases(self):
        """
        GIVEN:
            - Edge cases like empty strings or unusual inputs
        WHEN:
            - get_reorganized_title is called
        THEN:
            - Should handle gracefully
        """
        result1 = get_reorganized_title("")
        self.assertEqual(result1, " (reorganized)")

        result2 = get_reorganized_title("   ")
        self.assertEqual(result2, "    (reorganized)")

        result3 = get_reorganized_title("Single")
        self.assertEqual(result3, "Single (reorganized)")


class TestPDFActions(DirectoriesMixin, TestCase):
    def setUp(self):
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
    def test_merge(self, mock_consume_file):
        """
        GIVEN:
            - Existing documents
        WHEN:
            - Merge action is called with 3 documents
        THEN:
            - Consume file should be called
        """
        doc_ids = [self.doc1.id, self.doc2.id, self.doc3.id]
        metadata_document_id = self.doc1.id
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

        # With metadata_document_id overrides
        result = bulk_edit.merge(doc_ids, metadata_document_id=metadata_document_id)
        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(consume_file_args[1].title, "A (merged)")

        self.assertEqual(result, "OK")

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.chain")
    def test_merge_and_delete_originals(
        self,
        mock_chain,
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

        result = bulk_edit.merge(doc_ids, delete_originals=True)
        self.assertEqual(result, "OK")

        expected_filename = (
            f"{'_'.join([str(doc_id) for doc_id in doc_ids])[:100]}_merged.pdf"
        )

        mock_consume_file.assert_called()
        mock_delete_documents.assert_called()
        mock_chain.assert_called_once()

        consume_file_args, _ = mock_consume_file.call_args
        self.assertEqual(
            Path(consume_file_args[0].original_file).name,
            expected_filename,
        )
        self.assertEqual(consume_file_args[1].title, None)

        delete_documents_args, _ = mock_delete_documents.call_args
        self.assertEqual(
            delete_documents_args[0],
            doc_ids,
        )

    @mock.patch("documents.tasks.consume_file.s")
    def test_merge_with_archive_fallback(self, mock_consume_file):
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
    def test_merge_with_errors(self, mock_open_pdf, mock_consume_file):
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
    def test_split(self, mock_consume_file):
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

    @mock.patch("documents.tasks.consume_file.delay")
    @mock.patch("pikepdf.Pdf.save")
    def test_split_with_errors(self, mock_save_pdf, mock_consume_file):
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
    def test_rotate(self, mock_chord, mock_update_document, mock_update_documents):
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
    def test_delete_pages(self, mock_pdf_save, mock_update_archive_file):
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
    def test_delete_pages_with_error(self, mock_pdf_save, mock_update_archive_file):
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

    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    @mock.patch("documents.tasks.consume_file.s")
    def test_reorganize_uses_correct_file_path(
        self,
        mock_consume_file,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
    ):
        """
        GIVEN:
            - Document with archive version (doc2) and document without archive version (doc3)
        WHEN:
            - Reorganize action is called on each document
        THEN:
            - Should use archive path for document with archive version
            - Should use source path for document without archive version
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(4)]  # 4 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(return_value=2)  # Has 2 pages
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [1, 2],  # Simple page reorder
            ],
        }

        # Test with document that has archive version (doc2)
        doc_ids = [self.doc2.id]
        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
        )

        # Verify that pikepdf.open was called with the archive path
        mock_open_pdf.assert_called_with(self.doc2.archive_path)
        self.assertEqual(result, "OK")

        # Reset mocks
        mock_open_pdf.reset_mock()
        mock_consume_file.reset_mock()

        # Test with document that doesn't have archive version (doc3)
        doc_ids = [self.doc3.id]
        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
        )

        # Verify that pikepdf.open was called with the source path
        mock_open_pdf.assert_called_with(self.doc3.source_path)
        self.assertEqual(result, "OK")

    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    @mock.patch("documents.tasks.consume_file.s")
    def test_reorganize_simple_reorder(
        self,
        mock_consume_file,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
    ):
        """
        GIVEN:
            - Existing document with 8 pages
        WHEN:
            - Reorganize action is called with simple page reordering (single doc output)
        THEN:
            - Consume file should be called once
            - Title should indicate reorganization
            - Pages should be reordered correctly
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(8)]  # 8 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(return_value=8)  # Has 8 pages
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [3, 1, 2, 4, 5, 6, 7, 8],  # Reorder pages: move page 3 to beginning
            ],
        }

        user = User.objects.create(username="test_user")
        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
            user=user,
        )

        # Verify the pages were accessed in the correct order
        expected_page_indices = [2, 0, 1, 3, 4, 5, 6, 7]  # 0-based indices
        self.assertEqual(
            mock_dst_pdf.pages.append.call_count,
            len(expected_page_indices),
        )
        for i, expected_idx in enumerate(expected_page_indices):
            actual_page = mock_dst_pdf.pages.append.call_args_list[i][0][0]
            expected_page = mock_source_pdf.pages[expected_idx]
            self.assertEqual(actual_page, expected_page)

        mock_consume_file.assert_called_once()
        consume_file_args, _ = mock_consume_file.call_args

        # Check that the consumed document has reorganized title
        self.assertEqual(consume_file_args[1].title, "B (reorganized)")
        self.assertEqual(result, "OK")

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    @mock.patch("documents.tasks.consume_file.s")
    def test_reorganize_split_with_rotation(
        self,
        mock_consume_file,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
        mock_chord,
        mock_delete_documents,
    ):
        """
        GIVEN:
            - Existing document with 8 pages
        WHEN:
            - Reorganize action is called to split into 2 docs with rotation
        THEN:
            - Consume file should be called twice
            - Titles should indicate parts
            - Pages should be extracted correctly with rotation applied
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(8)]  # 8 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        # Create separate mock PDFs for each output document
        mock_dst_pdf1 = mock.Mock()
        mock_dst_pdf1.pages = mock.Mock()
        mock_dst_pdf1.pages.__len__ = mock.Mock(return_value=3)  # First doc has 3 pages
        # Support indexing for rotation (dst_pdf.pages[-1])
        mock_dst_pdf1.pages.__getitem__ = mock.Mock(return_value=mock.Mock())
        mock_dst_pdf2 = mock.Mock()
        mock_dst_pdf2.pages = mock.Mock()
        mock_dst_pdf2.pages.__len__ = mock.Mock(
            return_value=3,
        )  # Second doc has 3 pages
        mock_dst_pdf2.pages.__getitem__ = mock.Mock(return_value=mock.Mock())
        mock_new_pdf.side_effect = [mock_dst_pdf1, mock_dst_pdf2]

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [1, 2, {"p": 3, "r": 90}],  # First doc: pages 1,2,3 with page 3 rotated
                [4, 5, 6],  # Second doc: pages 4,5,6
            ],
        }

        user = User.objects.create(username="test_user")
        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
            delete_original=True,
            user=user,
        )

        self.assertEqual(mock_consume_file.call_count, 2)

        # Verify first document pages (pages 1, 2, 3)
        expected_first_pages = [0, 1, 2]  # 0-based indices
        self.assertEqual(
            mock_dst_pdf1.pages.append.call_count,
            len(expected_first_pages),
        )
        for i, expected_idx in enumerate(expected_first_pages):
            actual_page = mock_dst_pdf1.pages.append.call_args_list[i][0][0]
            expected_page = mock_source_pdf.pages[expected_idx]
            self.assertEqual(actual_page, expected_page)

        # Verify rotation was applied to the third page (after it was added)
        # The rotation happens after dst_pdf.pages.append, so we check pages[-1].rotate
        mock_dst_pdf1.pages.__getitem__.assert_called_with(-1)
        rotated_page = mock_dst_pdf1.pages.__getitem__.return_value
        rotated_page.rotate.assert_called_once_with(90, relative=False)

        # Verify second document pages (pages 4, 5, 6)
        expected_second_pages = [3, 4, 5]  # 0-based indices
        self.assertEqual(
            mock_dst_pdf2.pages.append.call_count,
            len(expected_second_pages),
        )
        for i, expected_idx in enumerate(expected_second_pages):
            actual_page = mock_dst_pdf2.pages.append.call_args_list[i][0][0]
            expected_page = mock_source_pdf.pages[expected_idx]
            self.assertEqual(actual_page, expected_page)

        # Check first document
        first_call_args, _ = mock_consume_file.call_args_list[0]
        self.assertEqual(first_call_args[1].title, "B (part 1)")

        # Check second document
        second_call_args, _ = mock_consume_file.call_args_list[1]
        self.assertEqual(second_call_args[1].title, "B (part 2)")

        # Verify chord was called with consume tasks and delete task
        mock_chord.assert_called_once()
        chord_args = mock_chord.call_args[1]
        self.assertIn("header", chord_args)
        self.assertIn("body", chord_args)

        # Verify the delete task was set up correctly
        mock_delete_documents.assert_called_once_with([self.doc2.id])

        self.assertEqual(result, "OK")

    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    @mock.patch("documents.tasks.consume_file.s")
    def test_reorganize_with_comments(
        self,
        mock_consume_file,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
    ):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called with page comments and rotation
        THEN:
            - Should process successfully (comments are logged but not stored)
            - Correct pages should be extracted with rotation applied
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(8)]  # 8 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(return_value=2)  # Has 2 pages
        # Support indexing for rotation (dst_pdf.pages[-1])
        mock_dst_pdf.pages.__getitem__ = mock.Mock(return_value=mock.Mock())
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [
                    {"p": 1, "c": "Important page"},
                    {"p": 2, "c": "Secondary info", "r": 180},
                ],
            ],
        }

        result = bulk_edit.reorganize(doc_ids, processing_instruction)

        # Verify the correct pages were extracted (pages 1 and 2, indices 0 and 1)
        expected_pages = [0, 1]  # 0-based indices
        self.assertEqual(mock_dst_pdf.pages.append.call_count, len(expected_pages))
        for i, expected_idx in enumerate(expected_pages):
            actual_page = mock_dst_pdf.pages.append.call_args_list[i][0][0]
            expected_page = mock_source_pdf.pages[expected_idx]
            self.assertEqual(actual_page, expected_page)

        # Verify rotation was applied to the second page (180 degrees)
        # The rotation happens after dst_pdf.pages.append, so we check pages[-1].rotate
        mock_dst_pdf.pages.__getitem__.assert_called_with(-1)
        rotated_page = mock_dst_pdf.pages.__getitem__.return_value
        rotated_page.rotate.assert_called_once_with(180, relative=False)

        mock_consume_file.assert_called_once()
        self.assertEqual(result, "OK")

    def test_reorganize_validation_errors(self):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called with invalid processing instructions
        THEN:
            - Should raise appropriate validation errors
        """
        doc_ids = [self.doc1.id, self.doc2.id]  # Multiple docs not supported
        processing_instruction = {"docs": [[1, 2]]}

        with self.assertRaises(
            ValueError,
            msg="Reorganize method only supports one document",
        ):
            bulk_edit.reorganize(doc_ids, processing_instruction)

        # Test missing docs field
        doc_ids = [self.doc2.id]
        with self.assertRaises(
            ValueError,
            msg="Processing instruction must contain 'docs' array",
        ):
            bulk_edit.reorganize(doc_ids, {})

        # Test empty docs array
        with self.assertRaises(ValueError, msg="'docs' array cannot be empty"):
            bulk_edit.reorganize(doc_ids, {"docs": []})

    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    @mock.patch("documents.tasks.consume_file.s")
    def test_reorganize_invalid_page_numbers(
        self,
        mock_consume_file,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
    ):
        """
        GIVEN:
            - Existing document with 8 pages
        WHEN:
            - Reorganize action is called with invalid page numbers
        THEN:
            - Should skip invalid pages but process valid ones
            - Only valid pages should be added to the output PDF
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(8)]  # 8 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(return_value=2)  # Has 2 valid pages
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [1, 999, 2],  # Page 999 doesn't exist, but 1 and 2 do
            ],
        }

        with self.assertLogs("paperless.bulk_edit", level="WARNING") as cm:
            result = bulk_edit.reorganize(doc_ids, processing_instruction)

            # Should log warning about invalid page number
            warning_found = any("Invalid page number 999" in log for log in cm.output)
            self.assertTrue(warning_found)

        # Verify only valid pages were processed (pages 1 and 2, indices 0 and 1)
        expected_pages = [0, 1]  # 0-based indices for pages 1 and 2
        self.assertEqual(mock_dst_pdf.pages.append.call_count, len(expected_pages))
        for i, expected_idx in enumerate(expected_pages):
            actual_page = mock_dst_pdf.pages.append.call_args_list[i][0][0]
            expected_page = mock_source_pdf.pages[expected_idx]
            self.assertEqual(actual_page, expected_page)

        mock_consume_file.assert_called_once()
        self.assertEqual(result, "OK")

    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("pikepdf.Pdf.save")
    def test_reorganize_with_errors(self, mock_save_pdf, mock_consume_file):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called but PDF save fails
        THEN:
            - Should raise exception and not consume files
        """
        mock_save_pdf.side_effect = Exception("Error saving PDF")
        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [[1, 2, 3]],
        }

        with self.assertRaises(Exception):
            bulk_edit.reorganize(doc_ids, processing_instruction)

        mock_consume_file.assert_not_called()

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    def test_reorganize_and_delete_original(
        self,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
        mock_chord,
        mock_consume_file,
        mock_delete_documents,
    ):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called with delete_original=True
        THEN:
            - Should create reorganized documents and queue original for deletion
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(6)]  # 6 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        # Mock two destination PDFs for split reorganization
        mock_dst_pdf1 = mock.Mock()
        mock_dst_pdf1.pages = mock.Mock()
        mock_dst_pdf1.pages.__len__ = mock.Mock(return_value=3)  # First doc has 3 pages

        mock_dst_pdf2 = mock.Mock()
        mock_dst_pdf2.pages = mock.Mock()
        mock_dst_pdf2.pages.__len__ = mock.Mock(
            return_value=3,
        )  # Second doc has 3 pages

        mock_new_pdf.side_effect = [mock_dst_pdf1, mock_dst_pdf2]

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [1, 2, 3],  # First doc: pages 1, 2, 3
                [4, 5, 6],  # Second doc: pages 4, 5, 6
            ],
        }

        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
            delete_original=True,
        )

        # Verify reorganization was executed
        self.assertEqual(result, "OK")

        # Verify consume tasks were created (should be 2 consume tasks)
        self.assertEqual(mock_consume_file.call_count, 2)

        # Verify chord was called with consume tasks and delete task
        mock_chord.assert_called_once()
        chord_args = mock_chord.call_args[1]
        self.assertIn("header", chord_args)
        self.assertIn("body", chord_args)

        # Verify the delete task was set up correctly
        mock_delete_documents.assert_called_once_with([self.doc2.id])

        # Verify the consume tasks have the expected titles
        first_call_args, _ = mock_consume_file.call_args_list[0]
        self.assertEqual(first_call_args[1].title, "B (part 1)")

        second_call_args, _ = mock_consume_file.call_args_list[1]
        self.assertEqual(second_call_args[1].title, "B (part 2)")

    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    def test_reorganize_single_document_no_delete(
        self,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
        mock_consume_file,
    ):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called for single document (no splitting) with delete_original=False
        THEN:
            - Should create reorganized document and original should be preserved
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(6)]  # 6 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(
            return_value=6,
        )  # Single doc has all pages
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [6, 5, 4, 3, 2, 1],  # Single doc: reordered pages
            ],
        }

        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
            delete_original=False,  # Explicitly don't delete original
        )

        # Verify reorganization was executed
        self.assertEqual(result, "OK")

        # Verify only one consume task was created
        mock_consume_file.assert_called_once()

        # Verify the title is set correctly for reordered document
        call_args, _ = mock_consume_file.call_args
        self.assertEqual(call_args[1].title, "B (reorganized)")

    @mock.patch("documents.bulk_edit.delete.si")
    @mock.patch("documents.bulk_edit.chord")
    @mock.patch("documents.tasks.consume_file.s")
    @mock.patch("magic.from_file")
    @mock.patch("pikepdf.Pdf.save")
    @mock.patch("pikepdf.new")
    @mock.patch("pikepdf.open")
    def test_reorganize_single_document_with_delete_original(
        self,
        mock_open_pdf,
        mock_new_pdf,
        mock_save_pdf,
        mock_magic,
        mock_consume_file,
        mock_chord,
        mock_delete_documents,
    ):
        """
        GIVEN:
            - Existing document
        WHEN:
            - Reorganize action is called for single document with delete_original=True
        THEN:
            - Should create reorganized document and queue original for deletion
        """
        # Setup mocks
        mock_source_pdf = mock.Mock()
        mock_source_pdf.pages = [mock.Mock() for _ in range(6)]  # 6 pages
        mock_open_pdf.return_value.__enter__.return_value = mock_source_pdf

        mock_dst_pdf = mock.Mock()
        mock_dst_pdf.pages = mock.Mock()
        mock_dst_pdf.pages.__len__ = mock.Mock(
            return_value=6,
        )  # Single doc has all pages
        mock_new_pdf.return_value = mock_dst_pdf

        # Mock the magic library to return PDF MIME type
        mock_magic.return_value = "application/pdf"

        doc_ids = [self.doc2.id]
        processing_instruction = {
            "src": ["sample.pdf"],
            "docs": [
                [6, 5, 4, 3, 2, 1],  # Single doc: reordered pages
            ],
        }

        result = bulk_edit.reorganize(
            doc_ids,
            processing_instruction,
            delete_original=True,  # Delete original after reorganization
        )

        # Verify reorganization was executed
        self.assertEqual(result, "OK")

        # Verify only one consume task was created
        mock_consume_file.assert_called_once()

        # Verify the title is set correctly for reordered document
        call_args, _ = mock_consume_file.call_args
        self.assertEqual(call_args[1].title, "B (reorganized)")

        # Verify chord was called with consume task and delete task
        mock_chord.assert_called_once()
        chord_args = mock_chord.call_args[1]
        self.assertIn("header", chord_args)
        self.assertIn("body", chord_args)

        # Verify the delete task was set up correctly
        mock_delete_documents.assert_called_once_with([self.doc2.id])
