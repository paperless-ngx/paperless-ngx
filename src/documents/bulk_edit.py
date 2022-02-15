import itertools

from django.db.models import Q
from django_q.tasks import async_task

from documents.models import Document, Correspondent, DocumentType


def set_correspondent(doc_ids, correspondent):
    if correspondent:
        correspondent = Correspondent.objects.get(id=correspondent)

    qs = Document.objects.filter(
        Q(id__in=doc_ids) & ~Q(correspondent=correspondent))
    affected_docs = [doc.id for doc in qs]
    qs.update(correspondent=correspondent)

    async_task(
        "documents.tasks.bulk_update_documents", document_ids=affected_docs)

    return "OK"


def set_document_type(doc_ids, document_type):
    if document_type:
        document_type = DocumentType.objects.get(id=document_type)

    qs = Document.objects.filter(
        Q(id__in=doc_ids) & ~Q(document_type=document_type))
    affected_docs = [doc.id for doc in qs]
    qs.update(document_type=document_type)

    async_task(
        "documents.tasks.bulk_update_documents", document_ids=affected_docs)

    return "OK"


def add_tag(doc_ids, tag):

    qs = Document.objects.filter(Q(id__in=doc_ids) & ~Q(tags__id=tag))
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.bulk_create([
        DocumentTagRelationship(
            document_id=doc, tag_id=tag) for doc in affected_docs
    ])

    async_task(
        "documents.tasks.bulk_update_documents", document_ids=affected_docs)

    return "OK"


def remove_tag(doc_ids, tag):

    qs = Document.objects.filter(Q(id__in=doc_ids) & Q(tags__id=tag))
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.filter(
        Q(document_id__in=affected_docs) &
        Q(tag_id=tag)
    ).delete()

    async_task(
        "documents.tasks.bulk_update_documents", document_ids=affected_docs)

    return "OK"


def modify_tags(doc_ids, add_tags, remove_tags):
    qs = Document.objects.filter(id__in=doc_ids)
    affected_docs = [doc.id for doc in qs]

    DocumentTagRelationship = Document.tags.through

    DocumentTagRelationship.objects.filter(
        document_id__in=affected_docs,
        tag_id__in=remove_tags,
    ).delete()

    DocumentTagRelationship.objects.bulk_create([DocumentTagRelationship(
        document_id=doc, tag_id=tag) for (doc, tag) in itertools.product(
        affected_docs, add_tags)
    ], ignore_conflicts=True)

    async_task(
        "documents.tasks.bulk_update_documents", document_ids=affected_docs)

    return "OK"


def delete(doc_ids):
    Document.objects.filter(id__in=doc_ids).delete()

    from documents import index

    with index.open_index_writer() as writer:
        for id in doc_ids:
            index.remove_document_by_id(writer, id)

    return "OK"
