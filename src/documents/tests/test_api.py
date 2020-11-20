import os
import shutil
import tempfile
from unittest import mock

from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework.test import APITestCase

from documents.models import Document, Correspondent, DocumentType, Tag


class DocumentApiTest(APITestCase):

    def setUp(self):
        self.scratch_dir = tempfile.mkdtemp()
        self.media_dir = tempfile.mkdtemp()
        self.originals_dir = os.path.join(self.media_dir, "documents", "originals")
        self.thumbnail_dir = os.path.join(self.media_dir, "documents", "thumbnails")

        os.makedirs(self.originals_dir, exist_ok=True)
        os.makedirs(self.thumbnail_dir, exist_ok=True)

        override_settings(
            SCRATCH_DIR=self.scratch_dir,
            MEDIA_ROOT=self.media_dir,
            ORIGINALS_DIR=self.originals_dir,
            THUMBNAIL_DIR=self.thumbnail_dir
        ).enable()

        user = User.objects.create_superuser(username="temp_admin")
        self.client.force_login(user=user)

    def tearDown(self):
        shutil.rmtree(self.scratch_dir, ignore_errors=True)
        shutil.rmtree(self.media_dir, ignore_errors=True)

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
        self.assertEqual(returned_doc['correspondent']['name'], c.name)
        self.assertEqual(returned_doc['document_type']['name'], dt.name)
        self.assertEqual(returned_doc['correspondent']['id'], c.id)
        self.assertEqual(returned_doc['document_type']['id'], dt.id)
        self.assertEqual(returned_doc['correspondent']['id'], returned_doc['correspondent_id'])
        self.assertEqual(returned_doc['document_type']['id'], returned_doc['document_type_id'])
        self.assertEqual(len(returned_doc['tags']), 1)
        self.assertEqual(returned_doc['tags'][0]['name'], tag.name)
        self.assertEqual(returned_doc['tags'][0]['id'], tag.id)
        self.assertListEqual(returned_doc['tags_id'], [tag.id])

        c2 = Correspondent.objects.create(name="c2")

        returned_doc['correspondent_id'] = c2.pk
        returned_doc['title'] = "the new title"

        response = self.client.put('/api/documents/{}/'.format(doc.pk), returned_doc, format='json')

        self.assertEqual(response.status_code, 200)

        doc_after_save = Document.objects.get(id=doc.id)

        self.assertEqual(doc_after_save.correspondent, c2)
        self.assertEqual(doc_after_save.title, "the new title")

        self.client.delete("/api/documents/{}/".format(doc_after_save.pk))

        self.assertEqual(len(Document.objects.all()), 0)

    def test_document_actions(self):

        _, filename = tempfile.mkstemp(dir=self.originals_dir)

        content = b"This is a test"
        content_thumbnail = b"thumbnail content"

        with open(filename, "wb") as f:
            f.write(content)

        doc = Document.objects.create(title="none", filename=os.path.basename(filename), mime_type="application/pdf")

        with open(os.path.join(self.thumbnail_dir, "{:07d}.png".format(doc.pk)), "wb") as f:
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
        self.assertEqual(results[0]['id'], doc2.id)
        self.assertEqual(results[1]['id'], doc3.id)

        response = self.client.get("/api/documents/?tags__id__in={},{}".format(tag_inbox.id, tag_3.id))
        self.assertEqual(response.status_code, 200)
        results = response.data['results']
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['id'], doc1.id)
        self.assertEqual(results[1]['id'], doc3.id)

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
