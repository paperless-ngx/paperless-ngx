import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from whoosh.writing import AsyncWriter

from documents import index
from documents.models import Document, Correspondent, DocumentType, Tag, SavedView
from documents.tests.utils import DirectoriesMixin


class TestDocumentApi(DirectoriesMixin, APITestCase):

    def setUp(self):
        super(TestDocumentApi, self).setUp()

        self.user = User.objects.create_superuser(username="temp_admin")
        self.client.force_login(user=self.user)

    def testDocuments(self):

        response = self.client.get("/api/documents/").data

        self.assertEqual(response['count'], 0)

        c = Correspondent.objects.create(name="c", pk=41)
        dt = DocumentType.objects.create(name="dt", pk=63)
        tag = Tag.objects.create(name="t", pk=85)

        doc = Document.objects.create(title="WOW", content="the content", correspondent=c, document_type=dt, checksum="123", mime_type="application/pdf")

        doc.tags.add(tag)

        response = self.client.get("/api/documents/", format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        returned_doc = response.data['results'][0]
        self.assertEqual(returned_doc['id'], doc.id)
        self.assertEqual(returned_doc['title'], doc.title)
        self.assertEqual(returned_doc['correspondent'], c.id)
        self.assertEqual(returned_doc['document_type'], dt.id)
        self.assertListEqual(returned_doc['tags'], [tag.id])

        c2 = Correspondent.objects.create(name="c2")

        returned_doc['correspondent'] = c2.pk
        returned_doc['title'] = "the new title"

        response = self.client.put('/api/documents/{}/'.format(doc.pk), returned_doc, format='json')

        self.assertEqual(response.status_code, 200)

        doc_after_save = Document.objects.get(id=doc.id)

        self.assertEqual(doc_after_save.correspondent, c2)
        self.assertEqual(doc_after_save.title, "the new title")

        self.client.delete("/api/documents/{}/".format(doc_after_save.pk))

        self.assertEqual(len(Document.objects.all()), 0)

    def test_document_actions(self):

        _, filename = tempfile.mkstemp(dir=self.dirs.originals_dir)

        content = b"This is a test"
        content_thumbnail = b"thumbnail content"

        with open(filename, "wb") as f:
            f.write(content)

        doc = Document.objects.create(title="none", filename=os.path.basename(filename), mime_type="application/pdf")

        with open(os.path.join(self.dirs.thumbnail_dir, "{:07d}.png".format(doc.pk)), "wb") as f:
            f.write(content_thumbnail)

        response = self.client.get('/api/documents/{}/download/'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

        response = self.client.get('/api/documents/{}/preview/'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

        response = self.client.get('/api/documents/{}/thumb/'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content_thumbnail)

    def test_download_with_archive(self):

        _, filename = tempfile.mkstemp(dir=self.dirs.originals_dir)

        content = b"This is a test"
        content_archive = b"This is the same test but archived"

        with open(filename, "wb") as f:
            f.write(content)

        filename = os.path.basename(filename)

        doc = Document.objects.create(title="none", filename=filename,
                                      mime_type="application/pdf")

        with open(doc.archive_path, "wb") as f:
            f.write(content_archive)

        response = self.client.get('/api/documents/{}/download/'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content_archive)

        response = self.client.get('/api/documents/{}/download/?original=true'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

        response = self.client.get('/api/documents/{}/preview/'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content_archive)

        response = self.client.get('/api/documents/{}/preview/?original=true'.format(doc.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

    def test_document_actions_not_existing_file(self):

        doc = Document.objects.create(title="none", filename=os.path.basename("asd"), mime_type="application/pdf")

        response = self.client.get('/api/documents/{}/download/'.format(doc.pk))
        self.assertEqual(response.status_code, 404)

        response = self.client.get('/api/documents/{}/preview/'.format(doc.pk))
        self.assertEqual(response.status_code, 404)

        response = self.client.get('/api/documents/{}/thumb/'.format(doc.pk))
        self.assertEqual(response.status_code, 404)

    def test_document_filters(self):

        doc1 = Document.objects.create(title="none1", checksum="A", mime_type="application/pdf")
        doc2 = Document.objects.create(title="none2", checksum="B", mime_type="application/pdf")
        doc3 = Document.objects.create(title="none3", checksum="C", mime_type="application/pdf")

        tag_inbox = Tag.objects.create(name="t1", is_inbox_tag=True)
        tag_2 = Tag.objects.create(name="t2")
        tag_3 = Tag.objects.create(name="t3")

        doc1.tags.add(tag_inbox)
        doc2.tags.add(tag_2)
        doc3.tags.add(tag_2)
        doc3.tags.add(tag_3)

        response = self.client.get("/api/documents/?is_in_inbox=true")
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], doc1.id)

        response = self.client.get("/api/documents/?is_in_inbox=false")
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]['id'], results[1]['id']], [doc2.id, doc3.id])

        response = self.client.get("/api/documents/?tags__id__in={},{}".format(tag_inbox.id, tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]['id'], results[1]['id']], [doc1.id, doc3.id])

        response = self.client.get("/api/documents/?tags__id__all={},{}".format(tag_2.id, tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], doc3.id)

        response = self.client.get("/api/documents/?tags__id__all={},{}".format(tag_inbox.id, tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 0)

        response = self.client.get("/api/documents/?tags__id__all={}a{}".format(tag_inbox.id, tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 3)

        response = self.client.get("/api/documents/?tags__id__none={}".format(tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        self.assertCountEqual([results[0]['id'], results[1]['id']], [doc1.id, doc2.id])

        response = self.client.get("/api/documents/?tags__id__none={},{}".format(tag_3.id, tag_2.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], doc1.id)

        response = self.client.get("/api/documents/?tags__id__none={},{}".format(tag_2.id, tag_inbox.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 0)

    def test_search_no_query(self):
        response = self.client.get("/api/search/")
        results = response.data['results']

        self.assertEqual(len(results), 0)

    def test_search(self):
        d1=Document.objects.create(title="invoice", content="the thing i bought at a shop and paid with bank account", checksum="A", pk=1)
        d2=Document.objects.create(title="bank statement 1", content="things i paid for in august", pk=2, checksum="B")
        d3=Document.objects.create(title="bank statement 3", content="things i paid for in september", pk=3, checksum="C")
        with AsyncWriter(index.open_index()) as writer:
            # Note to future self: there is a reason we dont use a model signal handler to update the index: some operations edit many documents at once
            # (retagger, renamer) and we don't want to open a writer for each of these, but rather perform the entire operation with one writer.
            # That's why we cant open the writer in a model on_save handler or something.
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)
        response = self.client.get("/api/search/?query=bank")
        results = response.data['results']
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_count'], 1)
        self.assertEqual(len(results), 3)

        response = self.client.get("/api/search/?query=september")
        results = response.data['results']
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_count'], 1)
        self.assertEqual(len(results), 1)

        response = self.client.get("/api/search/?query=statement")
        results = response.data['results']
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['page'], 1)
        self.assertEqual(response.data['page_count'], 1)
        self.assertEqual(len(results), 2)

        response = self.client.get("/api/search/?query=sfegdfg")
        results = response.data['results']
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(response.data['page'], 0)
        self.assertEqual(response.data['page_count'], 0)
        self.assertEqual(len(results), 0)

    def test_search_multi_page(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(55):
                doc = Document.objects.create(checksum=str(i), pk=i+1, title=f"Document {i+1}", content="content")
                index.update_document(writer, doc)

        # This is here so that we test that no document gets returned twice (might happen if the paging is not working)
        seen_ids = []

        for i in range(1, 6):
            response = self.client.get(f"/api/search/?query=content&page={i}")
            results = response.data['results']
            self.assertEqual(response.data['count'], 55)
            self.assertEqual(response.data['page'], i)
            self.assertEqual(response.data['page_count'], 6)
            self.assertEqual(len(results), 10)

            for result in results:
                self.assertNotIn(result['id'], seen_ids)
                seen_ids.append(result['id'])

        response = self.client.get(f"/api/search/?query=content&page=6")
        results = response.data['results']
        self.assertEqual(response.data['count'], 55)
        self.assertEqual(response.data['page'], 6)
        self.assertEqual(response.data['page_count'], 6)
        self.assertEqual(len(results), 5)

        for result in results:
            self.assertNotIn(result['id'], seen_ids)
            seen_ids.append(result['id'])

        response = self.client.get(f"/api/search/?query=content&page=7")
        results = response.data['results']
        self.assertEqual(response.data['count'], 55)
        self.assertEqual(response.data['page'], 6)
        self.assertEqual(response.data['page_count'], 6)
        self.assertEqual(len(results), 5)

    def test_search_invalid_page(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(15):
                doc = Document.objects.create(checksum=str(i), pk=i+1, title=f"Document {i+1}", content="content")
                index.update_document(writer, doc)

        first_page = self.client.get(f"/api/search/?query=content&page=1").data
        second_page = self.client.get(f"/api/search/?query=content&page=2").data
        should_be_first_page_1 = self.client.get(f"/api/search/?query=content&page=0").data
        should_be_first_page_2 = self.client.get(f"/api/search/?query=content&page=dgfd").data
        should_be_first_page_3 = self.client.get(f"/api/search/?query=content&page=").data
        should_be_first_page_4 = self.client.get(f"/api/search/?query=content&page=-7868").data

        self.assertDictEqual(first_page, should_be_first_page_1)
        self.assertDictEqual(first_page, should_be_first_page_2)
        self.assertDictEqual(first_page, should_be_first_page_3)
        self.assertDictEqual(first_page, should_be_first_page_4)
        self.assertNotEqual(len(first_page['results']), len(second_page['results']))

    @mock.patch("documents.index.autocomplete")
    def test_search_autocomplete(self, m):
        m.side_effect = lambda ix, term, limit: [term for _ in range(limit)]

        response = self.client.get("/api/search/autocomplete/?term=test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 10)

        response = self.client.get("/api/search/autocomplete/?term=test&limit=20")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 20)

        response = self.client.get("/api/search/autocomplete/?term=test&limit=-1")
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/search/autocomplete/")
        self.assertEqual(response.status_code, 400)

        response = self.client.get("/api/search/autocomplete/?term=")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 10)

    def test_search_spelling_correction(self):
        with AsyncWriter(index.open_index()) as writer:
            for i in range(55):
                doc = Document.objects.create(checksum=str(i), pk=i+1, title=f"Document {i+1}", content=f"Things document {i+1}")
                index.update_document(writer, doc)

        response = self.client.get("/api/search/?query=thing")
        correction = response.data['corrected_query']

        self.assertEqual(correction, "things")

        response = self.client.get("/api/search/?query=things")
        correction = response.data['corrected_query']

        self.assertEqual(correction, None)

    def test_search_more_like(self):
        d1=Document.objects.create(title="invoice", content="the thing i bought at a shop and paid with bank account", checksum="A", pk=1)
        d2=Document.objects.create(title="bank statement 1", content="things i paid for in august", pk=2, checksum="B")
        d3=Document.objects.create(title="bank statement 3", content="things i paid for in september", pk=3, checksum="C")
        with AsyncWriter(index.open_index()) as writer:
            index.update_document(writer, d1)
            index.update_document(writer, d2)
            index.update_document(writer, d3)

        response = self.client.get(f"/api/search/?more_like={d2.id}")

        self.assertEqual(response.status_code, 200)

        results = response.data['results']

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], d3.id)
        self.assertEqual(results[1]['id'], d1.id)

    def test_statistics(self):

        doc1 = Document.objects.create(title="none1", checksum="A")
        doc2 = Document.objects.create(title="none2", checksum="B")
        doc3 = Document.objects.create(title="none3", checksum="C")

        tag_inbox = Tag.objects.create(name="t1", is_inbox_tag=True)

        doc1.tags.add(tag_inbox)

        response = self.client.get("/api/statistics/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['documents_total'], 3)
        self.assertEqual(response.data['documents_inbox'], 1)

    @mock.patch("documents.views.async_task")
    def test_upload(self, m):

        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f})

        self.assertEqual(response.status_code, 200)

        m.assert_called_once()

        args, kwargs = m.call_args
        self.assertEqual(kwargs['override_filename'], "simple.pdf")
        self.assertIsNone(kwargs['override_title'])
        self.assertIsNone(kwargs['override_correspondent_id'])
        self.assertIsNone(kwargs['override_document_type_id'])
        self.assertIsNone(kwargs['override_tag_ids'])

    @mock.patch("documents.views.async_task")
    def test_upload_invalid_form(self, m):

        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"documenst": f})
        self.assertEqual(response.status_code, 400)
        m.assert_not_called()

    @mock.patch("documents.views.async_task")
    def test_upload_invalid_file(self, m):

        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.zip"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f})
        self.assertEqual(response.status_code, 400)
        m.assert_not_called()

    @mock.patch("documents.views.async_task")
    def test_upload_with_title(self, async_task):
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f, "title": "my custom title"})
        self.assertEqual(response.status_code, 200)

        async_task.assert_called_once()

        args, kwargs = async_task.call_args

        self.assertEqual(kwargs['override_title'], "my custom title")

    @mock.patch("documents.views.async_task")
    def test_upload_with_correspondent(self, async_task):
        c = Correspondent.objects.create(name="test-corres")
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f, "correspondent": c.id})
        self.assertEqual(response.status_code, 200)

        async_task.assert_called_once()

        args, kwargs = async_task.call_args

        self.assertEqual(kwargs['override_correspondent_id'], c.id)

    @mock.patch("documents.views.async_task")
    def test_upload_with_invalid_correspondent(self, async_task):
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f, "correspondent": 3456})
        self.assertEqual(response.status_code, 400)

        async_task.assert_not_called()

    @mock.patch("documents.views.async_task")
    def test_upload_with_document_type(self, async_task):
        dt = DocumentType.objects.create(name="invoice")
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f, "document_type": dt.id})
        self.assertEqual(response.status_code, 200)

        async_task.assert_called_once()

        args, kwargs = async_task.call_args

        self.assertEqual(kwargs['override_document_type_id'], dt.id)

    @mock.patch("documents.views.async_task")
    def test_upload_with_invalid_document_type(self, async_task):
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post("/api/documents/post_document/", {"document": f, "document_type": 34578})
        self.assertEqual(response.status_code, 400)

        async_task.assert_not_called()

    @mock.patch("documents.views.async_task")
    def test_upload_with_tags(self, async_task):
        t1 = Tag.objects.create(name="tag1")
        t2 = Tag.objects.create(name="tag2")
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "tags": [t2.id, t1.id]})
        self.assertEqual(response.status_code, 200)

        async_task.assert_called_once()

        args, kwargs = async_task.call_args

        self.assertCountEqual(kwargs['override_tag_ids'], [t1.id, t2.id])

    @mock.patch("documents.views.async_task")
    def test_upload_with_invalid_tags(self, async_task):
        t1 = Tag.objects.create(name="tag1")
        t2 = Tag.objects.create(name="tag2")
        with open(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), "rb") as f:
            response = self.client.post(
                "/api/documents/post_document/",
                {"document": f, "tags": [t2.id, t1.id, 734563]})
        self.assertEqual(response.status_code, 400)

        async_task.assert_not_called()

    def test_get_metadata(self):
        doc = Document.objects.create(title="test", filename="file.pdf", mime_type="image/png", archive_checksum="A")

        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "documents", "thumbnails", "0000001.png"), doc.source_path)
        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), doc.archive_path)

        response = self.client.get(f"/api/documents/{doc.pk}/metadata/")
        self.assertEqual(response.status_code, 200)

        meta = response.data

        self.assertEqual(meta['original_mime_type'], "image/png")
        self.assertTrue(meta['has_archive_version'])
        self.assertEqual(len(meta['original_metadata']), 0)
        self.assertGreater(len(meta['archive_metadata']), 0)

    def test_get_metadata_no_archive(self):
        doc = Document.objects.create(title="test", filename="file.pdf", mime_type="application/pdf")

        shutil.copy(os.path.join(os.path.dirname(__file__), "samples", "simple.pdf"), doc.source_path)

        response = self.client.get(f"/api/documents/{doc.pk}/metadata/")
        self.assertEqual(response.status_code, 200)

        meta = response.data

        self.assertEqual(meta['original_mime_type'], "application/pdf")
        self.assertFalse(meta['has_archive_version'])
        self.assertGreater(len(meta['original_metadata']), 0)
        self.assertIsNone(meta['archive_metadata'])

    def test_saved_views(self):
        u1 = User.objects.create_user("user1")
        u2 = User.objects.create_user("user2")

        v1 = SavedView.objects.create(user=u1, name="test1", sort_field="", show_on_dashboard=False, show_in_sidebar=False)
        v2 = SavedView.objects.create(user=u2, name="test2", sort_field="", show_on_dashboard=False, show_in_sidebar=False)
        v3 = SavedView.objects.create(user=u2, name="test3", sort_field="", show_on_dashboard=False, show_in_sidebar=False)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 0)

        self.assertEqual(self.client.get(f"/api/saved_views/{v1.id}/").status_code, 404)

        self.client.force_login(user=u1)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

        self.assertEqual(self.client.get(f"/api/saved_views/{v1.id}/").status_code, 200)

        self.client.force_login(user=u2)

        response = self.client.get("/api/saved_views/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 2)

        self.assertEqual(self.client.get(f"/api/saved_views/{v1.id}/").status_code, 404)

    def test_create_update_patch(self):

        u1 = User.objects.create_user("user1")

        view = {
            "name": "test",
            "show_on_dashboard": True,
            "show_in_sidebar": True,
            "sort_field": "created2",
            "filter_rules": [
                {
                    "rule_type": 4,
                    "value": "test"
                }
            ]
        }

        response = self.client.post("/api/saved_views/", view, format='json')
        self.assertEqual(response.status_code, 201)

        v1 = SavedView.objects.get(name="test")
        self.assertEqual(v1.sort_field, "created2")
        self.assertEqual(v1.filter_rules.count(), 1)
        self.assertEqual(v1.user, self.user)

        response = self.client.patch(f"/api/saved_views/{v1.id}/", {
            "show_in_sidebar": False
        }, format='json')

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(v1.show_in_sidebar)
        self.assertEqual(v1.filter_rules.count(), 1)

        view['filter_rules'] = [{
            "rule_type": 12,
            "value": "secret"
        }]

        response = self.client.put(f"/api/saved_views/{v1.id}/", view, format='json')
        self.assertEqual(response.status_code, 200)

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(v1.filter_rules.count(), 1)
        self.assertEqual(v1.filter_rules.first().value, "secret")

        view['filter_rules'] = []

        response = self.client.put(f"/api/saved_views/{v1.id}/", view, format='json')
        self.assertEqual(response.status_code, 200)

        v1 = SavedView.objects.get(id=v1.id)
        self.assertEqual(v1.filter_rules.count(), 0)
